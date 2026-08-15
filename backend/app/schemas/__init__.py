"""Pydantic v2 request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field


# -- auth ------------------------------------------------------------------- #
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = ""
    role: str = "student"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str
    student_id: str
    photo_url: str = ""


# -- chat ------------------------------------------------------------------- #
class Citation(BaseModel):
    cid: str = ""
    label: str = ""
    source_type: str = ""
    locator: str = ""
    page: int | None = None
    slide: int | None = None
    timestamp: float | None = None
    link: str = ""
    resolvable: bool = False


class AnswerOut(BaseModel):
    answer: str
    confidence: float = 0.0
    grounding: float | None = None
    generator: str = ""
    citations: list[Citation] = []
    evidence: list[dict] = []
    reasoning: list[str] = []
    used_web: bool = False
    needs_web: bool = False
    chat_id: int | None = None


class ChatIn(BaseModel):
    message: str
    chat_id: int | None = None
    concept: str | None = None
    top_k: int = 8


class ChatOut(BaseModel):
    id: int
    title: str
    updated_at: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    data: dict = {}


# -- generic ---------------------------------------------------------------- #
class Ok(BaseModel):
    ok: bool = True
    detail: str = ""
    data: Any = None
