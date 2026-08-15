"""Stage 10.5 report — concept-extraction quality: before vs after + figures."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import networkx as nx

from ala.config.settings import Settings
from ala.graph.builder import GraphBuilder
from ala.graph.models import EdgeType, NodeType
from ala.graph.store import GraphStore

_GENERIC = {"data", "example", "model", "result", "information", "chapter", "learning",
            "introduction", "using", "find", "value", "number", "name", "set", "step",
            "table", "column", "first", "print", "create", "function", "random", "plt"}


def run_concept_report(settings: Settings, *, embedder_key: str | None = "e5-small",
                       out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage10_graph")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    before = None
    bpath = out / "statistics_before.json"
    if bpath.is_file():
        before = json.loads(bpath.read_text(encoding="utf-8"))

    embedder = None
    if embedder_key:
        from ala.retrieval.embedding.factory import get_embedder
        embedder = get_embedder(embedder_key)

    graph = GraphBuilder(settings, embedder=embedder).build()
    GraphStore(settings.abspath((settings.graph or {}).get("location", "data/graph/concept_graph.db"))).save(graph)

    concepts = [n for n in graph.iter_nodes() if n.type == NodeType.CONCEPT.value]
    after_count = len(concepts)
    before_count = (before or {}).get("by_node_type", {}).get("concept")

    by_freq = sorted(concepts, key=lambda c: c.attrs.get("frequency", 0), reverse=True)
    by_domain = Counter(c.attrs.get("domain", "?") for c in concepts)
    multiword = [c for c in concepts if len(c.label.split()) >= 2]
    mined = [c for c in concepts if not c.attrs.get("seed", True)]
    seed_present = [c for c in concepts if c.attrs.get("seed", True)]

    # largest connected concepts (by related_to degree)
    sub = graph.concept_subgraph()
    rel = nx.Graph()
    for s, t, k in sub.edges(keys=True):
        if k == EdgeType.RELATED_TO.value:
            rel.add_edge(s, t)
    largest = sorted(rel.degree(), key=lambda kv: kv[1], reverse=True)[:10] if rel.number_of_nodes() else []
    label = {c.id: c.label for c in concepts}

    removed_generic = sorted({t["label"].lower() for t in (before or {}).get("top_degree_nodes", [])
                              if t.get("type") == "concept"} & _GENERIC)

    payload = {
        "concepts_before": before_count, "concepts_after": after_count,
        "seed_concepts": len(seed_present), "mined_concepts": len(mined),
        "multiword_concepts": len(multiword),
        "by_domain": dict(by_domain.most_common()),
        "most_frequent": [{"concept": c.label, "domain": c.attrs.get("domain"),
                           "frequency": c.attrs.get("frequency"),
                           "n_resources": c.attrs.get("n_resources"),
                           "confidence": c.attrs.get("confidence")} for c in by_freq[:15]],
        "largest_connected": [{"concept": label.get(nid, nid), "related_degree": d} for nid, d in largest],
        "removed_generic_examples": removed_generic,
        "added_multiword_examples": [c.label for c in multiword[:20]],
    }
    (out / "concept_quality.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _charts(payload, by_freq, by_domain, multiword, mined, seed_present, figs)
    (out / "CONCEPT_QUALITY.md").write_text(_markdown(payload), encoding="utf-8")
    return out


def _charts(payload, by_freq, by_domain, multiword, mined, seed, figs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # before/after
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    if payload["concepts_before"] is not None:
        a1.bar(["before\n(generic)", "after\n(domain)"],
               [payload["concepts_before"], payload["concepts_after"]],
               color=["#C44E52", "#55A868"])
        a1.set_title("Concept count: before vs after cleaning")
        for i, v in enumerate([payload["concepts_before"], payload["concepts_after"]]):
            a1.text(i, v, str(v), ha="center", va="bottom")
    dom = payload["by_domain"]
    a2.barh(list(dom.keys())[::-1], list(dom.values())[::-1], color="#4C72B0")
    a2.set_title("Concepts by domain (after)")
    fig.tight_layout(); fig.savefig(figs / "concept_quality_overview.png", dpi=130); plt.close(fig)

    # top concepts by frequency
    top = by_freq[:15]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh([c.label[:34] for c in top][::-1], [c.attrs.get("frequency", 0) for c in top][::-1],
            color="#55A868")
    ax.set_title("Top concepts by corpus frequency (domain-specific, cleaned)")
    ax.set_xlabel("frequency")
    fig.tight_layout(); fig.savefig(figs / "top_concepts_frequency.png", dpi=130); plt.close(fig)

    # composition
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(["seed\n(lexicon)", "mined\n(multi-word)", "multi-word\ntotal"],
           [len(seed), len(mined), len(multiword)], color=["#8172B3", "#DD8452", "#55A868"])
    ax.set_title("Concept composition (after)")
    fig.tight_layout(); fig.savefig(figs / "concept_composition.png", dpi=130); plt.close(fig)


def _markdown(p: dict) -> str:
    freq = "\n".join(f"| {m['concept']} | {m['domain']} | {m['frequency']} | {m['n_resources']} |"
                     for m in p["most_frequent"])
    largest = "\n".join(f"| {c['concept']} | {c['related_degree']} |" for c in p["largest_connected"])
    return "\n".join([
        "# Stage 10.5 — Concept Extraction Quality Upgrade",
        "",
        f"**Concepts before cleaning:** {p['concepts_before']} (generic-heavy) → "
        f"**after:** {p['concepts_after']} "
        f"({p['seed_concepts']} lexicon-matched · {p['mined_concepts']} embedding-mined · "
        f"{p['multiword_concepts']} multi-word).",
        "",
        "## Removed generic concepts (examples)",
        ", ".join(p["removed_generic_examples"]) or "(none)",
        "",
        "## Added multi-word / domain concepts (examples)",
        ", ".join(p["added_multiword_examples"]),
        "",
        "## Most frequent concepts",
        "",
        "| concept | domain | frequency | resources |",
        "|---|---|---|---|",
        freq,
        "",
        "## Largest connected concepts (related_to degree)",
        "",
        "| concept | related degree |",
        "|---|---|",
        largest,
        "",
        "## Figures",
        "- ![overview](figures/concept_quality_overview.png)",
        "- ![top concepts](figures/top_concepts_frequency.png)",
        "- ![composition](figures/concept_composition.png)",
        "",
    ])
