"""GraphContextBuilder — Evidence Package → structured ReasoningContext.

Applies duplicate removal, context budgeting (token-bounded), ordering (by
confidence) and compression (per-chunk truncation), then derives the graph
scaffolding the answer can reason over: concepts, relations, prerequisites,
neighbour concepts — each tied to a citation id. This object (and nothing else)
is what the prompt builder renders for the LLM.
"""

from __future__ import annotations

from ala.rag.citations import GraphCitationManager
from ala.rag.models import (ContextChunk, ContextConcept, ContextRelation,
                            GraphRAGConfig, ReasoningContext)
from ala.retrieval.evidence.models import EvidencePackage


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.3))


class GraphContextBuilder:
    def __init__(self, config: GraphRAGConfig | None = None,
                 citations: GraphCitationManager | None = None) -> None:
        self.config = config or GraphRAGConfig()
        self.citations = citations or GraphCitationManager()

    def build(self, pkg: EvidencePackage, *, trace: list[str] | None = None) -> ReasoningContext:
        cfg = self.config
        ctx = ReasoningContext(question=pkg.query, token_budget=cfg.token_budget,
                               overall_confidence=pkg.overall_confidence)
        cite_index: dict = {}

        # -- chunks: dedupe → budget → compress → cite ------------------- #
        seen_keys: set = set()
        used = 0
        n = 0
        for it in sorted(pkg.items, key=lambda x: x.confidence, reverse=True):
            if it.confidence < cfg.min_confidence or not (it.text or "").strip():
                continue
            key = self._dedupe_key(it)
            if key in seen_keys:
                continue
            text = self._truncate(it.text, cfg.max_chunk_tokens)
            toks = estimate_tokens(text)
            if used + toks > cfg.token_budget and ctx.chunks:
                break
            seen_keys.add(key)
            n += 1
            rec = self.citations.chunk_citation(it, n)
            cite_index[rec.cid] = rec
            ctx.chunks.append(ContextChunk(
                cid=rec.cid, text=text, citation=it.citation, resource_id=it.resource_id,
                source_type=it.source_type, confidence=it.confidence, tokens=toks))
            used += toks
            if len(ctx.chunks) >= cfg.context_chunks:
                break
        ctx.tokens_used = used

        # -- concepts / relations / prerequisites / neighbours ----------- #
        # keep top seeds but reserve slots for hop≥1 neighbours so the context
        # carries multi-hop relations to reason over (not just seed concepts).
        gev = pkg.graph_evidence
        hop0 = [e for e in gev if e.hop == 0]
        hopn = [e for e in gev if e.hop >= 1]
        reserve = min(len(hopn), max(0, cfg.context_concepts // 3))
        chosen = (hop0[: cfg.context_concepts - reserve] + hopn[:reserve])[: cfg.context_concepts]

        prereq_rel = {"prerequisite", "depends_on"}
        for i, ev in enumerate(chosen, start=1):
            rec = self.citations.concept_citation(ev, i)
            cite_index[rec.cid] = rec
            ctx.concepts.append(ContextConcept(
                cid=rec.cid, concept=ev.concept, hop=ev.hop, relationship=ev.relationship,
                path=ev.path, confidence=ev.confidence))
            if len(ev.path) >= 2:
                ctx.relations.append(ContextRelation(ev.path[-2], ev.relationship, ev.path[-1]))
            if ev.relationship in prereq_rel and ev.concept not in ctx.prerequisites:
                ctx.prerequisites.append(ev.concept)
            if ev.hop == 1 and ev.concept not in ctx.neighbor_concepts:
                ctx.neighbor_concepts.append(ev.concept)

        ctx.relations = _dedupe_relations(ctx.relations)
        ctx.citations = cite_index
        ctx.reasoning_trace = trace or []
        return ctx

    # ------------------------------------------------------------------ #
    def _dedupe_key(self, item) -> str:
        if self.config.dedupe_by == "resource_heading":
            return f"{item.resource_id}::{item.heading or ''}"
        if self.config.dedupe_by == "resource":
            return item.resource_id
        return item.chunk_id

    @staticmethod
    def _truncate(text: str, max_tokens: int) -> str:
        words = text.split()
        limit = int(max_tokens / 1.3)
        if len(words) <= limit:
            return text.strip()
        return " ".join(words[:limit]).strip() + " …"


def _dedupe_relations(rels: list[ContextRelation]) -> list[ContextRelation]:
    out, seen = [], set()
    for r in rels:
        key = (r.source, r.relationship, r.target)
        if r.source != r.target and key not in seen:
            seen.add(key)
            out.append(r)
    return out
