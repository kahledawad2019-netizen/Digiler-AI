"""Markdown loader (.md / .markdown) — structure-preserving."""

from __future__ import annotations

from pathlib import Path

from ala.core.enums import DocType, ExtractionMethod
from ala.ingestion.loaders.base import BaseLoader, BlockSpec
from ala.ingestion.loaders.markdown_parse import parse_markdown_blocks


class MarkdownLoader(BaseLoader):
    name = "markdown"
    extensions = (".md", ".markdown")
    doc_types = (DocType.LESSON_PAGE.value, DocType.OVERVIEW_NOTE.value)
    extraction_method = ExtractionMethod.NATIVE_TEXT

    def _parse(self, path: Path) -> list[BlockSpec]:
        return parse_markdown_blocks(path.read_text(encoding="utf-8", errors="replace"))
