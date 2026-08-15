"""Concept-graph visualizations (presentation-quality PNGs)."""

from __future__ import annotations

from pathlib import Path


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def statistics_figure(stats: dict, path: Path) -> Path:
    plt = _plt()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    nt = stats["by_node_type"]
    a1.bar(list(nt.keys()), list(nt.values()), color="#4C72B0")
    a1.set_title(f"Nodes by type (total {stats['nodes']})")
    a1.tick_params(axis="x", labelrotation=20)
    et = stats["by_edge_type"]
    a2.bar(list(et.keys()), list(et.values()), color="#55A868")
    a2.set_title(f"Edges by type (total {stats['edges']})")
    a2.tick_params(axis="x", labelrotation=30)
    fig.suptitle(f"Concept graph — density {stats['density']}, "
                 f"avg degree {stats['avg_degree']}, "
                 f"{stats['weakly_connected_components']} components")
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return Path(path)


def concept_network_figure(graph, path: Path, max_nodes: int = 60) -> Path:
    """Render the top concepts and their related_to relationships."""
    plt = _plt()
    import networkx as nx
    from ala.graph.models import EdgeType, NodeType

    sub = graph.concept_subgraph()
    # keep only related_to edges, top concepts by degree
    rel = nx.MultiDiGraph()
    for s, t, k, d in sub.edges(keys=True, data=True):
        if k == EdgeType.RELATED_TO.value:
            rel.add_edge(s, t, weight=d.get("weight", 1.0))
    if rel.number_of_nodes() == 0:
        for n in list(graph.nodes(NodeType.CONCEPT.value))[:max_nodes]:
            rel.add_node(n)
    top = sorted(rel.degree(), key=lambda kv: kv[1], reverse=True)[:max_nodes]
    keep = [n for n, _ in top]
    H = rel.subgraph(keep).copy()

    labels = {n: graph.g.nodes[n].get("label", n)[:22] for n in H.nodes}
    degrees = dict(H.degree())
    sizes = [200 + 120 * degrees.get(n, 0) for n in H.nodes]

    fig, ax = plt.subplots(figsize=(14, 10))
    pos = nx.spring_layout(H, seed=1, k=0.6)
    nx.draw_networkx_edges(H, pos, ax=ax, alpha=0.25, edge_color="#888")
    nx.draw_networkx_nodes(H, pos, ax=ax, node_size=sizes, node_color="#55A868", alpha=0.85)
    nx.draw_networkx_labels(H, pos, labels=labels, ax=ax, font_size=8)
    ax.set_title(f"Concept network — top {len(H.nodes)} concepts by related_to degree")
    ax.axis("off")
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return Path(path)


def prerequisite_figure(graph, path: Path) -> Path:
    """Module prerequisite chains per course (learning-path view)."""
    plt = _plt()
    import networkx as nx
    from ala.graph.models import EdgeType, NodeType

    modules = set(graph.nodes(NodeType.MODULE.value))
    P = nx.DiGraph()
    for s, t, k, d in graph.g.edges(keys=True, data=True):
        if k == EdgeType.PREREQUISITE.value and s in modules and t in modules:
            P.add_edge(s, t)
    if P.number_of_nodes() == 0:
        P.add_node("(no prerequisite chains)")
    labels = {n: n.split(":")[-1] for n in P.nodes}
    fig, ax = plt.subplots(figsize=(14, 8))
    try:
        pos = nx.multipartite_layout(P, subset_key=lambda n: n.split("/")[0]) \
            if P.number_of_edges() else nx.spring_layout(P, seed=1)
    except Exception:
        pos = nx.spring_layout(P, seed=1)
    nx.draw_networkx_edges(P, pos, ax=ax, arrows=True, alpha=0.5, edge_color="#C44E52")
    nx.draw_networkx_nodes(P, pos, ax=ax, node_size=500, node_color="#8172B3", alpha=0.85)
    nx.draw_networkx_labels(P, pos, labels=labels, ax=ax, font_size=7)
    ax.set_title("Module prerequisite chains (learning path)")
    ax.axis("off")
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return Path(path)
