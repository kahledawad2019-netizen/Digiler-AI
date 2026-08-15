"""HTML loader (.html / .htm) — structure-preserving via BeautifulSoup.

Walks the DOM and maps semantic tags to block types: headings, paragraphs,
lists, tables, code, blockquotes, figure captions. Collects hyperlinks and image
references into block ``meta``. Strips script/style/nav/footer chrome.
"""

from __future__ import annotations

from pathlib import Path

from ala.core.enums import DocType, ExtractionMethod
from ala.fabric.content import BlockType
from ala.ingestion.loaders.base import BaseLoader, BlockSpec

_DROP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "form"}
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


class HtmlLoader(BaseLoader):
    name = "html"
    extensions = (".html", ".htm")
    doc_types = (DocType.WEB.value, DocType.LESSON_PAGE.value)
    extraction_method = ExtractionMethod.HTML
    requires = ("bs4",)

    def _parse(self, path: Path) -> list[BlockSpec]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        for tag in soup(list(_DROP_TAGS)):
            tag.decompose()
        root = soup.body or soup

        specs: list[BlockSpec] = []
        stack: list[tuple[int, str]] = []

        def section_path() -> list[str]:
            return [t for _, t in stack]

        for el in root.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "pre",
             "code", "table", "blockquote", "figcaption"],
            recursive=True,
        ):
            name = el.name
            text = el.get_text(" ", strip=True)
            if not text:
                continue

            if name in _HEADINGS:
                level = _HEADINGS[name]
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, text))
                specs.append(BlockSpec(text=text, block_type=BlockType.HEADING,
                                       section_path=section_path(), meta={"level": level}))
                continue

            btype = {
                "p": BlockType.PARAGRAPH,
                "ul": BlockType.LIST,
                "ol": BlockType.LIST,
                "pre": BlockType.CODE,
                "code": BlockType.CODE,
                "table": BlockType.TABLE,
                "blockquote": BlockType.QUOTE,
                "figcaption": BlockType.IMAGE_CAPTION,
            }[name]

            meta: dict = {}
            links = [{"text": a.get_text(" ", strip=True), "url": a.get("href")}
                     for a in el.find_all("a", href=True)]
            if links:
                meta["links"] = links
            imgs = [img.get("src") for img in el.find_all("img", src=True)]
            if imgs:
                meta["images"] = imgs

            specs.append(BlockSpec(text=text, block_type=btype,
                                   section_path=section_path(), meta=meta))
        return specs
