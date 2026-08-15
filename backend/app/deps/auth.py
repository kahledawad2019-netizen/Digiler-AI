"""Auth dependencies — current user + role-based access control."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.base import get_session
from app.models import User

_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{get_settings().api_prefix}/auth/login", auto_error=False)


async def get_current_user(token: str | None = Depends(_oauth2),
                           session: AsyncSession = Depends(get_session)) -> User:
    cred_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise cred_exc
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise cred_exc
    user = (await session.execute(select(User).where(User.email == payload.get("sub")))).scalar_one_or_none()
    if user is None:
        raise cred_exc
    return user


def require_role(*roles: str):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if roles and user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user
    return _dep
