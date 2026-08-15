"""Chat — grounded answers (non-streaming + SSE streaming) with persisted history."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.db.base import SessionLocal, get_session
from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import Chat, Message, User
from app.schemas import AnswerOut, ChatIn, ChatOut, MessageOut
from app.services import chat_service

router = APIRouter(tags=["chat"])


async def _ensure_chat(session: AsyncSession, user: User, chat_id: int | None, first: str) -> Chat:
    if chat_id is not None:
        chat = (await session.execute(
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))).scalar_one_or_none()
        if chat is None:
            raise HTTPException(404, "Chat not found")
        return chat
    chat = Chat(user_id=user.id, title=first[:60] or "New chat")
    session.add(chat)
    await session.flush()
    return chat


@router.post("/chat", response_model=AnswerOut)
async def chat(body: ChatIn, user: User = Depends(get_current_user),
               services: AlaServices = Depends(services_dependency),
               session: AsyncSession = Depends(get_session)) -> AnswerOut:
    result = await run_in_threadpool(chat_service.build_answer, services, body.message,
                                     top_k=body.top_k, concept=body.concept)
    chat = await _ensure_chat(session, user, body.chat_id, body.message)
    session.add(Message(chat_id=chat.id, role="user", content=body.message))
    session.add(Message(chat_id=chat.id, role="assistant", content=result["answer"],
                        data_json=json.dumps({k: result[k] for k in
                                              ("confidence", "citations", "evidence", "reasoning",
                                               "grounding", "generator", "needs_web")}, default=str)))
    await session.commit()
    result["chat_id"] = chat.id
    return AnswerOut(**result)


@router.post("/chat/stream")
async def chat_stream(body: ChatIn, user: User = Depends(get_current_user),
                      services: AlaServices = Depends(services_dependency),
                      session: AsyncSession = Depends(get_session)):
    chat = await _ensure_chat(session, user, body.chat_id, body.message)
    session.add(Message(chat_id=chat.id, role="user", content=body.message))
    await session.commit()
    chat_id = chat.id

    async def event_gen():
        sync_gen = chat_service.stream_answer(services, body.message, top_k=body.top_k)
        sentinel = object()
        full, final = "", {}
        while True:
            item = await run_in_threadpool(lambda: next(sync_gen, sentinel))
            if item is sentinel:
                break
            if item.get("type") == "token":
                full += item["text"]
            else:
                final = item
            yield {"event": "message", "data": json.dumps(item, default=str)}
        async with SessionLocal() as s:                      # persist the assistant message
            s.add(Message(chat_id=chat_id, role="assistant", content=full,
                          data_json=json.dumps(final, default=str)))
            await s.commit()
        yield {"event": "done", "data": json.dumps({"chat_id": chat_id})}

    return EventSourceResponse(event_gen())


@router.get("/chats", response_model=list[ChatOut])
async def list_chats(user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(get_session)) -> list[ChatOut]:
    rows = (await session.execute(select(Chat).where(Chat.user_id == user.id)
                                  .order_by(Chat.updated_at.desc()))).scalars().all()
    return [ChatOut(id=c.id, title=c.title, updated_at=c.updated_at.isoformat()) for c in rows]


@router.get("/chats/{chat_id}", response_model=list[MessageOut])
async def chat_messages(chat_id: int, user: User = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)) -> list[MessageOut]:
    chat = (await session.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))).scalar_one_or_none()
    if chat is None:
        raise HTTPException(404, "Chat not found")
    msgs = (await session.execute(select(Message).where(Message.chat_id == chat_id)
                                  .order_by(Message.id))).scalars().all()
    return [MessageOut(id=m.id, role=m.role, content=m.content,
                       data=json.loads(m.data_json) if m.data_json else {}) for m in msgs]


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: int, user: User = Depends(get_current_user),
                      session: AsyncSession = Depends(get_session)) -> dict:
    await session.execute(delete(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    await session.commit()
    return {"ok": True}
