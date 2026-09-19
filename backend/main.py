import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from . import models
from .config import ADMIN_PASSWORD, ADMIN_USERNAME, CORS_ORIGINS
from .database import SessionLocal
from .audit import AuditMiddleware
from .routers import audit, auth, classes, courses, enrollments, stats, students
from .security import hash_password

logger = logging.getLogger("uvicorn.error")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def seed_admin() -> None:
    """Create the default admin when no users exist yet."""
    db = SessionLocal()
    try:
        if db.query(models.User).first() is None:
            db.add(
                models.User(
                    username=ADMIN_USERNAME,
                    password_hash=hash_password(ADMIN_PASSWORD),
                    role="admin",
                )
            )
            db.commit()
            logger.info("Created default admin account: %s", ADMIN_USERNAME)
    except (OperationalError, ProgrammingError) as e:
        logger.warning("Could not seed admin; check the database connection and run `alembic upgrade head`: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_admin()
    yield


app = FastAPI(title="Student Management API", lifespan=lifespan)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app.add_middleware(AuditMiddleware)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=400, content={"detail": "Data conflict: unique or foreign key constraint violated"})


API_PREFIX = "/api"
for router in (
    auth.router,
    students.router,
    classes.router,
    courses.router,
    enrollments.router,
    stats.router,
    audit.router,
):
    app.include_router(router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health", tags=["health"])
def health():
    return {"status": "ok"}


# Serve the frontend from the backend: open http://127.0.0.1:8000/
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
