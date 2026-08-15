"""Unified search — Knowledge Base resources + concepts + evidence."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User
from app.services import chat_service

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(q: str = Query(..., min_length=2), limit: int = 8,
                 services: AlaServices = Depends(services_dependency),
                 user: User = Depends(get_current_user)) -> dict:
    def _run():
        from ala.graph.models import NodeType
        from ala.metadata.schema import ResourceMetadata
        low = q.lower()
        # resources
        metas = [ResourceMetadata.from_dict(json.loads(r["metadata_json"]))
                 for r in services.catalog.list_all(record_status="active")]
        resources = [{"resource_id": m.resource_id, "title": m.title, "course": m.course,
                      "doc_type": str(m.doc_type)}
                     for m in metas if low in (m.title + " " + " ".join(m.topics)).lower()][:limit]
        # concepts (graph alias match)
        concepts = []
        for cid in services.graph.nodes(NodeType.CONCEPT.value):
            node = services.graph.node(cid)
            names = {a.lower() for a in node.attrs.get("aliases", [])} | {node.label.lower()}
            if any(low in n for n in names):
                concepts.append({"concept_id": cid, "concept": node.label})
            if len(concepts) >= limit:
                break
        # evidence (grounded chunks) — retrieval only, NO LLM generation
        pkg = chat_service.retrieve_package(services, q, top_k=limit)
        evidence = [{"resource_id": it.resource_id, "citation": it.citation,
                     "text": (it.text or "")[:200]} for it in pkg.items[:limit]]
        return {"resources": resources, "concepts": concepts, "evidence": evidence}
    return await run_in_threadpool(_run)
