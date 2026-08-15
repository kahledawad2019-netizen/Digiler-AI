"""GraphRAGPipeline — question → grounded, cited answer (V3 §5 generation layer).

    question → GraphEvidenceMerger → EvidencePackage
             → GraphContextBuilder → GraphPromptBuilder → generator
             → GraphCitationManager (grounding check) → GraphRAGAnswer

The generator only ever receives the structured prompt / context — never raw
retrieval output. Every answer is grounding-checked before it is returned.
"""

from __future__ import annotations

import time

from ala.rag.citations import GraphCitationManager
from ala.rag.context import GraphContextBuilder
from ala.rag.llm import ExtractiveGroundedGenerator
from ala.rag.merger import GraphEvidenceMerger
from ala.rag.models import GraphRAGAnswer, GraphRAGConfig, ReasoningContext
from ala.rag.prompt import GraphPromptBuilder
from ala.retrieval.evidence.models import EvidencePackage


class GraphRAGPipeline:
    def __init__(self, merger: GraphEvidenceMerger, context_builder: GraphContextBuilder,
                 prompt_builder: GraphPromptBuilder, generator=None,
                 citations: GraphCitationManager | None = None,
                 config: GraphRAGConfig | None = None) -> None:
        self.merger = merger
        self.context_builder = context_builder
        self.prompt_builder = prompt_builder
        self.generator = generator or ExtractiveGroundedGenerator()
        self.citations = citations or GraphCitationManager()
        self.config = config or GraphRAGConfig()

    def answer(self, question: str, *, top_k: int | None = None,
               filters: dict | None = None) -> GraphRAGAnswer:
        return self.answer_with_context(question, top_k=top_k, filters=filters)[0]

    def answer_with_context(self, question: str, *, top_k: int | None = None, filters: dict | None = None
                            ) -> tuple[GraphRAGAnswer, ReasoningContext, EvidencePackage]:
        t0 = time.perf_counter()
        pkg, gres = self.merger.merge(question, top_k=top_k, filters=filters)

        trace = [
            f"Retrieved {len(pkg.items)} candidate passages (hybrid + graph-aware ranking).",
            f"Linked the question to {gres.stats['seed_concepts']} seed concept(s); "
            f"expanded to {gres.stats['expanded_concepts']} concept(s) over "
            f"{gres.stats['max_hop']} hop(s).",
            f"Graph reached {gres.stats['graph_resources']} resource(s) through concept edges.",
        ]
        ctx = self.context_builder.build(pkg, trace=trace)
        ctx.reasoning_trace.append(
            f"Assembled a {ctx.tokens_used}-token grounded context: "
            f"{len(ctx.chunks)} source(s) + {len(ctx.concepts)} concept(s).")

        prompt = self.prompt_builder.build(ctx)
        text = self.generator.answer(ctx, prompt)

        grounding = self.citations.check_grounding(text, set(ctx.citations))
        used = self.citations.used_citations(text, ctx.citations)
        ans = GraphRAGAnswer(
            question=question, answer=text, citations=used,
            reasoning_trace=ctx.reasoning_trace, confidence=ctx.overall_confidence,
            grounding=grounding, generator=getattr(self.generator, "name", "llm"),
            stats={
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "context_tokens": ctx.tokens_used, "prompt_chars": len(prompt),
                "n_sources": len(ctx.chunks), "n_concepts": len(ctx.concepts),
                "n_relations": len(ctx.relations),
                "graph_latency_ms": gres.stats.get("latency_ms"),
            })
        return ans, ctx, pkg


class GraphRAGService:
    """Wire the whole GraphRAG pipeline from settings; owns Qdrant/SQLite handles."""

    def __init__(self, settings, config: GraphRAGConfig | None = None, generator=None) -> None:
        from ala.catalog.repository import KnowledgeCatalog
        from ala.retrieval.evidence.builder import EvidenceBuilder
        from ala.retrieval.graphsearch.factory import build_graph_retriever
        from ala.retrieval.search.textresolver import ChunkTextResolver

        self.settings = settings
        self.config = config or GraphRAGConfig.from_settings(settings)
        self._bundle = build_graph_retriever(settings)
        self.catalog = KnowledgeCatalog.from_settings(settings)
        builder = EvidenceBuilder(self._bundle.graph, ChunkTextResolver(settings),
                                  self.catalog, "graphrag")
        merger = GraphEvidenceMerger(self._bundle.graph, builder, self.config)
        self.pipeline = GraphRAGPipeline(
            merger, GraphContextBuilder(self.config), GraphPromptBuilder(),
            generator=generator or self._default_generator(settings), config=self.config)

    def _default_generator(self, settings):
        # Use the configured LLM provider (Ollama by default) when it is reachable;
        # otherwise fall back to the offline extractive-grounded generator.
        from ala.llm.factory import make_generator
        return make_generator(settings)

    def answer(self, question: str, *, top_k: int | None = None,
               filters: dict | None = None) -> GraphRAGAnswer:
        return self.pipeline.answer(question, top_k=top_k, filters=filters)

    def answer_with_context(self, question: str, *, top_k=None, filters=None):
        return self.pipeline.answer_with_context(question, top_k=top_k, filters=filters)

    def close(self) -> None:
        self._bundle.close()
        self.catalog.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
