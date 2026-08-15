"""GraphBuilder — construct the concept graph from the ingested corpus.

Deterministic (no LLM) construction (V3 §4.3 G1): structural hierarchy from the
catalog + taxonomy, high-precision concepts from the ConceptExtractor (curated
domain lexicon + embedding-aware multi-word mining), and typed relations
(appears_in / explains / related_to / prerequisite / depends_on / references /
extends) with provenance. Supports full build + ``build_from_metas`` (testable).
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict

import yaml

from ala.catalog.repository import KnowledgeCatalog
from ala.config.settings import Settings
from ala.core import ids
from ala.core.enums import RelationType
from ala.graph.concepts import ConceptExtractor
from ala.graph.graph import ConceptGraph
from ala.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from ala.metadata.schema import ResourceMetadata

log = logging.getLogger("ala.graph")
_WORD = re.compile(r"\w+", re.UNICODE)
_MAX_DOC_CHARS = 30000

_RELATION_EDGE = {
    RelationType.EXTENDS.value: EdgeType.EXTENDS.value,
    RelationType.DEPENDS_ON.value: EdgeType.DEPENDS_ON.value,
    RelationType.PART_OF.value: EdgeType.CONTAINS.value,
    RelationType.RELATED_TO.value: EdgeType.RELATED_TO.value,
    RelationType.SIMILAR_TO.value: EdgeType.RELATED_TO.value,
}


class GraphBuilder:
    def __init__(self, settings: Settings, embedder=None, *, min_concept_resources: int = 2) -> None:
        self.settings = settings
        self.embedder = embedder
        self.min_concept_resources = min_concept_resources
        self._course_titles = self._load_course_titles()
        self._lexicon = self._load_lexicon()

    # ------------------------------------------------------------------ #
    def build(self) -> ConceptGraph:
        metas = self._load_metas()
        return self.build_from_metas(metas, self._load_resource_docs(metas))

    def build_from_metas(self, metas: list[ResourceMetadata],
                         resource_docs: dict[str, str] | None = None) -> ConceptGraph:
        graph = ConceptGraph()
        if resource_docs is None:
            resource_docs = {m.resource_id: _fallback_doc(m) for m in metas}

        for meta in metas:
            self._structural(graph, meta)
        self._build_concepts(graph, metas, resource_docs)
        self._module_prerequisites(graph, metas)
        self._resource_relations(graph, metas)
        log.info("Built concept graph: %s", graph.statistics()["by_node_type"])
        return graph

    # ------------------------------------------------------------------ #
    def _structural(self, graph: ConceptGraph, meta: ResourceMetadata) -> None:
        course_id = f"course:{meta.course}"
        module_id = f"module:{meta.course}/{meta.module}"
        resource_id = f"resource:{meta.resource_id}"

        graph.add_node(GraphNode(course_id, NodeType.COURSE.value,
                                 self._course_titles.get(meta.course, meta.course),
                                 {"course": meta.course, "track": meta.track}))
        graph.add_node(GraphNode(module_id, NodeType.MODULE.value, meta.module or "misc",
                                 {"course": meta.course, "week": meta.week}))
        graph.add_node(GraphNode(resource_id, NodeType.RESOURCE.value, meta.title,
                                 {"resource_id": meta.resource_id, "doc_type": str(meta.doc_type),
                                  "role": str(meta.role), "language": str(meta.language),
                                  "course": meta.course, "module": meta.module}))
        graph.add_edge(GraphEdge(course_id, module_id, EdgeType.CONTAINS.value))
        graph.add_edge(GraphEdge(module_id, resource_id, EdgeType.CONTAINS.value))

        for topic in list(meta.topics) + list(meta.subtopics):
            tslug = ids.slugify(topic)
            if not tslug:
                continue
            tid = f"topic:{tslug}"
            graph.add_node(GraphNode(tid, NodeType.TOPIC.value, topic, {}))
            graph.add_edge(GraphEdge(resource_id, tid, EdgeType.CONTAINS.value,
                                     provenance=[meta.resource_id]))

    def _build_concepts(self, graph, metas, resource_docs) -> None:
        extractor = ConceptExtractor(self._lexicon, self.embedder)
        concepts = extractor.extract(resource_docs)

        title_tokens = {m.resource_id: set(_tokens(m.title)) for m in metas}
        topic_terms = {m.resource_id: {t.lower() for t in m.topics} for m in metas}

        for c in concepts:
            graph.add_node(GraphNode(c.concept_id, NodeType.CONCEPT.value, c.canonical, c.node_attrs()))
            canon_tokens = set(_tokens(c.canonical))
            for rid in c.source_resources:
                rnode = f"resource:{rid}"
                strong = bool(canon_tokens & title_tokens.get(rid, set())) or \
                    any(a in topic_terms.get(rid, set()) for a in c.aliases)
                graph.add_edge(GraphEdge(c.concept_id, rnode,
                                         EdgeType.APPEARS_IN.value if strong else EdgeType.MENTIONED_IN.value,
                                         provenance=[rid], confidence=c.confidence))
                if strong:
                    graph.add_edge(GraphEdge(rnode, c.concept_id, EdgeType.EXPLAINS.value,
                                             provenance=[rid]))

        # concept <-> concept related_to via co-occurrence
        by_resource: dict[str, list[str]] = defaultdict(list)
        for c in concepts:
            for rid in c.source_resources:
                by_resource[rid].append(c.concept_id)
        pair_weight: Counter = Counter()
        pair_prov: dict[tuple, list] = defaultdict(list)
        for rid, cids in by_resource.items():
            for i in range(len(cids)):
                for j in range(i + 1, len(cids)):
                    key = tuple(sorted((cids[i], cids[j])))
                    pair_weight[key] += 1
                    if len(pair_prov[key]) < 5:
                        pair_prov[key].append(rid)
        for (a, b), w in pair_weight.items():
            if w >= self.min_concept_resources:
                graph.add_edge(GraphEdge(a, b, EdgeType.RELATED_TO.value, weight=float(w),
                                         provenance=pair_prov[(a, b)]))

    def _module_prerequisites(self, graph, metas) -> None:
        by_course: dict[str, set[str]] = defaultdict(set)
        for meta in metas:
            by_course[meta.course].add(meta.module or "")
        for course, modules in by_course.items():
            weeks = sorted((m for m in modules if re.match(r"w\d+", m or "")),
                           key=lambda m: int(re.search(r"\d+", m).group()))
            for prev, cur in zip(weeks, weeks[1:]):
                a, b = f"module:{course}/{prev}", f"module:{course}/{cur}"
                graph.add_edge(GraphEdge(a, b, EdgeType.PREREQUISITE.value))
                graph.add_edge(GraphEdge(b, a, EdgeType.DEPENDS_ON.value))

    def _resource_relations(self, graph, metas) -> None:
        for meta in metas:
            for rel in meta.relationships:
                etype = _RELATION_EDGE.get(str(rel.type))
                if etype:
                    graph.add_edge(GraphEdge(f"resource:{meta.resource_id}",
                                             f"resource:{rel.target_resource_id}", etype,
                                             confidence=rel.confidence or 1.0))

    # ------------------------------------------------------------------ #
    def _load_metas(self) -> list[ResourceMetadata]:
        catalog = KnowledgeCatalog.from_settings(self.settings)
        try:
            rows = catalog.list_all(record_status="active")
            return [ResourceMetadata.from_dict(json.loads(r["metadata_json"])) for r in rows]
        finally:
            catalog.close()

    def _load_resource_docs(self, metas) -> dict[str, str]:
        from ala.retrieval.chunking.store import ChunkStore

        store = ChunkStore(self.settings.derived_path)
        docs: dict[str, str] = {}
        for m in metas:
            texts = store.load_text(m.resource_id, "child")
            joined = " ".join(texts.values())[:_MAX_DOC_CHARS]
            docs[m.resource_id] = joined if joined.strip() else _fallback_doc(m)
        return docs

    def _load_lexicon(self) -> list[dict]:
        path = self.settings.abspath(self.settings.paths.taxonomy_dir) / "concept_lexicon.yaml"
        if not path.is_file():
            return []
        return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("concepts", [])

    def _load_course_titles(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for track in (self.settings.tracks or {}).get("tracks", []):
            for course in track.get("courses", []):
                out[course["id"]] = course.get("title", course["id"])
        return out


# --------------------------------------------------------------------------- #
def _tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall((text or "").lower()) if len(t) >= 3]


def _fallback_doc(meta: ResourceMetadata) -> str:
    return " ".join([meta.title, *meta.pedagogy.keywords, *meta.topics, *meta.subtopics])
