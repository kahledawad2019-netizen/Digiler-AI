"""Source loaders + the registry that selects one by file type.

Each loader implements the ``SourceAdapter`` contract from ``ala.fabric`` and
produces a ``LearningResource``. Heavy third-party parsers are imported lazily
inside each loader, so importing this package never fails if an optional
dependency is absent — the loader reports a structured error instead.
"""

from ala.ingestion.loaders.base import BaseLoader, BlockSpec
from ala.ingestion.loaders.registry import LoaderRegistry, default_loaders
from ala.ingestion.loaders.text_loader import TextLoader
from ala.ingestion.loaders.markdown_loader import MarkdownLoader
from ala.ingestion.loaders.html_loader import HtmlLoader
from ala.ingestion.loaders.pdf_loader import PdfLoader
from ala.ingestion.loaders.pptx_loader import PptxLoader
from ala.ingestion.loaders.docx_loader import DocxLoader
from ala.ingestion.loaders.notebook_loader import NotebookLoader

__all__ = [
    "BaseLoader",
    "BlockSpec",
    "LoaderRegistry",
    "default_loaders",
    "TextLoader",
    "MarkdownLoader",
    "HtmlLoader",
    "PdfLoader",
    "PptxLoader",
    "DocxLoader",
    "NotebookLoader",
]
