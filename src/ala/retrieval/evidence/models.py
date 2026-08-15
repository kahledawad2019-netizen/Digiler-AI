"""Evidence data model — every field the LLM needs to answer with citations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ala.core.clock import utcnow_iso
from ala.core.enums import _StrEnum

_Model = ConfigDict(extra="forbid")


class SourceType(_StrEnum):
    PDF = "pdf"
    SLIDE = "slide"
    VIDEO = "video"
    WEB = "web"
    NOTEBOOK = "notebook"
    DOCUMENT = "document"


class EvidenceItem(BaseModel):
    """One cited piece of evidence."""

    model_config = _Model

    rank: int
    chunk_id: str
    parent_chunk: str | None = None
    text: str

    # scores
    retrieval_score: float                 # == fused_score (the ranking score)
    dense_score: float | None = None
    bm25_score: float | None = None
    fused_score: float = 0.0
    semantic_similarity: float | None = None   # dense cosine (0..1)
    confidence: float = 0.0                # calibrated [0,1]
    retrieval_reason: str = ""             # explanation of why this was selected

    # provenance / citation
    source_type: str = SourceType.DOCUMENT.value
    resource_id: str = ""
    document_title: str | None = None
    heading: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page: int | None = None
    page_end: int | None = None
    slide: int | None = None
    timestamp: float | None = None         # video seconds
    language: str | None = None
    citation: str = ""
    metadata: dict = Field(default_factory=dict)


class GraphEvidenceItem(BaseModel):
    """A concept reached by graph expansion — the 'why' behind graph-sourced chunks."""

    model_config = _Model
    concept_id: str
    concept: str
    score: float
    hop: int
    relationship: str                              # edge type that reached it
    path: list[str] = Field(default_factory=list)  # concept labels along the path
    source_resources: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class EvidencePackage(BaseModel):
    """The complete object handed to the generator (never raw retrieval output)."""

    model_config = _Model

    query: str
    normalized_query: str
    retriever: str = "hybrid"
    items: list[EvidenceItem] = Field(default_factory=list)
    graph_evidence: list[GraphEvidenceItem] = Field(default_factory=list)   # Stage 11+
    overall_confidence: float = 0.0
    created_at: str = Field(default_factory=utcnow_iso)
    stats: dict = Field(default_factory=dict)

    # -- convenience ------------------------------------------------------ #
    def resource_ids(self) -> list[str]:
        seen: list[str] = []
        for it in self.items:
            if it.resource_id not in seen:
                seen.append(it.resource_id)
        return seen

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> "EvidencePackage":
        return cls.model_validate(data)
