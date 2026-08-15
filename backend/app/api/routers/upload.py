"""Upload — a file automatically flows through the existing ingestion pipeline.

Ingestion → DIR → chunking → metadata → embedding → Qdrant → BM25 → concept graph
is performed by the existing ``IncrementalIngestor`` (no step re-implemented). NOTE:
concurrent ingestion while GraphRAG holds Qdrant requires **Qdrant in server mode**
(the docker-compose provides it); local-path mode is single-process only.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db.base import get_session
from app.deps.auth import require_role
from app.deps.services import AlaServices, services_dependency
from app.models import UploadRecord, User

router = APIRouter(prefix="/upload", tags=["upload"])

_DOC_TYPE = {".pdf": "reference", ".pptx": "lecture_slides", ".ppsx": "lecture_slides",
             ".docx": "reference", ".txt": "lesson_page", ".md": "lesson_page",
             ".ipynb": "notebook", ".vtt": "video", ".srt": "video",
             ".png": "other", ".jpg": "other", ".jpeg": "other"}


def _safe_name(filename: str) -> str:
    """Sanitise an uploaded filename to a single, safe path component.

    Strips any directory parts and disallows path-traversal — an attacker-supplied
    name like ``../../evil.txt`` must never escape the upload directory.
    """
    name = Path(filename or "").name                     # drop any directory components
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)         # allowlist safe characters
    if not name or name in (".", ".."):
        raise HTTPException(400, "Invalid filename")
    return name


def _ingest(services: AlaServices, path: Path, *, track: str, course: str, module: str,
            title: str) -> dict:
    from ala.core.enums import DocType, Role
    from ala.ingestion.context import ResourceClassification
    suffix = path.suffix.lower()
    if suffix in (".vtt", ".srt"):
        from ala.video.ingest import VideoIngestor
        vi = VideoIngestor(services.settings)
        out = vi.ingest_video(str(path), title=title)
        return {"resource_id": out.resource_id, "ok": out.ok, "n": out.n_segments}
    dt = DocType(_DOC_TYPE.get(suffix, "other"))
    cls = ResourceClassification(track=track, course=course, module=module, title=title,
                                 doc_type=dt, role=Role.MATERIAL)
    out = services.bundle.ingestor.ingest(str(path), cls)
    return {"resource_id": out.resource_id, "ok": out.ok, "n": out.n_children}


@router.post("")
async def upload(file: UploadFile = File(...), course: str = Form("uploads"),
                 module: str = Form("misc"), track: str = Form("uploads"),
                 services: AlaServices = Depends(services_dependency),
                 user: User = Depends(require_role("student", "instructor", "admin")),
                 session: AsyncSession = Depends(get_session)) -> dict:
    s = get_settings()
    safe_name = _safe_name(file.filename)
    if Path(safe_name).suffix.lower() not in _DOC_TYPE:
        raise HTTPException(415, f"Unsupported file type: {file.filename}")
    dest_dir = services.settings.raw_path / track / course / module
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_name
    data = await file.read()
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File too large")
    dest.write_bytes(data)

    record = UploadRecord(user_id=user.id, filename=safe_name, status="pending")
    session.add(record)
    await session.flush()
    try:
        result = await run_in_threadpool(_ingest, services, dest, track=track, course=course,
                                         module=module, title=Path(safe_name).stem)
        record.resource_id = result.get("resource_id", "")
        record.status = "indexed" if result.get("ok") else "failed"
        record.detail = f"{result.get('n', 0)} chunks"
    except Exception as exc:                                   # noqa: BLE001
        record.status = "failed"
        record.detail = str(exc)[:500]
    await session.commit()
    return {"id": record.id, "filename": record.filename, "resource_id": record.resource_id,
            "status": record.status, "detail": record.detail}


@router.get("s")
async def list_uploads(user: User = Depends(require_role("student", "instructor", "admin")),
                       session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(select(UploadRecord).where(UploadRecord.user_id == user.id)
                                  .order_by(UploadRecord.id.desc()))).scalars().all()
    return {"uploads": [{"id": r.id, "filename": r.filename, "resource_id": r.resource_id,
                         "status": r.status, "detail": r.detail} for r in rows]}
