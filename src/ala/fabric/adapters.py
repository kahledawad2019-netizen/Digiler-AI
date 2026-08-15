"""Source adapters — the contract every loader implements.

A ``SourceAdapter`` turns one raw source (a file, a URL) into a
``LearningResource``. Task 7 will add PDF/PPTX/DOCX/HTML/notebook/YouTube/web
adapters; all they must do is honour this Protocol, so the rest of the platform
stays untouched as sources are added (Open/Closed).

``PlainTextAdapter`` is the reference implementation — it proves the fabric
end-to-end for ``.txt`` / ``.md`` without pulling in any heavy parsing
dependency. It is intentionally simple; it is NOT the ingestion pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ala.core.enums import DocType, ExtractionMethod, StageStatus
from ala.fabric.content import Anchor, BlockType
from ala.fabric.learning_resource import LearningResource
from ala.metadata.schema import ResourceMetadata


@runtime_checkable
class SourceAdapter(Protocol):
    """Contract: raw source + descriptor -> unified LearningResource."""

    name: str
    doc_types: tuple[str, ...]         # doc_types this adapter can produce

    def can_handle(self, path: Path) -> bool:
        """True if this adapter can load the given source path."""
        ...

    def load(self, path: Path, metadata: ResourceMetadata) -> LearningResource:
        """Parse the source into a LearningResource (metadata already known)."""
        ...


class PlainTextAdapter:
    """Reference adapter for plain-text / Markdown sources.

    Splits on blank lines into paragraph blocks, treats Markdown ``#`` lines as
    headings, tracks the heading breadcrumb into ``section_path``, and records a
    char-offset anchor per block. Records a processing step on the metadata so
    the provenance lineage is populated even for this trivial path.
    """

    name = "plain_text"
    doc_types = (DocType.LESSON_PAGE.value, DocType.OVERVIEW_NOTE.value, DocType.OTHER.value)
    _EXTS = {".txt", ".md", ".markdown"}

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self._EXTS

    def load(self, path: Path, metadata: ResourceMetadata) -> LearningResource:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        resource = LearningResource.from_metadata(metadata)
        resource.raw_text = text

        section: list[str] = []
        cursor = 0
        for para in _paragraphs(text):
            start = text.find(para, cursor)
            cursor = start + len(para)
            stripped = para.strip()
            if stripped.startswith("#"):  # Markdown heading
                heading = stripped.lstrip("#").strip()
                section = [heading]
                resource.add_block(
                    heading,
                    block_type=BlockType.HEADING,
                    anchor=Anchor(char_start=start, char_end=cursor),
                    section_path=list(section),
                )
            else:
                resource.add_block(
                    stripped,
                    block_type=BlockType.PARAGRAPH,
                    anchor=Anchor(char_start=start, char_end=cursor),
                    section_path=list(section),
                )

        metadata.provenance.extraction_method = ExtractionMethod.NATIVE_TEXT
        metadata.add_processing_step(
            "extract", status=StageStatus.DONE, tool=self.name, version="1.0",
            notes=f"{resource.block_count} blocks",
        )
        return resource


def _paragraphs(text: str):
    """Yield non-empty paragraphs split on blank lines."""
    for chunk in text.replace("\r\n", "\n").split("\n\n"):
        if chunk.strip():
            yield chunk
