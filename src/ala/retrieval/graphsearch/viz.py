"""Stage 11 — presentation-quality figures, all from real benchmark outputs.

render_all() writes every figure the graduation deck needs: ranking comparison,
graph coverage, hop distribution, an example traversal / retrieved subgraph /
concept expansion, node & edge importance, evidence composition, traversal-depth
comparison, and latency.
"""

from __future__ import annotations

from pathlib import Path

_C = {"hybrid": "#4C72B0", "graph": "#55A868", "accent": "#DD8452",
      "seed": "#C44E52", "hop1": "#8172B3", "hop2": "#CCB974", "res": "#937860"}


def render_all(graph, payload: dict, example, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _ranking_comparison(plt, payload, figs)
    _graph_coverage(plt, payload["graph_metrics"], figs)
    _hop_distribution(plt, payload["graph_metrics"], figs)
    _depth_comparison(plt, payload["depth_ablation"], figs)
    _latency(plt, payload, figs)
    _node_importance(plt, graph, figs)
    _edge_importance(plt, graph, figs)
    _evidence_composition(plt, example, figs)
    _traversal_example(plt, graph, example, figs)
    _retrieved_graph(plt, example, figs)
    _concept_expansion(plt, example, figs)


# --------------------------------------------------------------------------- #
def _bar_grouped(plt, title, metrics, hybrid, graph, path):
    import numpy as np
    x = np.arange(len(metrics))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - 0.2, hybrid, 0.4, label="Hybrid", color=_C["hybrid"])
    ax.bar(x + 0.2, graph, 0.4, label="Graph", color=_C["graph"])
    ax.set_xticks(x); ax.set_xticklabels(metrics)
    ax.set_title(title); ax.set_ylabel("score"); ax.legend()
    ax.set_ylim(0, max([*hybrid, *graph, 0.01]) * 1.25)
    for i, (h, g) in enumerate(zip(hybrid, graph)):
        ax.text(i - 0.2, h, f"{h:.3f}", ha="center", va="bottom", fontsize=8)
        ax.text(i + 0.2, g, f"{g:.3f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def _ranking_comparison(plt, payload, figs):
    rp = {r["retriever"]: r for r in payload["related_passage"]}
    cols = ["Hit@1", "Hit@5", "MRR", "nDCG@10"]
    _bar_grouped(plt, "Hybrid vs Graph — related-passage (semantic) retrieval", cols,
                 [rp["hybrid"][c] for c in cols], [rp["graph"][c] for c in cols],
                 figs / "ranking_comparison.png")


def _graph_coverage(plt, gm, figs):
    labels = ["concept-link\ncoverage", "graph\nrecall", "node\ncoverage",
              "edge\ncoverage", "concept\ncoverage", "graph-evid.\n→gold"]
    vals = [gm["concept_link_coverage"], gm["graph_recall"], gm["node_coverage"],
            gm["edge_coverage"], gm["concept_coverage"], gm["graph_evidence_gold_rate"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(labels, vals, color=_C["graph"])
    ax.set_ylim(0, 1.0); ax.set_title("Graph-retrieval coverage & recall (real corpus)")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout(); fig.savefig(figs / "graph_coverage.png", dpi=130); plt.close(fig)


def _hop_distribution(plt, gm, figs):
    hd = gm["hop_distribution"] or {"0": 0}
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar([f"{k}-hop" for k in hd], list(hd.values()),
           color=[_C["seed"], _C["hop1"], _C["hop2"]][:len(hd)] or _C["graph"])
    ax.set_title("Hop at which the gold resource is reached")
    ax.set_ylabel("queries")
    for i, v in enumerate(hd.values()):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "hop_distribution.png", dpi=130); plt.close(fig)


def _depth_comparison(plt, ablation, figs):
    hops = [row["hops"] for row in ablation]
    fig, ax = plt.subplots(figsize=(8, 5))
    for metric, color in (("Hit@1", _C["hybrid"]), ("MRR", _C["graph"]), ("nDCG@10", _C["accent"])):
        ax.plot(hops, [row[metric] for row in ablation], "o-", label=metric, color=color)
    ax.set_xticks(hops); ax.set_xlabel("traversal depth (hops)")
    ax.set_title("Traversal-depth ablation (related-passage)"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "traversal_depth_comparison.png", dpi=130); plt.close(fig)


def _latency(plt, payload, figs):
    ki = {r["retriever"]: r for r in payload["known_item"]}
    fig, ax = plt.subplots(figsize=(6, 5))
    names = ["Hybrid", "Graph"]
    vals = [ki["hybrid"]["latency_ms"], ki["graph"]["latency_ms"]]
    ax.bar(names, vals, color=[_C["hybrid"], _C["graph"]])
    ax.set_title("Mean query latency"); ax.set_ylabel("ms / query")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.1f}", ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "latency.png", dpi=130); plt.close(fig)


def _node_importance(plt, graph, figs):
    from ala.graph.models import EdgeType, NodeType
    deg: dict[str, int] = {}
    for cid in graph.nodes(NodeType.CONCEPT.value):
        deg[cid] = len(graph.neighbors(cid, edge_types={EdgeType.RELATED_TO.value}))
    top = sorted(deg.items(), key=lambda kv: kv[1], reverse=True)[:12]
    labels = [(graph.node(c).label if graph.node(c) else c)[:26] for c, _ in top][::-1]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(labels, [d for _, d in top][::-1], color=_C["hybrid"])
    ax.set_title("Node importance — concept degree (related_to)")
    ax.set_xlabel("connected concepts")
    fig.tight_layout(); fig.savefig(figs / "node_importance.png", dpi=130); plt.close(fig)


def _edge_importance(plt, graph, figs):
    from ala.graph.models import EdgeType
    seen: set = set()
    edges = []
    for s, t, k, d in graph.g.edges(keys=True, data=True):
        if k != EdgeType.RELATED_TO.value:
            continue
        key = tuple(sorted((s, t)))
        if key in seen:
            continue
        seen.add(key)
        a = graph.node(s).label if graph.node(s) else s
        b = graph.node(t).label if graph.node(t) else t
        edges.append((f"{a[:16]} — {b[:16]}", d.get("weight", 1.0)))
    edges.sort(key=lambda kv: kv[1], reverse=True)
    edges = edges[:12]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh([e for e, _ in edges][::-1], [w for _, w in edges][::-1], color=_C["accent"])
    ax.set_title("Edge importance — strongest related_to (co-occurrence weight)")
    ax.set_xlabel("weight")
    fig.tight_layout(); fig.savefig(figs / "edge_importance.png", dpi=130); plt.close(fig)


def _evidence_composition(plt, example, figs):
    import numpy as np
    chunks = example.chunks[:6]
    if not chunks:
        return
    labels = [f"#{r.rank}\n{(r.payload.get('resource_id') or '')[-14:]}" for r in chunks]
    comps = ["bm25", "dense", "graph"]
    colors = [_C["hybrid"], _C["accent"], _C["graph"]]
    # components live on very different scales (BM25 ~20, dense/graph 0-1); scale
    # each to its max across the shown chunks so the *relative* mix is legible.
    raw = {c: np.array([float(r.component_scores.get(c, 0.0)) for r in chunks]) for c in comps}
    norm = {c: (v / v.max() if v.max() else v) for c, v in raw.items()}
    bottom = np.zeros(len(chunks))
    fig, ax = plt.subplots(figsize=(10, 5))
    for comp, col in zip(comps, colors):
        ax.bar(labels, norm[comp], bottom=bottom, label=comp, color=col)
        bottom += norm[comp]
    ax.set_title(f'Evidence composition — "{example.query}" (per-signal contribution, scaled)')
    ax.set_ylabel("normalised component score"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "evidence_composition.png", dpi=130); plt.close(fig)


def _expanded_subgraph(graph, example, limit=30):
    """Real subgraph induced on the top-scored expanded concepts (+ their edges)."""
    import networkx as nx
    from ala.retrieval.graphsearch.config import CONCEPT_EDGE_TYPES
    top = sorted(example.expanded.values(), key=lambda e: e.score, reverse=True)[:limit]
    ids = [e.concept_id for e in top]
    idset = set(ids)
    h = nx.Graph()
    for cid in ids:
        h.add_node(cid)
    for cid in ids:
        for nb, etype, _ in graph.neighbors(cid, edge_types=CONCEPT_EDGE_TYPES):
            if nb in idset and cid != nb:
                h.add_edge(cid, nb)
    return h


def _traversal_example(plt, graph, example, figs):
    import networkx as nx
    if not example.expanded:
        return
    h = _expanded_subgraph(graph, example)
    pos = nx.spring_layout(h, seed=1, k=0.9)
    hop = {c: e.hop for c, e in example.expanded.items()}
    palette = {0: _C["seed"], 1: _C["hop1"], 2: _C["hop2"]}
    colors = [palette.get(hop.get(n, 2), _C["res"]) for n in h.nodes()]
    sizes = [700 if hop.get(n) == 0 else 380 for n in h.nodes()]
    labels = {n: (graph.node(n).label if graph.node(n) else n)[:18] for n in h.nodes()}
    fig, ax = plt.subplots(figsize=(12, 8))
    nx.draw_networkx_edges(h, pos, ax=ax, alpha=0.3, edge_color="#888")
    nx.draw_networkx_nodes(h, pos, ax=ax, node_color=colors, node_size=sizes, alpha=0.92)
    nx.draw_networkx_labels(h, pos, labels, ax=ax, font_size=8)
    import matplotlib.patches as mp
    ax.legend(handles=[mp.Patch(color=_C["seed"], label="seed (hop 0)"),
                       mp.Patch(color=_C["hop1"], label="hop 1"),
                       mp.Patch(color=_C["hop2"], label="hop 2")], loc="lower left")
    ax.set_title(f'Graph traversal — "{example.query}"'); ax.axis("off")
    fig.tight_layout(); fig.savefig(figs / "traversal_example.png", dpi=130); plt.close(fig)


def _retrieved_graph(plt, example, figs):
    import networkx as nx
    gev = example.graph_evidence[:6]
    if not gev:
        return
    h = nx.Graph()
    node_color, node_size, labels = [], [], {}
    for g in gev:
        h.add_node(g.concept_id); labels[g.concept_id] = g.concept[:18]
        node_color.append(_C["seed"] if g.hop == 0 else _C["hop1"]); node_size.append(600)
        for rid in g.source_resources[:3]:
            rn = f"res:{rid}"
            if rn not in labels:
                h.add_node(rn); labels[rn] = rid[-16:]
                node_color.append(_C["res"]); node_size.append(240)
            h.add_edge(g.concept_id, rn)
    pos = nx.spring_layout(h, seed=3, k=1.1)
    fig, ax = plt.subplots(figsize=(12, 8))
    nx.draw_networkx_edges(h, pos, ax=ax, alpha=0.3, edge_color="#999")
    nx.draw_networkx_nodes(h, pos, ax=ax, node_color=node_color, node_size=node_size, alpha=0.9)
    nx.draw_networkx_labels(h, pos, labels, ax=ax, font_size=7)
    import matplotlib.patches as mp
    ax.legend(handles=[mp.Patch(color=_C["seed"], label="concept"),
                       mp.Patch(color=_C["res"], label="resource (provenance)")], loc="lower left")
    ax.set_title(f'Retrieved graph — "{example.query}" (concepts → source resources)')
    ax.axis("off")
    fig.tight_layout(); fig.savefig(figs / "retrieved_graph.png", dpi=130); plt.close(fig)


def _concept_expansion(plt, example, figs):
    """Seed → expanded concept paths as a directed tree."""
    import networkx as nx
    exp = sorted(example.expanded.values(), key=lambda e: e.score, reverse=True)[:14]
    if not exp:
        return
    h = nx.DiGraph()
    labels, colors = {}, {}
    for e in exp:
        for a, b in zip(e.path, e.path[1:]):
            h.add_edge(a, b)
        h.add_node(e.concept_id)
        labels[e.concept_id] = e.label[:16]
        colors[e.concept_id] = _C["seed"] if e.hop == 0 else (_C["hop1"] if e.hop == 1 else _C["hop2"])
    for n in h.nodes():
        labels.setdefault(n, n.replace("concept:", "")[:16]); colors.setdefault(n, _C["hop2"])
    try:
        pos = nx.nx_agraph.graphviz_layout(h, prog="dot")
    except Exception:
        pos = nx.spring_layout(h, seed=7, k=1.0)
    fig, ax = plt.subplots(figsize=(12, 7))
    nx.draw_networkx_edges(h, pos, ax=ax, alpha=0.4, edge_color="#888",
                           arrows=True, arrowsize=12)
    nx.draw_networkx_nodes(h, pos, ax=ax, node_color=[colors[n] for n in h.nodes()],
                           node_size=520, alpha=0.9)
    nx.draw_networkx_labels(h, pos, labels, ax=ax, font_size=8)
    ax.set_title(f'Concept expansion paths — "{example.query}"'); ax.axis("off")
    fig.tight_layout(); fig.savefig(figs / "concept_expansion.png", dpi=130); plt.close(fig)
