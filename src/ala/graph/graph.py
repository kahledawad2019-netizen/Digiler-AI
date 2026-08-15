"""ConceptGraph — NetworkX-backed typed multigraph with provenance + statistics."""

from __future__ import annotations

from collections import Counter

import networkx as nx

from ala.graph.models import EdgeType, GraphEdge, GraphNode, NodeType


class ConceptGraph:
    def __init__(self) -> None:
        self.g = nx.MultiDiGraph()

    # -- mutation --------------------------------------------------------- #
    def add_node(self, node: GraphNode) -> None:
        if self.g.has_node(node.id):
            data = self.g.nodes[node.id]
            data.setdefault("attrs", {}).update(node.attrs)
            if node.label and not data.get("label"):
                data["label"] = node.label
        else:
            self.g.add_node(node.id, type=node.type, label=node.label, attrs=dict(node.attrs))

    def add_edge(self, edge: GraphEdge) -> None:
        for n in (edge.source, edge.target):
            if not self.g.has_node(n):
                self.g.add_node(n, type=NodeType.CONCEPT.value, label=n, attrs={})
        if self.g.has_edge(edge.source, edge.target, key=edge.type):
            d = self.g[edge.source][edge.target][edge.type]
            d["weight"] += edge.weight
            for p in edge.provenance:
                if p not in d["provenance"]:
                    d["provenance"].append(p)
        else:
            self.g.add_edge(edge.source, edge.target, key=edge.type, type=edge.type,
                            weight=edge.weight, provenance=list(edge.provenance),
                            confidence=edge.confidence)

    # -- access ----------------------------------------------------------- #
    def has_node(self, node_id: str) -> bool:
        return self.g.has_node(node_id)

    def node(self, node_id: str) -> GraphNode | None:
        if not self.g.has_node(node_id):
            return None
        d = self.g.nodes[node_id]
        return GraphNode(node_id, d.get("type", ""), d.get("label", node_id), d.get("attrs", {}))

    def nodes(self, node_type: str | None = None) -> list[str]:
        if node_type is None:
            return list(self.g.nodes)
        return [n for n, d in self.g.nodes(data=True) if d.get("type") == node_type]

    def neighbors(self, node_id: str, *, edge_types: set[str] | None = None,
                  direction: str = "both") -> list[tuple[str, str, dict]]:
        """Return (neighbor_id, edge_type, edge_data) tuples."""
        out: list[tuple[str, str, dict]] = []
        if direction in ("out", "both"):
            for _, tgt, key, data in self.g.out_edges(node_id, keys=True, data=True):
                if edge_types is None or key in edge_types:
                    out.append((tgt, key, data))
        if direction in ("in", "both"):
            for src, _, key, data in self.g.in_edges(node_id, keys=True, data=True):
                if edge_types is None or key in edge_types:
                    out.append((src, key, data))
        return out

    # -- statistics ------------------------------------------------------- #
    def statistics(self) -> dict:
        g = self.g
        n, m = g.number_of_nodes(), g.number_of_edges()
        by_node = Counter(d.get("type") for _, d in g.nodes(data=True))
        by_edge = Counter(k for _, _, k in g.edges(keys=True))
        degrees = [d for _, d in g.degree()]
        top = sorted(g.degree(), key=lambda kv: kv[1], reverse=True)[:10]
        return {
            "nodes": n,
            "edges": m,
            "by_node_type": dict(by_node),
            "by_edge_type": dict(by_edge),
            "density": round(nx.density(g), 6) if n > 1 else 0.0,
            "avg_degree": round(sum(degrees) / n, 3) if n else 0.0,
            "weakly_connected_components": nx.number_weakly_connected_components(g) if n else 0,
            "top_degree_nodes": [{"id": nid, "label": g.nodes[nid].get("label", nid),
                                  "type": g.nodes[nid].get("type"), "degree": deg}
                                 for nid, deg in top],
        }

    def concept_subgraph(self) -> nx.MultiDiGraph:
        concept_ids = set(self.nodes(NodeType.CONCEPT.value))
        return self.g.subgraph(concept_ids).copy()

    def iter_nodes(self):
        for nid, d in self.g.nodes(data=True):
            yield GraphNode(nid, d.get("type", ""), d.get("label", nid), d.get("attrs", {}))

    def iter_edges(self):
        for s, t, k, d in self.g.edges(keys=True, data=True):
            yield GraphEdge(s, t, k, d.get("weight", 1.0), d.get("provenance", []),
                            d.get("confidence", 1.0))
