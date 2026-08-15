"""Controlled vocabularies for resource metadata.

Every value a resource may take for a classification/status field lives here as
a ``str``-backed ``Enum``. Using enums (instead of free strings scattered through
the code) is what lets the validation pipeline and the catalog reason about
state machines, and it keeps the JSON human-readable (the value *is* the string).
"""

from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    """Base: members compare/serialize as their string value.

    (We define our own rather than importing ``enum.StrEnum`` so behaviour is
    identical across the 3.11+ range and JSON encoding is trivial.)
    """

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class DocType(_StrEnum):
    """What *kind* of document a resource is. Drives the chunking strategy."""

    LECTURE_SLIDES = "lecture_slides"
    LESSON_PAGE = "lesson_page"
    TEXTBOOK = "textbook"
    NOTEBOOK = "notebook"
    DATASET = "dataset"
    ASSESSMENT = "assessment"
    WORKSHEET = "worksheet"
    REFERENCE = "reference"
    VIDEO = "video"          # future (Video Knowledge module)
    WEB = "web"              # future (Web Search fallback)
    OVERVIEW_NOTE = "overview_note"
    OTHER = "other"


class Role(_StrEnum):
    """The pedagogical role a resource plays. Separates prose from data/code."""

    MATERIAL = "material"      # lectures, lessons, notes — embedded as prose
    CODE = "code"             # notebooks, scripts — referenced, chunked by cell
    DATASET = "dataset"       # csv/sql — referenced, NOT embedded as prose
    ASSESSMENT = "assessment"  # assignments, worksheets, quizzes
    REFERENCE = "reference"    # textbooks — on-demand, separate index treatment


class Language(_StrEnum):
    """Supported content languages (BCP-47 short codes)."""

    EN = "en"
    AR = "ar"


class ExtractionMethod(_StrEnum):
    """How text was (or will be) obtained from the raw source."""

    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    VLM = "vlm"
    PPTX = "pptx"
    TRANSCRIPT = "transcript"
    HTML = "html"
    NONE = "none"          # not yet extracted


class ChunkStrategy(_StrEnum):
    """Doc-type-aware parent strategy (redesign §6)."""

    SECTION = "section"                  # prose: structural section parents
    SLIDE = "slide"                      # one parent per slide
    PAGE = "page"                        # one parent per page
    NOTEBOOK_CELL = "notebook_cell"      # one parent per cell-group
    TRANSCRIPT_WINDOW = "transcript_window"  # video windows
    NONE = "none"


class ProcessingStatus(_StrEnum):
    """Top-level lifecycle of a resource through the ingestion spine.

    Ordered pipeline: PENDING -> EXTRACTED -> CHUNKED -> EMBEDDED -> GRAPHED
    -> INDEXED. FAILED / QUARANTINED are terminal-until-fixed.
    """

    PENDING = "pending"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    GRAPHED = "graphed"
    INDEXED = "indexed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class StageStatus(_StrEnum):
    """Per-stage status for OCR / embedding / graph / vector pipelines.

    ``NOT_REQUIRED`` lets us distinguish "this resource never needs OCR" from
    "OCR pending", which the change detector and dashboards both care about.
    """

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class ValidationStatus(_StrEnum):
    UNVALIDATED = "unvalidated"
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class Persistence(_StrEnum):
    """V3 §3 resource lifecycle flag."""

    PERMANENT = "permanent"
    SESSION = "session"


class RecordStatus(_StrEnum):
    """Catalog-level record state (versioning & supersede-not-delete)."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"
    DRAFT = "draft"


class Difficulty(_StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    UNKNOWN = "unknown"


class RelationType(_StrEnum):
    """Typed resource-to-resource relationships (single edge list, M1.5).

    Deliberately mirrors the Concept Graph edge vocabulary so "a relationship"
    means one thing across the platform. Replaces six parallel link arrays.
    """

    DEPENDS_ON = "depends_on"
    EXTENDS = "extends"
    RELATED_TO = "related_to"
    RECOMMENDED_NEXT = "recommended_next"
    RECOMMENDED_PREVIOUS = "recommended_previous"
    SIMILAR_TO = "similar_to"
    PART_OF = "part_of"
    CONTRASTS_WITH = "contrasts_with"


class RelationSource(_StrEnum):
    """Where a relationship came from — hand-authored vs computed."""

    MANUAL = "manual"       # curated by a human
    DERIVED = "derived"     # computed (embedding similarity / graph) — recomputable


class SourceTier(_StrEnum):
    """Web source trust tiering (V3 §5.3). Higher tiers are boosted in fusion."""

    OFFICIAL = "official"       # official docs / vendor
    ACADEMIC = "academic"       # *.edu, arXiv
    ENCYCLOPEDIC = "encyclopedic"  # wikipedia
    GENERAL = "general"
    LOW_TRUST = "low_trust"     # forums / content farms (demoted/flagged)
    UNKNOWN = "unknown"


class AsrSource(_StrEnum):
    """Transcript provenance for video resources (V3 §6.4)."""

    HUMAN_CAPTIONS = "human_captions"
    AUTO_CAPTIONS = "auto_captions"
    WHISPER = "whisper"
