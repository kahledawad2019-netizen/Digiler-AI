"""Concept graph — data for the interactive concept-network visualization."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/stats")
async def stats(services: AlaServices = Depends(services_dependency),
                user: User = Depends(get_current_user)) -> dict:
    return await run_in_threadpool(services.graph.statistics)


@router.get("/concept/{concept_id}")
async def concept_neighbourhood(concept_id: str, services: AlaServices = Depends(services_dependency),
                                user: User = Depends(get_current_user)) -> dict:
    def _run():
        cid = concept_id if concept_id.startswith("concept:") else f"concept:{concept_id}"
        g = services.graph
        node = g.node(cid)
        if node is None:
            return {"nodes": [], "edges": []}
        nodes = {cid: {"id": cid, "label": node.label, "type": "concept"}}
        edges = []
        for nb, etype, data in g.neighbors(cid):
            nb_node = g.node(nb)
            nodes.setdefault(nb, {"id": nb, "label": nb_node.label if nb_node else nb,
                                  "type": nb_node.type if nb_node else "concept"})
            edges.append({"source": cid, "target": nb, "type": etype,
                          "weight": data.get("weight", 1.0)})
        return {"nodes": list(nodes.values()), "edges": edges}
    return await run_in_threadpool(_run)
