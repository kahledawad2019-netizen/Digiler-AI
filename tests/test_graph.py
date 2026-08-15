"""Stage 10 — concept graph tests."""

from __future__ import annotations

from ala.graph import (
    ConceptGraph,
    EdgeType,
    GraphBuilder,
    GraphEdge,
    GraphNode,
    GraphStore,
    NodeType,
)


def test_graph_add_dedupe_and_statistics():
    g = ConceptGraph()
    g.add_node(GraphNode("course:dmv", NodeType.COURSE.value, "Data Mining"))
    g.add_node(GraphNode("concept:fk", NodeType.CONCEPT.value, "Foreign Key"))
    g.add_edge(GraphEdge("course:dmv", "concept:fk", EdgeType.CONTAINS.value))
    g.add_edge(GraphEdge("course:dmv", "concept:fk", EdgeType.CONTAINS.value, weight=1.0))
    st = g.statistics()
    assert st["nodes"] == 2 and st["edges"] == 1        # deduped by (src,tgt,type)
    assert g.g["course:dmv"]["concept:fk"][EdgeType.CONTAINS.value]["weight"] == 2.0
    assert st["by_node_type"]["course"] == 1 and "density" in st


def test_store_roundtrip(tmp_path):
    g = ConceptGraph()
    g.add_node(GraphNode("concept:x", NodeType.CONCEPT.value, "X", {"seed": True}))
    g.add_node(GraphNode("resource:r", NodeType.RESOURCE.value, "R"))
    g.add_edge(GraphEdge("concept:x", "resource:r", EdgeType.APPEARS_IN.value,
                         weight=2.0, provenance=["r"]))
    GraphStore(tmp_path / "g.db").save(g)
    g2 = GraphStore(tmp_path / "g.db").load()
    assert g2.node("concept:x").attrs["seed"] is True
    nbrs = g2.neighbors("concept:x", direction="out")
    assert nbrs and nbrs[0][1] == EdgeType.APPEARS_IN.value and nbrs[0][2]["weight"] == 2.0
    assert g2.node("concept:x").attrs and "r" in nbrs[0][2]["provenance"]


def test_builder_from_metas(settings, make_meta):
    m1 = make_meta("technical.dmv.w03.constraints", course="dmv", module="w03",
                   title="Constraints and Foreign Key")
    m1.topics = ["constraints", "foreign key"]
    m1.pedagogy.keywords = ["foreign", "key", "constraint", "referential", "integrity"]
    m2 = make_meta("technical.dmv.w04.dml", course="dmv", module="w04", title="DML Basics")
    m2.topics = ["insert", "update"]
    m2.pedagogy.keywords = ["foreign", "key", "insert", "update", "delete"]

    g = GraphBuilder(settings).build_from_metas([m1, m2])

    # structural hierarchy
    assert g.has_node("course:dmv")
    assert g.has_node("module:dmv/w03")
    assert g.has_node("resource:technical.dmv.w03.constraints")
    contains = g.neighbors("module:dmv/w03", edge_types={EdgeType.CONTAINS.value}, direction="out")
    assert any(nb == "resource:technical.dmv.w03.constraints" for nb, _, _ in contains)

    # module prerequisite w03 -> w04
    prereq = g.neighbors("module:dmv/w03", edge_types={EdgeType.PREREQUISITE.value}, direction="out")
    assert any(nb == "module:dmv/w04" for nb, _, _ in prereq)

    # concepts mined + seed; a concept appears in / mentioned_in a resource
    concepts = g.nodes(NodeType.CONCEPT.value)
    assert concepts
    stats = g.statistics()
    assert stats["by_edge_type"].get("appears_in", 0) + stats["by_edge_type"].get("mentioned_in", 0) > 0
