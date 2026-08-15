"""ConfidenceEstimator — does the Knowledge Base actually know this?

Combines real signals from one GraphRAG turn into a single [0,1] confidence and a
level. Low confidence is the gate that triggers web research. The discriminative
signals (semantic similarity, BM25 strength, evidence agreement, concept linking)
drop for out-of-corpus questions — validated in the Stage 14 benchmark, not tuned
to a target.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean

from ala.rag.models import GraphRAGAnswer, ReasoningContext
from ala.research.models import ConfidenceLevel, ConfidenceReport, ResearchConfig
from ala.retrieval.evidence.models import EvidencePackage


class ConfidenceEstimator:
    def __init__(self, config: ResearchConfig | None = None) -> None:
        self.config = config or ResearchConfig()

    def estimate(self, pkg: EvidencePackage, ctx: ReasoningContext | None = None,
                 answer: GraphRAGAnswer | None = None) -> ConfidenceReport:
        cfg = self.config
        items = pkg.items
        top = items[:5]

        semantic = max((it.semantic_similarity or 0.0 for it in top), default=0.0)
        top_bm25 = max((it.bm25_score or 0.0 for it in top), default=0.0)
        bm25 = min(1.0, top_bm25 / cfg.bm25_ref) if cfg.bm25_ref else 0.0

        res = [c.resource_id for c in (ctx.chunks if ctx else [])] or [it.resource_id for it in top]
        agreement = (Counter(res).most_common(1)[0][1] / len(res)) if res else 0.0

        graph = mean([g.confidence for g in pkg.graph_evidence[:5]]) if pkg.graph_evidence else 0.0
        citation = float(answer.grounding.get("grounding_ratio", 0.0)) if answer else 0.0
        n_support = len(ctx.chunks) if ctx else len(top)
        support = min(1.0, n_support / cfg.support_ref) if cfg.support_ref else 0.0

        signals = {"semantic": round(semantic, 4), "bm25": round(bm25, 4),
                   "agreement": round(agreement, 4), "graph": round(graph, 4),
                   "citation": round(citation, 4), "support": round(support, 4),
                   "n_supporting": n_support, "top_bm25_raw": round(top_bm25, 3)}

        w = cfg.weights
        wsum = sum(w.values()) or 1.0
        score = sum(w[k] * signals[k] for k in w) / wsum
        score = round(min(1.0, max(0.0, score)), 4)

        if score >= cfg.high_threshold:
            level = ConfidenceLevel.HIGH.value
        elif score >= cfg.low_threshold:
            level = ConfidenceLevel.MEDIUM.value
        else:
            level = ConfidenceLevel.LOW.value

        return ConfidenceReport(score=score, level=level,
                                needs_research=score < cfg.confidence_threshold, signals=signals)
