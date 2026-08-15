"""Security primitives — password hashing + JWT (access/refresh)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def _token(subject: str, *, minutes: int | None = None, days: int | None = None,
           token_type: str = "access", extra: dict | None = None) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + (timedelta(days=days) if days else timedelta(minutes=minutes or 30))
    payload: dict[str, Any] = {"sub": subject, "type": token_type, "iat": now, "exp": exp}
    payload.update(extra or {})
    return jwt.encode(payload, s.secret_key, algorithm=s.algorithm)


def create_access_token(subject: str, *, role: str = "student") -> str:
    s = get_settings()
    return _token(subject, minutes=s.access_token_minutes, token_type="access", extra={"role": role})


def create_refresh_token(subject: str) -> str:
    s = get_settings()
    return _token(subject, days=s.refresh_token_days, token_type="refresh")


def decode_token(token: str) -> dict | None:
    s = get_settings()
    try:
        return jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
    except JWTError:
        return None
