"""Stage 12 — GraphRAG benchmark on the **real corpus** (no mocks).

Runs the full pipeline over the label-free known-item eval questions and measures
grounding, citation validity, context precision/recall, graph coverage, multi-hop
reasoning presence, latency/throughput and context size. The cross-system
faithfulness comparison (Dense/BM25/Hybrid/Graph/GraphRAG) is Stage 13.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ala.config.settings import Settings
from ala.rag.pipeline import GraphRAGService
from ala.retrieval.evaluation.evalset import build_known_item_evalset


def run_graphrag_benchmark(settings: Settings, *, n: int = 60, seed: int = 0,
                           example_query: str = "what is a convolutional neural network",
                           out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage12_graphrag")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    evalset, _ = build_known_item_evalset(settings, n=n, seed=seed)
    svc = GraphRAGService(settings)
    try:
        svc.answer("warmup", top_k=5)                          # cold Qdrant index build

        grounding, ctx_prec, latencies, tokens = [], [], [], []
        n_concepts, n_relations = [], []
        valid = has_cite = recall_hits = has_concept = has_relation = 0
        src_types: Counter = Counter()

        for q in evalset:
            ans, ctx, _pkg = svc.answer_with_context(q.query)
            grounding.append(ans.grounding["grounding_ratio"])
            valid += int(ans.grounding["citation_valid"])
            has_cite += int(bool(ans.citations))
            ctx_res = [c.resource_id for c in ctx.chunks]
            if ctx_res:
                ctx_prec.append(sum(1 for r in ctx_res if r == q.gold_resource_id) / len(ctx_res))
            recall_hits += int(q.gold_resource_id in ctx_res)
            n_concepts.append(len(ctx.concepts)); has_concept += int(bool(ctx.concepts))
            n_relations.append(len(ctx.relations)); has_relation += int(bool(ctx.relations))
            latencies.append(ans.stats["latency_ms"]); tokens.append(ctx.tokens_used)
            for c in ans.citations:
                if c.kind == "chunk":
                    src_types[c.source_type] += 1

        m = max(1, len(evalset))
        mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0
        metrics = {
            "n_questions": len(evalset),
            "grounding_ratio": mean(grounding),
            "citation_validity": round(valid / m, 4),
            "answer_has_citation": round(has_cite / m, 4),
            "context_precision": mean(ctx_prec),
            "context_recall": round(recall_hits / m, 4),
            "graph_coverage": round(has_concept / m, 4),
            "avg_concepts_in_context": mean(n_concepts),
            "multi_hop_presence": round(has_relation / m, 4),
            "avg_relations_in_context": mean(n_relations),
            "avg_context_tokens": mean(tokens),
            "mean_latency_ms": mean(latencies),
            "throughput_qps": round(1000.0 / mean(latencies), 2) if latencies else 0.0,
            "citation_source_types": dict(src_types),
        }

        example = _example(svc, example_query)
        payload = {"metrics": metrics, "tokens": tokens, "example": example}
        (out / "graphrag.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                           encoding="utf-8")

        from ala.rag import viz
        viz.render_all(payload, figs)
        (out / "GRAPHRAG.md").write_text(_markdown(metrics, example), encoding="utf-8")
        return out
    finally:
        svc.close()


def _example(svc: GraphRAGService, query: str) -> dict:
    ans, ctx, _ = svc.answer_with_context(query, top_k=8)
    return {
        "question": ans.question, "answer": ans.answer, "generator": ans.generator,
        "confidence": ans.confidence, "grounding": ans.grounding,
        "reasoning_trace": ans.reasoning_trace, "stats": ans.stats,
        "citations": [c.__dict__ for c in ans.citations],
        "context": {
            "sources": [{"cid": c.cid, "resource_id": c.resource_id, "type": c.source_type,
                         "confidence": c.confidence, "tokens": c.tokens} for c in ctx.chunks],
            "concepts": [{"cid": c.cid, "concept": c.concept, "hop": c.hop,
                          "relationship": c.relationship} for c in ctx.concepts],
            "relations": [r.__dict__ for r in ctx.relations],
            "prerequisites": ctx.prerequisites,
        },
    }


def _markdown(m: dict, ex: dict) -> str:
    cites = "\n".join(f"| {c['cid']} | {c['label']} | {c.get('source_type','')} | {c['confidence']} |"
                      for c in ex["citations"])
    return "\n".join([
        "# Stage 12 — GraphRAG: Benchmark",
        "",
        f"Real corpus, **{m['n_questions']} questions**, offline extractive-grounded generator.",
        "",
        "## Metrics",
        "",
        "| metric | value |",
        "|---|---|",
        f"| grounding ratio | {m['grounding_ratio']} |",
        f"| citation validity | {m['citation_validity']} |",
        f"| answer has citation | {m['answer_has_citation']} |",
        f"| context precision | {m['context_precision']} |",
        f"| context recall | {m['context_recall']} |",
        f"| graph coverage (≥1 concept) | {m['graph_coverage']} |",
        f"| avg concepts / context | {m['avg_concepts_in_context']} |",
        f"| multi-hop presence (≥1 relation) | {m['multi_hop_presence']} |",
        f"| avg relations / context | {m['avg_relations_in_context']} |",
        f"| avg context tokens | {m['avg_context_tokens']} |",
        f"| mean latency (ms) | {m['mean_latency_ms']} |",
        f"| throughput (qps) | {m['throughput_qps']} |",
        f"| citation source types | {m['citation_source_types']} |",
        "",
        f"## Example — \"{ex['question']}\"",
        "",
        f"**Answer:** {ex['answer']}",
        "",
        f"grounding={ex['grounding']['grounding_ratio']} · valid={ex['grounding']['citation_valid']} "
        f"· confidence={ex['confidence']} · generator={ex['generator']}",
        "",
        "| citation | source | type | confidence |",
        "|---|---|---|---|",
        cites,
        "",
        "**Reasoning trace:**",
        *[f"- {s}" for s in ex["reasoning_trace"]],
        "",
        "## Figures (`figures/`)",
        "- `pipeline_diagram.png` · `grounding.png` · `context_composition.png`",
        "- `citation_sources.png` · `token_distribution.png` · `context_precision_recall.png`",
        "- `evidence_contribution.png` · `reasoning_flow.png`",
        "",
        "## Honest note",
        "The offline generator is **extractive-grounded** (selects + cites real passages), so "
        "grounding/citation-validity are ~1.0 by construction — this measures the *pipeline's* "
        "grounding guarantee, not an LLM's. Fluent NL synthesis + faithfulness under an actual "
        "LLM is evaluated at Stage 13 via the `OpenAICompatibleLLM` seam.",
        "",
    ])
