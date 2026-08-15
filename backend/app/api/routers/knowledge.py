"""Knowledge Base — catalog tree + per-resource actions (all via the retrieval pipeline).

Summaries/quizzes/related-concepts are produced by the existing GraphRAG + concept
graph, never by prompting the LLM directly on a document.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User
from app.services import chat_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
log = logging.getLogger("digiler.knowledge")


def _metas(services: AlaServices):
    from ala.metadata.schema import ResourceMetadata
    rows = services.catalog.list_all(record_status="active")
    return [ResourceMetadata.from_dict(json.loads(r["metadata_json"])) for r in rows]


@router.get("/tree")
async def tree(services: AlaServices = Depends(services_dependency),
               user: User = Depends(get_current_user)) -> dict:
    metas = await run_in_threadpool(_metas, services)
    courses: dict = {}
    for m in metas:
        c = courses.setdefault(m.course, {"course": m.course, "track": m.track, "modules": {}})
        mod = c["modules"].setdefault(m.module or "misc", {"module": m.module or "misc", "resources": []})
        mod["resources"].append({"resource_id": m.resource_id, "title": m.title,
                                 "doc_type": str(m.doc_type), "topics": list(m.topics)[:6]})
    for c in courses.values():
        c["modules"] = sorted(c["modules"].values(), key=lambda x: x["module"])
    return {"courses": sorted(courses.values(), key=lambda x: x["course"])}


@router.get("/resources")
async def resources(course: str | None = None, doc_type: str | None = None,
                    q: str | None = Query(None), limit: int = 100,
                    services: AlaServices = Depends(services_dependency),
                    user: User = Depends(get_current_user)) -> dict:
    metas = await run_in_threadpool(_metas, services)
    out = []
    for m in metas:
        if course and m.course != course:
            continue
        if doc_type and str(m.doc_type) != doc_type:
            continue
        if q and q.lower() not in (m.title + " " + " ".join(m.topics)).lower():
            continue
        out.append({"resource_id": m.resource_id, "title": m.title, "course": m.course,
                    "module": m.module, "doc_type": str(m.doc_type)})
    return {"resources": out[:limit], "total": len(out)}


@router.get("/resource/{resource_id}")
async def resource_detail(resource_id: str, services: AlaServices = Depends(services_dependency),
                          user: User = Depends(get_current_user)) -> dict:
    meta = await run_in_threadpool(services.catalog.get, resource_id)
    if meta is None:
        raise HTTPException(404, "Resource not found")
    return {"resource_id": meta.resource_id, "title": meta.title, "course": meta.course,
            "module": meta.module, "doc_type": str(meta.doc_type), "language": str(meta.language),
            "topics": list(meta.topics), "keywords": list(meta.pedagogy.keywords),
            "file_path": meta.file.file_path}


@router.post("/resource/{resource_id}/summarize")
async def summarize(resource_id: str, services: AlaServices = Depends(services_dependency),
                    user: User = Depends(get_current_user)) -> dict:
    meta = await run_in_threadpool(services.catalog.get, resource_id)
    if meta is None:
        raise HTTPException(404, "Resource not found")
    q = f"Summarize the key points of {meta.title}"
    result = await run_in_threadpool(chat_service.build_answer, services, q,
                                     top_k=8, filters={"resource_id": resource_id})
    return {"resource_id": resource_id, "summary": result["answer"],
            "citations": result["citations"], "confidence": result["confidence"]}


@router.post("/resource/{resource_id}/summarize/stream")
async def summarize_stream(resource_id: str, services: AlaServices = Depends(services_dependency),
                           user: User = Depends(get_current_user)):
    """Streaming summary (SSE) — the summary is LLM-generated and can take tens of
    seconds; streaming keeps the connection alive (no proxy timeout / socket reset)."""
    meta = await run_in_threadpool(services.catalog.get, resource_id)
    if meta is None:
        raise HTTPException(404, "Resource not found")
    q = f"Summarize the key points of {meta.title}"

    async def event_gen():
        sync_gen = chat_service.stream_answer(services, q, top_k=8,
                                              filters={"resource_id": resource_id})
        sentinel = object()
        while True:
            item = await run_in_threadpool(lambda: next(sync_gen, sentinel))
            if item is sentinel:
                break
            yield {"event": "message", "data": json.dumps(item, default=str)}
        yield {"event": "done", "data": json.dumps({"resource_id": resource_id})}

    return EventSourceResponse(event_gen())


@router.get("/resource/{resource_id}/related")
async def related_concepts(resource_id: str, services: AlaServices = Depends(services_dependency),
                           user: User = Depends(get_current_user)) -> dict:
    def _related():
        from ala.graph.models import EdgeType
        g = services.graph
        rnode = f"resource:{resource_id}"
        concepts = [nb for nb, _e, _d in g.neighbors(rnode) if nb.startswith("concept:")]
        out = []
        for cid in concepts[:12]:
            node = g.node(cid)
            related = [g.node(nb).label for nb, et, _d in
                       g.neighbors(cid, edge_types={EdgeType.RELATED_TO.value})
                       if g.node(nb)][:5]
            out.append({"concept_id": cid, "concept": node.label if node else cid,
                        "related": related})
        return out
    return {"resource_id": resource_id, "concepts": await run_in_threadpool(_related)}


@router.post("/resource/{resource_id}/quiz")
async def resource_quiz(resource_id: str, services: AlaServices = Depends(services_dependency),
                        user: User = Depends(get_current_user)) -> dict:
    def _quiz():
        g = services.graph
        rnode = f"resource:{resource_id}"
        concept = next((nb for nb, _e, _d in g.neighbors(rnode) if nb.startswith("concept:")), None)
        if concept is None:
            return ("no_concept", None)
        r = services.functions.dispatch("quiz", {"concept": concept, "student_id": user.student_id})
        if not r.ok:
            return ("failed", getattr(r, "error", "quiz function returned no result"))
        return ("ok", r.result)

    try:
        status, payload = await run_in_threadpool(_quiz)
    except Exception as exc:                                  # never reset the socket — 503 + log
        log.exception("quiz generation crashed for resource %s", resource_id)
        raise HTTPException(503, f"Quiz generation failed: {exc}") from exc
    if status == "no_concept":
        raise HTTPException(422, "No concept available to quiz on for this resource")
    if status == "failed":
        log.error("quiz function failed for resource %s: %s", resource_id, payload)
        raise HTTPException(503, f"Quiz generation failed: {payload}")
    return payload


@router.get("/resource/{resource_id}/citations")
async def resource_citations(resource_id: str, services: AlaServices = Depends(services_dependency),
                             user: User = Depends(get_current_user)) -> dict:
    meta = await run_in_threadpool(services.catalog.get, resource_id)
    if meta is None:
        raise HTTPException(404, "Resource not found")
    # Citations come from retrieval — no LLM generation (was a wasted 30 s+ generation).
    citations = await run_in_threadpool(chat_service.citations_only, services,
                                        f"key points of {meta.title}", top_k=6,
                                        filters={"resource_id": resource_id})
    return {"resource_id": resource_id, "citations": citations}
