"""Authentication — register / login / refresh / me (JWT + RBAC)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (create_access_token, create_refresh_token, decode_token,
                               hash_password, verify_password)
from app.db.base import get_session
from app.deps.auth import get_current_user
from app.models import User
from app.schemas import RefreshIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.email, role=user.role),
                    refresh_token=create_refresh_token(user.email))


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    exists = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    role = body.role if body.role in ("student", "instructor", "admin") else "student"
    user = User(email=body.email, hashed_password=hash_password(body.password), name=body.name,
                role=role)
    session.add(user)
    await session.flush()
    user.student_id = f"student-{user.id}"
    await session.commit()
    return _tokens(user)


@router.post("/login", response_model=TokenOut)
async def login(form: OAuth2PasswordRequestForm = Depends(),
                session: AsyncSession = Depends(get_session)) -> TokenOut:
    user = (await session.execute(select(User).where(User.email == form.username))).scalar_one_or_none()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return _tokens(user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = (await session.execute(select(User).where(User.email == payload.get("sub")))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return _tokens(user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name, role=user.role,
                   student_id=user.student_id, photo_url=user.photo_url)
