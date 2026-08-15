"""WebDocumentParser — download + clean a source into a LearningResource-ready file.

Handles HTML (BeautifulSoup), PDF (pypdf) and plain/markdown; local ``file://``
URLs (the offline provider) are read directly. Output is a cleaned Markdown file
saved under ``knowledge_base/raw/<research_track>/…`` so the **existing** ingestion
pipeline (loaders → DIR → chunking → …) processes it — no parallel pipeline.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from ala.core import ids
from ala.research.models import ResearchConfig, WebDocument, WebResult

log = logging.getLogger("ala.research.parser")
_UA = "Mozilla/5.0 (compatible; DigilerAI-Research/1.0)"


class WebDocumentParser:
    def __init__(self, config: ResearchConfig | None = None) -> None:
        self.config = config or ResearchConfig()

    def fetch(self, r: WebResult) -> WebDocument | None:
        try:
            if r.url.startswith("file://") or r.raw.get("path"):
                return self._local(r)
            return self._remote(r)
        except Exception as exc:                              # never crash the pipeline
            log.warning("Parse failed for %s: %s", r.url, exc)
            return None

    # ------------------------------------------------------------------ #
    def _local(self, r: WebResult) -> WebDocument | None:
        path = Path(r.raw.get("path") or unquote(urlparse(r.url).path))
        if not path.is_file():
            return None
        raw = path.read_bytes()
        text, title = self._extract(raw, path.suffix.lower().lstrip("."), r.title)
        return WebDocument(url=r.url, title=title or r.title, text=text,
                           domain=r.domain, published=r.published, doc_type="web")

    def _remote(self, r: WebResult) -> WebDocument | None:
        import urllib.request
        req = urllib.request.Request(r.url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read()
        kind = "pdf" if "pdf" in ctype or r.url.lower().endswith(".pdf") else "html"
        text, title = self._extract(raw, kind, r.title)
        if len(text.split()) < 40:                           # too thin to be useful
            return None
        return WebDocument(url=r.url, title=title or r.title, text=text,
                           domain=r.domain, published=r.published, doc_type="web")

    def _extract(self, raw: bytes, kind: str, fallback_title: str) -> tuple[str, str]:
        if kind == "pdf":
            return self._pdf(raw), fallback_title
        if kind in ("html", "htm"):
            return self._html(raw, fallback_title)
        return raw.decode("utf-8", errors="ignore").strip(), fallback_title

    @staticmethod
    def _html(raw: bytes, fallback_title: str) -> tuple[str, str]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()
        title = (soup.title.get_text(strip=True) if soup.title else "") or fallback_title
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
        return text, title

    @staticmethod
    def _pdf(raw: bytes) -> str:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages).strip()

    # ------------------------------------------------------------------ #
    def save(self, doc: WebDocument, dest_dir: Path) -> Path:
        """Persist as Markdown for the standard ingestion loaders."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        slug = ids.slugify(doc.title or doc.domain or "web-source")[:60] or "web-source"
        path = dest_dir / f"{slug}.md"
        header = [f"# {doc.title}", "", f"> Source: {doc.url}"]
        if doc.published:
            header.append(f"> Published: {doc.published}")
        path.write_text("\n".join(header) + "\n\n" + doc.text, encoding="utf-8")
        doc.path = str(path)
        return path
