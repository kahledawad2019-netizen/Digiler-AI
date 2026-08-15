"""Plain-text loader (.txt)."""

from __future__ import annotations

from pathlib import Path

from ala.core.enums import DocType, ExtractionMethod
from ala.fabric.content import Anchor, BlockType
from ala.ingestion.loaders.base import BaseLoader, BlockSpec


class TextLoader(BaseLoader):
    name = "text"
    extensions = (".txt",)
    doc_types = (DocType.LESSON_PAGE.value, DocType.OVERVIEW_NOTE.value, DocType.OTHER.value)
    extraction_method = ExtractionMethod.NATIVE_TEXT

    def _parse(self, path: Path) -> list[BlockSpec]:
        text = path.read_text(encoding="utf-8", errors="replace")
        specs: list[BlockSpec] = []
        cursor = 0
        for chunk in text.replace("\r\n", "\n").split("\n\n"):
            if not chunk.strip():
                cursor += len(chunk) + 2
                continue
            start = text.find(chunk, cursor)
            end = start + len(chunk)
            cursor = end
            specs.append(
                BlockSpec(
                    text=chunk.strip(),
                    block_type=BlockType.PARAGRAPH,
                    anchor=Anchor(char_start=start, char_end=end),
                )
            )
        return specs
