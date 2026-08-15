"""Stage 10 report — build + persist the concept graph, stats + figures."""

from __future__ import annotations

import json
from pathlib import Path

from ala.config.settings import Settings
from ala.graph import viz
from ala.graph.builder import GraphBuilder
from ala.graph.graph import ConceptGraph
from ala.graph.store import GraphStore


def build_and_persist(settings: Settings) -> tuple[ConceptGraph, Path]:
    cfg = settings.graph or {}
    builder = GraphBuilder(
        settings,
        min_concept_resources=cfg.get("min_concept_resources", 2),
        max_concepts_per_course=cfg.get("max_concepts_per_course", 60),
    )
    graph = builder.build()
    store = GraphStore(settings.abspath(cfg.get("location", "data/graph/concept_graph.db")))
    store.save(graph)
    return graph, store.db_path


def run_report(settings: Settings, *, out_dir: str | Path | None = None) -> Path:
    graph, db_path = build_and_persist(settings)
    stats = graph.statistics()

    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage10_graph")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    viz.statistics_figure(stats, figs / "graph_statistics.png")
    viz.concept_network_figure(graph, figs / "concept_network.png")
    viz.prerequisite_figure(graph, figs / "prerequisite_chains.png")

    (out / "statistics.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "README.md").write_text(_markdown(stats, db_path), encoding="utf-8")
    return out


def _markdown(stats: dict, db_path: Path) -> str:
    top = "\n".join(f"| {t['label'][:40]} | {t['type']} | {t['degree']} |"
                    for t in stats["top_degree_nodes"])
    return "\n".join([
        "# Stage 10 — Concept Graph: Statistics & Visualizations",
        "",
        f"Persisted to `{db_path}` (SQLite). NetworkX in-memory for algorithms.",
        "",
        "## Statistics",
        "",
        f"- **Nodes:** {stats['nodes']} — {stats['by_node_type']}",
        f"- **Edges:** {stats['edges']} — {stats['by_edge_type']}",
        f"- **Density:** {stats['density']} · **Avg degree:** {stats['avg_degree']} · "
        f"**Weakly-connected components:** {stats['weakly_connected_components']}",
        "",
        "### Top-degree nodes",
        "",
        "| node | type | degree |",
        "|---|---|---|",
        top,
        "",
        "## Figures",
        "- ![statistics](figures/graph_statistics.png)",
        "- ![concept network](figures/concept_network.png)",
        "- ![prerequisite chains](figures/prerequisite_chains.png)",
        "",
    ])
