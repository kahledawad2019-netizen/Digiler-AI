"""GraphStore — persist/load the concept graph to SQLite (V3 §4.4: SQLite + NetworkX)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ala.graph.graph import ConceptGraph
from ala.graph.models import GraphEdge, GraphNode

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY, type TEXT, label TEXT, attrs_json TEXT
);
CREATE TABLE IF NOT EXISTS edges (
    source TEXT, target TEXT, type TEXT, weight REAL, provenance_json TEXT, confidence REAL,
    PRIMARY KEY (source, target, type)
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
"""


class GraphStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def save(self, graph: ConceptGraph) -> Path:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript(_SCHEMA)
            conn.execute("DELETE FROM nodes")
            conn.execute("DELETE FROM edges")
            conn.executemany(
                "INSERT INTO nodes(id,type,label,attrs_json) VALUES (?,?,?,?)",
                [(n.id, n.type, n.label, json.dumps(n.attrs, ensure_ascii=False))
                 for n in graph.iter_nodes()],
            )
            conn.executemany(
                "INSERT OR REPLACE INTO edges(source,target,type,weight,provenance_json,confidence) "
                "VALUES (?,?,?,?,?,?)",
                [(e.source, e.target, e.type, e.weight, json.dumps(e.provenance), e.confidence)
                 for e in graph.iter_edges()],
            )
            conn.commit()
        finally:
            conn.close()
        return self.db_path

    def load(self) -> ConceptGraph:
        graph = ConceptGraph()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            for r in conn.execute("SELECT * FROM nodes"):
                graph.add_node(GraphNode(r["id"], r["type"], r["label"],
                                         json.loads(r["attrs_json"] or "{}")))
            for r in conn.execute("SELECT * FROM edges"):
                graph.add_edge(GraphEdge(r["source"], r["target"], r["type"], r["weight"],
                                         json.loads(r["provenance_json"] or "[]"), r["confidence"]))
        finally:
            conn.close()
        return graph

    def exists(self) -> bool:
        return self.db_path.is_file()
