"""LoaderRegistry — selects a loader for a path (Stage 3: Loader Selection).

Loaders are injected, not hardcoded into the pipeline, so adding a future
adapter (YouTube, web, image-OCR) is a registration, not a pipeline edit.
"""

from __future__ import annotations

from pathlib import Path

from ala.fabric.adapters import SourceAdapter
from ala.ingestion.errors import UnsupportedResourceError
from ala.ingestion.loaders.docx_loader import DocxLoader
from ala.ingestion.loaders.html_loader import HtmlLoader
from ala.ingestion.loaders.markdown_loader import MarkdownLoader
from ala.ingestion.loaders.notebook_loader import NotebookLoader
from ala.ingestion.loaders.pdf_loader import PdfLoader
from ala.ingestion.loaders.pptx_loader import PptxLoader
from ala.ingestion.loaders.text_loader import TextLoader


class LoaderRegistry:
    def __init__(self, loaders: list[SourceAdapter] | None = None) -> None:
        self._loaders: list[SourceAdapter] = list(loaders) if loaders else []

    def register(self, loader: SourceAdapter) -> None:
        self._loaders.append(loader)

    def select(self, path: str | Path) -> SourceAdapter:
        p = Path(path)
        for loader in self._loaders:
            if loader.can_handle(p):
                return loader
        raise UnsupportedResourceError(f"No loader for '{p.suffix}' ({p.name})")

    def supported_extensions(self) -> set[str]:
        exts: set[str] = set()
        for loader in self._loaders:
            exts.update(getattr(loader, "extensions", ()))
        return exts


def default_loaders() -> LoaderRegistry:
    """The standard loader set for this milestone."""
    return LoaderRegistry(
        [
            TextLoader(),
            MarkdownLoader(),
            HtmlLoader(),
            PdfLoader(),
            PptxLoader(),
            DocxLoader(),
            NotebookLoader(),
        ]
    )
