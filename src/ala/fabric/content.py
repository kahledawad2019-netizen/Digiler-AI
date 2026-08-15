"""Unified content blocks and citation anchors.

A ``ContentBlock`` is the atomic, source-agnostic unit of meaning — a paragraph,
a slide, a notebook cell, a transcript window. Every downstream capability reads
blocks, not file formats:

    * Parent-Child chunking groups blocks into parents, splits into children.
    * Hybrid RAG embeds block text (dense) and indexes it (BM25).
    * Graph RAG mines concepts from blocks and links via ``section_path``.
    * Citations render the block's typed ``Anchor`` ([p.14] / [slide 7] / [12:34]).
    * Verifier reads per-block ``meta`` (ocr_confidence / asr_source) for caveats.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ala.core.enums import Language, _StrEnum

_Strict = ConfigDict(extra="forbid", use_enum_values=True)


class BlockType(_StrEnum):
    """What a block *is*, independent of the source format."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    CODE = "code"
    EQUATION = "equation"
    QUOTE = "quote"
    IMAGE_CAPTION = "image_caption"   # OCR/VLM text lifted from an image
    SLIDE = "slide"                   # a whole slide's text (lecture_slides)
    NOTEBOOK_CELL = "notebook_cell"   # a markdown/code cell
    TRANSCRIPT_SEGMENT = "transcript_segment"  # a video window
    OTHER = "other"


class Anchor(BaseModel):
    """A typed pointer back into the original source, for citations.

    Exactly which fields are set depends on the source: PDFs use ``page``, slide
    decks ``slide``, notebooks ``cell``, videos ``t_start``/``t_end``. ``char_*``
    is a universal fallback offset into the extracted text.
    """

    model_config = _Strict

    page: int | None = None
    slide: int | None = None
    cell: int | None = None
    t_start: float | None = None    # seconds
    t_end: float | None = None
    char_start: int | None = None
    char_end: int | None = None

    def render(self) -> str:
        """A short human-readable citation fragment, e.g. 'p.14' or '12:34'."""
        if self.slide is not None:
            return f"slide {self.slide}"
        if self.page is not None:
            return f"p.{self.page}"
        if self.cell is not None:
            return f"cell {self.cell}"
        if self.t_start is not None:
            m, s = divmod(int(self.t_start), 60)
            return f"{m}:{s:02d}"
        if self.char_start is not None:
            return f"@{self.char_start}"
        return ""


class ContentBlock(BaseModel):
    """One unit of resource content with its position, type, and anchor."""

    model_config = _Strict

    block_id: str                     # stable within a resource, e.g. "<rid>#b0007"
    order: int                        # 0-based position in reading order
    type: BlockType = BlockType.PARAGRAPH
    text: str = ""
    language: Language | None = None  # per-block (supports code-switched resources)
    anchor: Anchor = Field(default_factory=Anchor)
    section_path: list[str] = Field(default_factory=list)  # heading breadcrumb
    meta: dict = Field(default_factory=dict)  # ocr_confidence, asr_source, etc.

    def is_empty(self) -> bool:
        return not self.text.strip()
