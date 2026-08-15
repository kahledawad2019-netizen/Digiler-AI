"""Admin panel — user management + platform stats (role: admin).

A thin control surface over existing stores: users live in the web DB (SQLAlchemy),
the catalog / concept graph / LLM health come from the shared ala services. No
business logic is re-implemented here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.base import get_session
from app.deps.auth import require_role
from app.deps.services import AlaServices, services_dependency
from app.models import Chat, Message, UploadRecord, User

router = APIRouter(prefix="/admin", tags=["admin"])

ROLES = {"student", "instructor", "admin"}


def _user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role,
            "student_id": u.student_id, "created_at": u.created_at.isoformat()}


async def _admin_count(session: AsyncSession) -> int:
    return int((await session.execute(
        select(func.count()).select_from(User).where(User.role == "admin"))).scalar_one())


@router.get("/users")
async def list_users(session: AsyncSession = Depends(get_session),
                     _admin: User = Depends(require_role("admin"))) -> dict:
    rows = (await session.execute(select(User).order_by(User.id))).scalars().all()
    return {"users": [_user_out(u) for u in rows], "total": len(rows)}


class RoleUpdate(BaseModel):
    role: str


@router.patch("/users/{user_id}")
async def set_user_role(user_id: int, body: RoleUpdate,
                        session: AsyncSession = Depends(get_session),
                        admin: User = Depends(require_role("admin"))) -> dict:
    if body.role not in ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"role must be one of {sorted(ROLES)}")
    target = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    # Never allow removing the last remaining admin (would lock everyone out).
    if target.role == "admin" and body.role != "admin" and await _admin_count(session) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot demote the last admin")
    target.role = body.role
    await session.commit()
    return _user_out(target)


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session),
                      admin: User = Depends(require_role("admin"))) -> dict:
    if user_id == admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot delete your own account")
    target = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.role == "admin" and await _admin_count(session) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot delete the last admin")
    await session.execute(delete(User).where(User.id == user_id))  # chats cascade
    await session.commit()
    return {"deleted": user_id}


@router.get("/stats")
async def platform_stats(_admin: User = Depends(require_role("admin")),
                         session: AsyncSession = Depends(get_session),
                         services: AlaServices = Depends(services_dependency)) -> dict:
    by_role = dict((await session.execute(
        select(User.role, func.count()).group_by(User.role))).all())
    total_users = sum(by_role.values())
    total_chats = int((await session.execute(select(func.count()).select_from(Chat))).scalar_one())
    total_messages = int((await session.execute(select(func.count()).select_from(Message))).scalar_one())
    total_uploads = int((await session.execute(select(func.count()).select_from(UploadRecord))).scalar_one())

    def _knowledge():
        return {"catalog_resources": len(services.catalog.list_all(record_status="active")),
                "graph": services.graph.statistics()}
    knowledge = await run_in_threadpool(_knowledge)

    return {"users": {"total": total_users, "by_role": by_role},
            "chats": total_chats, "messages": total_messages, "uploads": total_uploads,
            "knowledge": knowledge}


@router.get("/health")
async def component_health(_admin: User = Depends(require_role("admin")),
                           services: AlaServices = Depends(services_dependency)) -> dict:
    from ala.llm.factory import available_provider
    from ala.llm.provider import LLMConfig

    def _run():
        cfg = LLMConfig.from_settings(services.settings)
        gstats = services.graph.statistics()
        vloc = ""
        try:
            vloc = str(services.settings.retrieval["vector_store"]["location"])
        except Exception:
            vloc = "unknown"
        return {
            "llm": {"provider": cfg.provider, "model": cfg.model, "base_url": cfg.base_url,
                    "reachable": available_provider(services.settings) is not None},
            "catalog": {"ok": True, "resources": len(services.catalog.list_all(record_status="active"))},
            "graph": {"ok": gstats.get("nodes", 0) > 0, "nodes": gstats.get("nodes", 0),
                      "edges": gstats.get("edges", 0)},
            "vector_store": {"location": vloc},
        }
    return await run_in_threadpool(_run)
