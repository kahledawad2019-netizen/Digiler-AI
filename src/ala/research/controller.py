"""ResearchModeController — orchestrate the confidence-gated research flow.

    question → GraphRAG(KB) → confidence → high? answer
                                        → low?  web search → score/rank sources
                                                → parse → merge with KB evidence
                                                → GraphRAG answer → ask to save
                                                → approved? incremental ingest

Reuses the GraphRAG pipeline's own context/prompt/generator/citations (no
regeneration logic duplicated) and the existing ingestion pipeline for growth.
"""

from __future__ import annotations

import time

from ala.rag.models import GraphRAGAnswer
from ala.rag.pipeline import GraphRAGService
from ala.research.confidence import ConfidenceEstimator
from ala.research.ingest import IncrementalIngestor
from ala.research.merge import ResearchEvidenceMerger
from ala.research.models import ResearchConfig, ResearchResult
from ala.research.parser import WebDocumentParser
from ala.research.search import WebSearchAdapter
from ala.research.session import ResearchSessionLog
from ala.research.sources import SourceQualityEvaluator


class ResearchModeController:
    def __init__(self, settings, graphrag: GraphRAGService, *, search: WebSearchAdapter,
                 evaluator: SourceQualityEvaluator | None = None,
                 parser: WebDocumentParser | None = None,
                 merger: ResearchEvidenceMerger | None = None,
                 confidence: ConfidenceEstimator | None = None,
                 session: ResearchSessionLog | None = None,
                 ingestor: IncrementalIngestor | None = None,
                 config: ResearchConfig | None = None) -> None:
        self.settings = settings
        self.graphrag = graphrag
        self.config = config or ResearchConfig.from_settings(settings)
        self.search = search
        self.evaluator = evaluator or SourceQualityEvaluator(self.config)
        self.parser = parser or WebDocumentParser(self.config)
        self.merger = merger or ResearchEvidenceMerger(self.config)
        self.confidence = confidence or ConfidenceEstimator(self.config)
        self.session = session or ResearchSessionLog.from_settings(settings)
        self._ingestor = ingestor

    # ------------------------------------------------------------------ #
    def research(self, question: str, *, approve=None, top_k: int = 8) -> ResearchResult:
        t0 = time.perf_counter()
        ans, ctx, pkg = self.graphrag.answer_with_context(question, top_k=top_k)
        conf = self.confidence.estimate(pkg, ctx, ans)

        used_web = False
        sources: list[dict] = []
        ingested: list[str] = []
        web_ms = ingest_ms = 0.0

        if conf.needs_research and self.search.enabled:
            tw = time.perf_counter()
            scored = self.evaluator.select(self.search.search(question))
            web_docs = []
            for ss in scored:
                doc = self.parser.fetch(ss.result)
                if doc:
                    web_docs.append((ss, doc))
            web_ms = round((time.perf_counter() - tw) * 1000, 1)
            sources = [{"title": ss.result.title, "url": ss.result.url,
                        "domain": ss.result.domain, "provider": ss.result.provider,
                        "trust": ss.score.trust, "authority": ss.score.authority}
                       for ss in scored]

            if web_docs:
                ans, ctx = self._answer_over(self.merger.merge(pkg, web_docs, question))
                used_web = True
                approved = self.config.auto_approve or bool(approve and approve(question, sources))
                if approved:
                    ti = time.perf_counter()
                    ingested = self._ingest(web_docs)
                    ingest_ms = round((time.perf_counter() - ti) * 1000, 1)

        citations = [c.__dict__ for c in ans.citations]
        record = self.session.append({
            "question": question, "confidence": conf.score, "level": conf.level,
            "needs_research": conf.needs_research, "used_web": used_web,
            "provider": self.search.provider.name, "sources": sources,
            "approved": bool(ingested), "ingested": ingested,
            "stats": {"web_ms": web_ms, "ingest_ms": ingest_ms,
                      "total_ms": round((time.perf_counter() - t0) * 1000, 1)},
        })
        return ResearchResult(
            question=question, answer=ans.answer, confidence=conf, used_web=used_web,
            sources=sources, citations=citations, ingested=ingested,
            session_id=record["timestamp"],
            stats={"web_ms": web_ms, "ingest_ms": ingest_ms, "grounding": ans.grounding,
                   "generator": ans.generator})

    # ------------------------------------------------------------------ #
    def _answer_over(self, merged_pkg) -> tuple[GraphRAGAnswer, object]:
        """Regenerate an answer over a merged package, reusing the GraphRAG pieces."""
        p = self.graphrag.pipeline
        ctx = p.context_builder.build(merged_pkg, trace=["web + KB evidence merged"])
        text = p.generator.answer(ctx, p.prompt_builder.build(ctx))
        grounding = p.citations.check_grounding(text, set(ctx.citations))
        used = p.citations.used_citations(text, ctx.citations)
        ans = GraphRAGAnswer(question=merged_pkg.query, answer=text, citations=used,
                             reasoning_trace=ctx.reasoning_trace, confidence=ctx.overall_confidence,
                             grounding=grounding, generator=getattr(p.generator, "name", "llm"),
                             stats={"n_sources": len(ctx.chunks)})
        return ans, ctx

    def _ingest(self, web_docs) -> list[str]:
        from ala.core.enums import DocType, Role
        from ala.ingestion.context import ResourceClassification
        ingestor = self._ingestor or IncrementalIngestor.from_settings(self.settings)
        dest = self.settings.raw_path / self.config.research_track / self.config.research_course / "web"
        out: list[str] = []
        for _ss, doc in web_docs:
            path = self.parser.save(doc, dest)
            cls = ResourceClassification(
                track=self.config.research_track, course=self.config.research_course,
                module="web", title=doc.title, doc_type=DocType.WEB, role=Role.REFERENCE,
                subject=doc.domain)
            outcome = ingestor.ingest(path, cls)
            if outcome.ok:
                out.append(outcome.resource_id)
        return out

    @classmethod
    def from_settings(cls, settings, config: ResearchConfig | None = None) -> "ResearchModeController":
        cfg = config or ResearchConfig.from_settings(settings)
        return cls(settings, GraphRAGService(settings),
                   search=WebSearchAdapter.from_settings(settings, cfg), config=cfg)

    def close(self) -> None:
        self.graphrag.close()
