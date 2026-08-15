"""Stage 3 — Chunk as a first-class object, with metadata separate from text.

``ChunkMetadata`` carries everything retrieval/graph/RL need; ``Chunk`` bundles
metadata + text for in-memory convenience, but the ``ChunkStore`` persists the
two separately (metadata index vs. text store) so the metadata can be scanned,
filtered, and evolved without loading megabytes of text.

Reserved fields (``embedding_*``, ``graph_node_ids``, ``scores``) are present now
so later stages fill them rather than migrate the schema — the same
future-proofing principle used for ResourceMetadata.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ala.core.enums import _StrEnum

_Strict = ConfigDict(extra="forbid", use_enum_values=True)


class ChunkKind(_StrEnum):
    PARENT = "parent"      # context unit (returned to the LLM)
    CHILD = "child"        # match unit (embedded / searched)


class ChunkType(_StrEnum):
    """The dominant structural nature of a chunk (drives display + weighting)."""

    SECTION = "section"
    PARAGRAPH = "paragraph"
    SLIDE = "slide"
    TABLE = "table"
    CODE = "code"
    NOTEBOOK_CELL = "notebook_cell"
    TRANSCRIPT = "transcript"
    MIXED = "mixed"
    OTHER = "other"


class RetrievalScores(BaseModel):
    """Reserved score slots filled by Stages 5/7 (None until then)."""

    model_config = _Strict
    dense: float | None = None
    bm25: float | None = None
    graph: float | None = None
    rrf: float | None = None
    rerank: float | None = None


class ChunkMetadata(BaseModel):
    """All metadata about one chunk. Stored separately from the chunk text."""

    model_config = _Strict

    # identity & hierarchy
    chunk_id: str
    parent_id: str | None = None          # None for parent chunks
    resource_id: str
    kind: ChunkKind
    order: int                            # position within the resource
    child_ids: list[str] = Field(default_factory=list)   # parents list their children
    source_block_ids: list[str] = Field(default_factory=list)

    # content descriptors
    language: str = "en"
    token_count: int = 0
    chunk_type: ChunkType = ChunkType.OTHER

    # citation anchors (every child inherits these from its structural parent)
    section_path: list[str] = Field(default_factory=list)
    heading: str | None = None
    page: int | None = None
    page_end: int | None = None
    slide: int | None = None
    timestamp: float | None = None        # video t_start (seconds)

    # pedagogical enrichment (inherited from the resource; refined later)
    topics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)

    # reserved for later stages (future-proofing; no migration needed)
    embedding_version: str | None = None      # Stage 4
    embedding_model: str | None = None        # Stage 4
    embedding_dim: int | None = None          # Stage 4
    graph_node_ids: list[str] = Field(default_factory=list)   # Stage 6
    scores: RetrievalScores = Field(default_factory=RetrievalScores)  # Stage 5/7

    def citation(self) -> str:
        """Human-readable citation fragment for this chunk."""
        loc = ""
        if self.slide is not None:
            loc = f"slide {self.slide}"
        elif self.timestamp is not None:
            m, s = divmod(int(self.timestamp), 60)
            loc = f"{m}:{s:02d}"
        elif self.page is not None:
            loc = f"p.{self.page}" + (f"-{self.page_end}" if self.page_end and self.page_end != self.page else "")
        head = self.heading or (self.section_path[-1] if self.section_path else "")
        return f"[{self.resource_id}" + (f", {loc}" if loc else "") + (f", {head}" if head else "") + "]"


class Chunk(BaseModel):
    """Metadata + text. The store persists the two halves separately."""

    model_config = _Strict
    metadata: ChunkMetadata
    text: str

    @property
    def chunk_id(self) -> str:
        return self.metadata.chunk_id


class ChunkSet(BaseModel):
    """The parents and children produced from one resource."""

    model_config = _Strict
    resource_id: str
    parents: list[Chunk] = Field(default_factory=list)
    children: list[Chunk] = Field(default_factory=list)

    @property
    def parent_ids(self) -> list[str]:
        return [c.chunk_id for c in self.parents]

    @property
    def child_ids(self) -> list[str]:
        return [c.chunk_id for c in self.children]

    def child_map(self) -> dict[str, Chunk]:
        return {c.chunk_id: c for c in self.children}
