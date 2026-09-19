import os

# Tests use an in-memory SQLite database; must be set before importing backend
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import audit, models
from backend.ratelimit import login_limiter
from backend.database import Base, get_db
from backend.main import app
from backend.security import hash_password

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enable_fk(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
audit.session_factory = TestingSession


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    db.add_all(
        [
            models.User(username="admin", password_hash=hash_password("admin123"), role="admin"),
            models.User(username="viewer", password_hash=hash_password("viewer123"), role="user"),
        ]
    )
    db.commit()
    db.close()
    login_limiter.clear()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    # seed_admin in the lifespan uses the real SessionLocal, so the lifespan is not entered here
    return TestClient(app)


def _login(client, username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return _login(client, "admin", "admin123")


@pytest.fixture
def viewer(client):
    return _login(client, "viewer", "viewer123")


@pytest.fixture
def student_payload():
    return {"name": "Alice Smith", "age": 20, "gender": "female", "student_no": "S001", "major": "Computer Science"}
