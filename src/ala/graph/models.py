"""Concept-graph node/edge vocabulary + value types.

Requested node types map to these (V3 §4.2 — a scoped concept graph, not an
everything-graph): lessons/documents/videos → RESOURCE (distinguished by
doc_type), subtopics → TOPIC; definitions/examples/exercises/assignments are
captured via ``example_of`` edges + chunk role tags rather than separate node
types, to avoid node explosion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ala.core.enums import _StrEnum


class NodeType(_StrEnum):
    COURSE = "course"
    MODULE = "module"
    RESOURCE = "resource"
    TOPIC = "topic"
    CONCEPT = "concept"
    CHUNK = "chunk"


class EdgeType(_StrEnum):
    CONTAINS = "contains"          # hierarchy: course⊃module⊃resource⊃chunk, resource⊃topic
    APPEARS_IN = "appears_in"      # concept → resource (strong: title/topic)
    MENTIONED_IN = "mentioned_in"  # concept → resource/chunk (weaker: keyword)
    EXPLAINS = "explains"          # resource → concept (resource explains it)
    RELATED_TO = "related_to"      # concept ↔ concept / topic → concept (co-occurrence)
    PREREQUISITE = "prerequisite"  # concept → concept, module → module
    DEPENDS_ON = "depends_on"      # resource/module → its prerequisite
    EXAMPLE_OF = "example_of"      # example chunk/resource → concept
    REFERENCES = "references"      # resource → resource
    EXTENDS = "extends"            # resource → resource


@dataclass
class GraphNode:
    id: str
    type: str
    label: str
    attrs: dict = field(default_factory=dict)   # provenance + extras (resource_ids, course, …)


@dataclass
class GraphEdge:
    source: str
    target: str
    type: str
    weight: float = 1.0
    provenance: list[str] = field(default_factory=list)   # resource/chunk ids
    confidence: float = 1.0
