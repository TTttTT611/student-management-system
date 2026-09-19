"""Audit middleware: records every write request (POST/PUT/DELETE) under /api, including login attempts."""
import json
import logging

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from . import models
from .config import COOKIE_NAME
from .database import SessionLocal
from .security import client_ip, decode_token

logger = logging.getLogger("uvicorn.error")

# Tests swap this for the test database session factory
session_factory = SessionLocal

WRITE_METHODS = {"POST", "PUT", "DELETE"}
SENSITIVE_KEYS = {"password", "old_password", "new_password"}
MAX_DETAIL = 1000


def _mask(obj):
    if isinstance(obj, dict):
        return {k: ("***" if k in SENSITIVE_KEYS else _mask(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mask(v) for v in obj]
    return obj


def _current_user_from_request(request: Request) -> tuple[int | None, str | None]:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.cookies.get(COOKIE_NAME)
    if not token:
        return None, None
    try:
        user_id = int(decode_token(token)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None, None
    db = session_factory()
    try:
        user = db.get(models.User, user_id)
        return (user.id, user.username) if user else (None, None)
    finally:
        db.close()


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        should_log = request.method in WRITE_METHODS and request.url.path.startswith("/api/")
        if not should_log:
            return await call_next(request)

        body_bytes = await request.body()
        response = await call_next(request)

        detail = None
        content_type = request.headers.get("content-type", "")
        if body_bytes and content_type.startswith("application/json"):
            try:
                detail = json.dumps(_mask(json.loads(body_bytes)), ensure_ascii=False)
            except ValueError:
                detail = None
        elif body_bytes:
            detail = f"<{content_type.split(';')[0] or 'binary'} {len(body_bytes)} bytes>"
        if detail and len(detail) > MAX_DETAIL:
            detail = detail[:MAX_DETAIL] + "…"

        if request.url.path.endswith("/auth/login"):
            # For login requests record the attempted username, not a stale session cookie
            user_id = None
            try:
                username = json.loads(body_bytes).get("username")
            except (ValueError, AttributeError):
                username = None
        else:
            user_id, username = _current_user_from_request(request)

        db = session_factory()
        try:
            db.add(
                models.AuditLog(
                    user_id=user_id,
                    username=(username or "")[:50] or None,
                    ip=client_ip(request),
                    method=request.method,
                    path=str(request.url.path)[:255],
                    status=response.status_code,
                    detail=detail,
                )
            )
            db.commit()
        except Exception as e:  # a failed log write must never break the request
            logger.warning("Failed to write audit log: %s", e)
        finally:
            db.close()
        return response
