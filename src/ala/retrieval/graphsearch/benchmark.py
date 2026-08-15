"""Stage 11 — Graph-retrieval benchmark on the **real corpus** (no mocks).

Reuses the label-free known-item eval set (Stage 8). Produces:

* ranking comparison — Hybrid vs Graph, known-item **and** related-passage;
* graph-specific metrics — concept-link coverage, graph recall (gold resource
  reached via concept expansion), node/edge/concept coverage, hop distribution,
  graph-evidence→gold rate, latency / throughput;
* a traversal-depth ablation (1/2/3 hops);
* an example traversal (real query) for the figures.

Everything is computed from actual retriever executions.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from ala.config.settings import Settings
from ala.retrieval.evaluation.evaluate import evaluate, results_markdown
from ala.retrieval.evaluation.evalset import build_known_item_evalset
from ala.retrieval.graphsearch.config import PROVENANCE_EDGE_TYPES
from ala.retrieval.graphsearch.factory import build_graph_retriever


def run_graph_benchmark(settings: Settings, *, n: int = 100, seed: int = 0,
                        example_query: str = "convolutional neural network",
                        out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage11_graph_retrieval")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    evalset, resource_chunks = build_known_item_evalset(settings, n=n, seed=seed)
    bundle = build_graph_retriever(settings)
    try:
        gr = bundle.graph
        hybrid = bundle.base.hybrid
        graph = gr.graph
        gstats = graph.statistics()
        total_concepts = gstats["by_node_type"].get("concept", 0)

        # warm up the local Qdrant index once (first query pays a one-time
        # ~50s cold build) so the timed passes report true steady-state latency.
        gr.retrieve("warmup", top_k=5)

        gr.config.max_hops = 2
        # 1. ranking comparison (known-item + related-passage)
        ki = [evaluate("hybrid", hybrid.retrieve, evalset, resource_chunks),
              evaluate("graph", gr.retrieve, evalset, resource_chunks)]
        rp = [evaluate("hybrid", hybrid.retrieve, evalset, resource_chunks, exclude_gold_chunk=True),
              evaluate("graph", gr.retrieve, evalset, resource_chunks, exclude_gold_chunk=True)]

        # 2. graph-specific metrics (single pass over retrieve_with_graph)
        gm = _graph_metrics(gr, graph, evalset, total_concepts, gstats)

        # 3. traversal-depth ablation (related-passage)
        ablation = []
        for h in (1, 2, 3):
            gr.config.max_hops = h
            r = evaluate(f"graph@{h}hop", gr.retrieve, evalset, resource_chunks, exclude_gold_chunk=True)
            ablation.append({"hops": h, **r.to_row()})
        gr.config.max_hops = 2

        # 4. example traversal for the figures
        example = gr.retrieve_with_graph(example_query, top_k=8)

        payload = {
            "corpus": {"nodes": gstats["nodes"], "edges": gstats["edges"],
                       "concepts": total_concepts, "n_queries": len(evalset)},
            "known_item": [r.to_row() for r in ki],
            "related_passage": [r.to_row() for r in rp],
            "graph_metrics": gm,
            "depth_ablation": ablation,
            "example": _example_payload(example),
        }
        (out / "graph_retrieval.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        from ala.retrieval.graphsearch import viz
        viz.render_all(graph, payload, example, figs)

        (out / "GRAPH_RETRIEVAL.md").write_text(
            _markdown(payload, ki, rp), encoding="utf-8")
        return out
    finally:
        bundle.close()


def _graph_metrics(gr, graph, evalset, total_concepts, gstats) -> dict:
    touched_nodes: set[str] = set()
    touched_edges: set[tuple] = set()
    touched_concepts: set[str] = set()
    linked = recall_hits = 0
    hop_hist: Counter = Counter()
    n_seed: list[int] = []
    n_expanded: list[int] = []
    latencies: list[float] = []
    gev_gold_rate: list[float] = []

    for q in evalset:
        res = gr.retrieve_with_graph(q.query, top_k=10)
        n_seed.append(res.stats["seed_concepts"])
        n_expanded.append(res.stats["expanded_concepts"])
        latencies.append(res.stats["latency_ms"])
        if res.seed_concepts:
            linked += 1
        touched_concepts |= set(res.expanded.keys())
        reached: dict[str, int] = {}
        for cid, ec in res.expanded.items():
            touched_nodes.add(cid)
            for nb, etype, _ in graph.neighbors(cid, edge_types=PROVENANCE_EDGE_TYPES):
                if nb.startswith("resource:"):
                    rid = nb[len("resource:"):]
                    reached[rid] = min(reached.get(rid, 99), ec.hop)
                    touched_nodes.add(nb)
                    touched_edges.add((cid, nb, etype))
        if q.gold_resource_id in reached:
            recall_hits += 1
            hop_hist[reached[q.gold_resource_id]] += 1
        if res.graph_evidence:
            hit = sum(1 for g in res.graph_evidence if q.gold_resource_id in g.source_resources)
            gev_gold_rate.append(hit / len(res.graph_evidence))

    n = max(1, len(evalset))
    mean_lat = sum(latencies) / len(latencies) if latencies else 0.0
    return {
        "concept_link_coverage": round(linked / n, 3),
        "graph_recall": round(recall_hits / n, 3),
        "avg_seed_concepts": round(sum(n_seed) / n, 2),
        "avg_expanded_concepts": round(sum(n_expanded) / n, 2),
        "node_coverage": round(len(touched_nodes) / max(1, gstats["nodes"]), 3),
        "edge_coverage": round(len(touched_edges) / max(1, gstats["edges"]), 3),
        "concept_coverage": round(len(touched_concepts) / max(1, total_concepts), 3),
        "hop_distribution": {str(k): v for k, v in sorted(hop_hist.items())},
        "graph_evidence_gold_rate": round(sum(gev_gold_rate) / len(gev_gold_rate), 3) if gev_gold_rate else 0.0,
        "mean_latency_ms": round(mean_lat, 2),
        "throughput_qps": round(1000.0 / mean_lat, 1) if mean_lat else 0.0,
    }


def _example_payload(example) -> dict:
    return {
        "query": example.query,
        "seed_concepts": [{"id": c, "score": round(s, 3)} for c, s in example.seed_concepts.items()],
        "expanded": [{"concept": e.label, "hop": e.hop, "relationship": e.relationship,
                      "score": round(e.score, 3), "path": e.path}
                     for e in sorted(example.expanded.values(), key=lambda e: e.score, reverse=True)[:12]],
        "graph_evidence": [g.model_dump(mode="json") for g in example.graph_evidence[:8]],
        "top_chunks": [{"rank": r.rank, "resource_id": r.payload.get("resource_id"),
                        "score": round(r.score, 4), "components": r.component_scores}
                       for r in example.chunks[:6]],
        "stats": example.stats,
    }


def _markdown(p: dict, ki, rp) -> str:
    gm = p["graph_metrics"]
    abl_cols = ["hops", "Hit@1", "Hit@5", "MRR", "nDCG@10", "latency_ms"]
    abl = "\n".join("| " + " | ".join(str(row[c]) for c in abl_cols) + " |"
                    for row in p["depth_ablation"])
    ex = p["example"]
    ex_exp = "\n".join(
        f"| {e['concept']} | {e['hop']} | {e['relationship']} | {e['score']} |"
        for e in ex["expanded"][:8])
    return "\n".join([
        "# Stage 11 — Graph Retrieval: Benchmark",
        "",
        f"Real corpus: **{p['corpus']['nodes']} nodes / {p['corpus']['edges']} edges / "
        f"{p['corpus']['concepts']} concepts**; **{p['corpus']['n_queries']} queries**.",
        "",
        "## Ranking comparison — known-item (find the source resource)",
        "",
        results_markdown(ki),
        "",
        "## Ranking comparison — related-passage (semantic: find the *other* passages)",
        "",
        results_markdown(rp),
        "",
        "## Graph-specific metrics",
        "",
        "| metric | value |",
        "|---|---|",
        f"| concept-link coverage | {gm['concept_link_coverage']} |",
        f"| graph recall (gold reached via expansion) | {gm['graph_recall']} |",
        f"| avg seed concepts / query | {gm['avg_seed_concepts']} |",
        f"| avg expanded concepts / query | {gm['avg_expanded_concepts']} |",
        f"| node coverage | {gm['node_coverage']} |",
        f"| edge coverage | {gm['edge_coverage']} |",
        f"| concept coverage | {gm['concept_coverage']} |",
        f"| graph-evidence→gold rate | {gm['graph_evidence_gold_rate']} |",
        f"| mean latency (ms) | {gm['mean_latency_ms']} |",
        f"| throughput (qps) | {gm['throughput_qps']} |",
        f"| hop distribution | {gm['hop_distribution']} |",
        "",
        "## Traversal-depth ablation (related-passage)",
        "",
        "| " + " | ".join(abl_cols) + " |",
        "| " + " | ".join("---" for _ in abl_cols) + " |",
        abl,
        "",
        f"## Example traversal — \"{ex['query']}\"",
        "",
        f"Seed concepts: {', '.join(c['id'].replace('concept:', '') for c in ex['seed_concepts']) or '(none)'}.  "
        f"Expanded {ex['stats']['expanded_concepts']} concepts over {ex['stats']['max_hop']} hops "
        f"in {ex['stats']['latency_ms']} ms.",
        "",
        "| expanded concept | hop | relationship | score |",
        "|---|---|---|---|",
        ex_exp,
        "",
        "## Figures (`figures/`)",
        "- `ranking_comparison.png` · `graph_coverage.png` · `hop_distribution.png`",
        "- `traversal_example.png` · `retrieved_graph.png` · `concept_expansion.png`",
        "- `node_importance.png` · `edge_importance.png` · `evidence_composition.png`",
        "- `traversal_depth_comparison.png` · `latency.png`",
        "",
    ])
