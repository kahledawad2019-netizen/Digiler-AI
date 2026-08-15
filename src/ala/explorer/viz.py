"""Stage 15 — Citation Explorer figures, from real citation indexes."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

_C = {"chunk": "#4C72B0", "concept": "#8172B3", "web": "#DD8452", "green": "#55A868",
      "grey": "#937860", "red": "#C44E52"}


def render_all(payload: dict, example_index, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _distribution(plt, payload, figs)
    _accuracy(plt, payload, figs)
    _evidence_composition(plt, example_index, figs)
    _flow(plt, example_index, figs)


def _distribution(plt, p, figs):
    bt = p["by_source_type"]; bk = p["by_kind"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
    a1.bar(list(bt.keys()), list(bt.values()),
           color=[_C.get(k, _C["grey"]) for k in bt])
    a1.set_title("Citations by source type"); a1.set_ylabel("citations")
    for i, v in enumerate(bt.values()):
        a1.text(i, v, str(v), ha="center", va="bottom")
    a2.bar(list(bk.keys()), list(bk.values()), color=[_C.get(k, _C["grey"]) for k in bk])
    a2.set_title("Citations by kind")
    for i, v in enumerate(bk.values()):
        a2.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "citation_distribution.png", dpi=130); plt.close(fig)


def _accuracy(plt, p, figs):
    labels = ["resolvable\n(link works)", "locator coverage\n(page/slide/ts)", "mean\nconfidence"]
    vals = [p["resolvable_rate"], p["locator_coverage"], p["mean_confidence"]]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(labels, vals, color=[_C["green"], _C["chunk"], _C["concept"]])
    ax.set_ylim(0, 1.08); ax.set_title(f"Citation accuracy ({p['n_queries']} queries, real corpus)")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "citation_accuracy.png", dpi=130); plt.close(fig)


def _evidence_composition(plt, index, figs):
    by = Counter(n.kind for n in index.nodes)
    fig, ax = plt.subplots(figsize=(7, 5))
    order = ["chunk", "concept", "web"]
    vals = [by.get(k, 0) for k in order]
    ax.bar(order, vals, color=[_C[k] for k in order])
    ax.set_title(f'Evidence composition — "{index.query[:40]}"')
    ax.set_ylabel("citations")
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "evidence_composition.png", dpi=130); plt.close(fig)


def _flow(plt, index, figs):
    import networkx as nx
    nodes = index.nodes[:14]
    if not nodes:
        return
    g = nx.DiGraph()
    pos, colors, labels = {}, {}, {}
    for i, n in enumerate(nodes):                             # left column: citations
        g.add_node(n.cid); pos[n.cid] = (0, -i); colors[n.cid] = _C.get(n.kind, _C["grey"])
        labels[n.cid] = n.cid
        tgt = (n.resource_id or n.label)[:22] or n.cid        # right column: sources
        if tgt not in pos:
            g.add_node(tgt); pos[tgt] = (2, -list({m.resource_id or m.label for m in nodes}).index(
                n.resource_id or n.label)); colors[tgt] = _C["grey"]; labels[tgt] = tgt
        g.add_edge(n.cid, tgt)
    fig, ax = plt.subplots(figsize=(12, 8))
    nx.draw_networkx_edges(g, pos, ax=ax, alpha=0.4, edge_color="#999")
    nx.draw_networkx_nodes(g, pos, ax=ax, node_color=[colors[x] for x in g.nodes()],
                           node_size=[900 if x in {n.cid for n in nodes} else 500 for x in g.nodes()],
                           alpha=0.9)
    nx.draw_networkx_labels(g, pos, labels, ax=ax, font_size=7)
    ax.set_title(f'Citation flow — "{index.query[:44]}" (citations → sources)')
    ax.axis("off")
    fig.tight_layout(); fig.savefig(figs / "citation_flow.png", dpi=130); plt.close(fig)
