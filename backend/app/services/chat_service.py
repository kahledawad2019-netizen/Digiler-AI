"""Chat orchestration — reuses GraphRAG + Ollama streaming + the confidence gate.

Non-streaming answers come straight from ``GraphRAGService.answer_with_context``
(which already selects Ollama or the extractive generator). Streaming reuses the
GraphRAG pipeline's merger/context/prompt builders, then streams tokens from the
Ollama provider. Web search is never triggered automatically — the confidence gate
(the existing ``ConfidenceEstimator``) only sets ``needs_web``.
"""

from __future__ import annotations

from typing import Iterator

from app.deps.services import AlaServices


def _citations(services: AlaServices, package) -> list[dict]:
    try:
        idx = services.citation_index(package)
    except Exception:
        return []
    return [{"cid": n.cid, "label": n.label, "source_type": n.source_type, "locator": n.locator,
             "page": n.page, "slide": n.slide, "timestamp": n.timestamp, "link": n.link,
             "resolvable": n.resolvable} for n in idx.nodes]


def _evidence(package, k: int = 6) -> list[dict]:
    return [{"rank": it.rank, "resource_id": it.resource_id, "citation": it.citation,
             "source_type": it.source_type, "page": it.page, "timestamp": it.timestamp,
             "confidence": it.confidence, "text": (it.text or "")[:400]}
            for it in package.items[:k]]


def retrieve_package(services: AlaServices, question: str, *, top_k: int = 8,
                     filters: dict | None = None):
    """Retrieval ONLY — the evidence package without running the LLM generator.

    Use this for endpoints that need retrieved evidence/citations but NOT a written
    answer (search, citation explorer). Calling ``answer_with_context`` there forced a
    full (20–40 s) LLM generation whose text was then discarded — the root cause of the
    endpoint-timeout class of bugs.
    """
    pkg, _gres = services.graphrag.pipeline.merger.merge(question, top_k=top_k, filters=filters)
    return pkg


def citations_only(services: AlaServices, question: str, *, top_k: int = 8,
                   filters: dict | None = None) -> list[dict]:
    """Resolved citations for a query — retrieval only, no generation."""
    return _citations(services, retrieve_package(services, question, top_k=top_k, filters=filters))


def build_answer(services: AlaServices, question: str, *, top_k: int = 8,
                 concept: str | None = None, filters: dict | None = None) -> dict:
    """Full grounded answer (sources, confidence, evidence, reasoning) — no web."""
    ans, ctx, pkg = services.graphrag.answer_with_context(question, top_k=top_k, filters=filters)
    conf = services.research.confidence.estimate(pkg, ctx, ans)
    return {
        "answer": ans.answer,
        "confidence": conf.score,
        "grounding": (ans.grounding or {}).get("grounding_ratio"),
        "generator": ans.generator,
        "citations": _citations(services, pkg),
        "evidence": _evidence(pkg),
        "reasoning": ans.reasoning_trace,
        "used_web": False,
        "needs_web": conf.needs_research,
    }


def stream_answer(services: AlaServices, question: str, *, top_k: int = 8,
                  filters: dict | None = None) -> Iterator[dict]:
    """Yield SSE events: {'type':'token','text':…} … then {'type':'final', …}."""
    from ala.llm.factory import available_provider

    pipeline = services.graphrag.pipeline
    pkg, gres = pipeline.merger.merge(question, top_k=top_k, filters=filters)
    ctx = pipeline.context_builder.build(pkg, trace=["web + KB evidence"])
    prompt = pipeline.prompt_builder.build(ctx)
    provider = available_provider(services.settings)

    full = ""
    used_llm = False
    if provider is not None:
        # "/no_think" disables Qwen3's reasoning phase → the first token arrives in a few
        # seconds instead of ~30 s, so streaming answers feel responsive (no "empty box").
        messages = [{"role": "system", "content": "You are Digiler AI. Answer ONLY from the "
                     "numbered evidence and cite every claim with its [C#]/[K#] tag."},
                    {"role": "user", "content": "/no_think\n" + prompt}]
        try:
            for token in provider.stream(messages):
                full += token
                yield {"type": "token", "text": token}
            used_llm = bool(full.strip())
        except Exception:                                     # server/model error mid-stream
            full = ""
    if not full.strip():
        # provider absent, or the stream errored / produced nothing → grounded fallback
        full = pipeline.generator.answer(ctx, prompt)
        yield {"type": "token", "text": full}

    grounding = pipeline.citations.check_grounding(full, set(ctx.citations))
    from ala.rag.models import GraphRAGAnswer
    ans = GraphRAGAnswer(question=question, answer=full, grounding=grounding,
                         reasoning_trace=ctx.reasoning_trace, confidence=ctx.overall_confidence)
    conf = services.research.confidence.estimate(pkg, ctx, ans)
    yield {"type": "final", "confidence": conf.score, "needs_web": conf.needs_research,
           "grounding": grounding.get("grounding_ratio"),
           "generator": (getattr(provider, "name", "llm") if used_llm else "extractive-grounded"),
           "citations": _citations(services, pkg), "evidence": _evidence(pkg),
           "reasoning": ctx.reasoning_trace}
