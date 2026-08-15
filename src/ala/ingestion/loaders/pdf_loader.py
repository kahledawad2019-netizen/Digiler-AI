"""PDF loader (.pdf) via pypdf.

Structured as two parts for testability + SOLID:
  * ``_extract_pages`` — the I/O side (pypdf), injectable for tests (DI seam).
  * ``_build`` — pure logic turning page texts into page-anchored blocks.

Heading *promotion* is deferred to the Structural Parsing stage, since pypdf text
carries no heading semantics; here we keep faithful, page-anchored paragraphs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from ala.core.enums import DocType, ExtractionMethod
from ala.fabric.content import Anchor, BlockType
from ala.ingestion.loaders.base import BaseLoader, BlockSpec

_PARA_SPLIT = re.compile(r"\n\s*\n")


class PdfLoader(BaseLoader):
    name = "pdf"
    extensions = (".pdf",)
    doc_types = (
        DocType.TEXTBOOK.value, DocType.LESSON_PAGE.value,
        DocType.LECTURE_SLIDES.value, DocType.REFERENCE.value,
    )
    extraction_method = ExtractionMethod.NATIVE_TEXT
    requires = ("pypdf",)

    def __init__(self, page_extractor: Callable[[Path], list[str]] | None = None) -> None:
        # Inject a page-text extractor in tests to avoid needing a real PDF.
        self._page_extractor = page_extractor

    def _extract_pages(self, path: Path) -> list[str]:
        if self._page_extractor is not None:
            return self._page_extractor(path)
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [(page.extract_text() or "") for page in reader.pages]

    def _parse(self, path: Path) -> list[BlockSpec]:
        return self._build(self._extract_pages(path))

    def _build(self, pages: list[str]) -> list[BlockSpec]:
        specs: list[BlockSpec] = []
        for page_no, raw in enumerate(pages, start=1):
            text = (raw or "").replace("\r\n", "\n")
            parts = _PARA_SPLIT.split(text) if _PARA_SPLIT.search(text) else [text]
            for part in parts:
                clean = part.strip()
                if not clean:
                    continue
                specs.append(
                    BlockSpec(
                        text=clean,
                        block_type=BlockType.PARAGRAPH,
                        anchor=Anchor(page=page_no),
                        meta={"page": page_no},
                    )
                )
        return specs
