"""A small, dependency-free Markdown block parser.

Reused by the Markdown loader and the Notebook loader (markdown cells). It
preserves structure — headings, code fences, lists, tables, blockquotes,
paragraphs — and tracks the heading breadcrumb into ``section_path``. It also
lifts hyperlinks into ``meta['links']``. It is intentionally not a full CommonMark
implementation; it targets the structures that matter for retrieval quality.
"""

from __future__ import annotations

import re

from ala.fabric.content import BlockType
from ala.ingestion.loaders.base import BlockSpec

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_ULIST = re.compile(r"^\s*([-*+])\s+\S")
_OLIST = re.compile(r"^\s*\d+[.)]\s+\S")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _links(text: str) -> list[dict]:
    return [{"text": m.group(1), "url": m.group(2)} for m in _LINK.finditer(text)]


def parse_markdown_blocks(text: str) -> list[BlockSpec]:
    lines = text.replace("\r\n", "\n").split("\n")
    specs: list[BlockSpec] = []
    stack: list[tuple[int, str]] = []      # (level, title) heading breadcrumb
    i, n = 0, len(lines)

    def section_path() -> list[str]:
        return [t for _, t in stack]

    def flush(buf: list[str], btype: BlockType) -> None:
        text_block = "\n".join(buf).strip()
        if not text_block:
            return
        meta = {"links": _links(text_block)} if btype in (BlockType.PARAGRAPH, BlockType.LIST) else {}
        if not meta.get("links"):
            meta.pop("links", None)
        specs.append(BlockSpec(text=text_block, block_type=btype,
                               section_path=section_path(), meta=meta))

    while i < n:
        line = lines[i]

        # fenced code block
        if line.lstrip().startswith("```"):
            fence = line.lstrip()[:3]
            lang = line.lstrip()[3:].strip()
            code: list[str] = []
            i += 1
            while i < n and not lines[i].lstrip().startswith(fence):
                code.append(lines[i])
                i += 1
            i += 1  # closing fence
            specs.append(BlockSpec(text="\n".join(code), block_type=BlockType.CODE,
                                   section_path=section_path(),
                                   meta={"language": lang} if lang else {}))
            continue

        m = _HEADING.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            specs.append(BlockSpec(text=title, block_type=BlockType.HEADING,
                                   section_path=section_path(), meta={"level": level}))
            i += 1
            continue

        if not line.strip():
            i += 1
            continue

        # table: a header row followed by a separator row
        if "|" in line and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            tbl = [line]
            i += 1
            while i < n and "|" in lines[i]:
                tbl.append(lines[i])
                i += 1
            flush(tbl, BlockType.TABLE)
            continue

        if _ULIST.match(line) or _OLIST.match(line):
            lst = []
            while i < n and (_ULIST.match(lines[i]) or _OLIST.match(lines[i]) or
                             (lines[i].strip() and lines[i].startswith(" "))):
                lst.append(lines[i])
                i += 1
            flush(lst, BlockType.LIST)
            continue

        if line.lstrip().startswith(">"):
            quote = []
            while i < n and lines[i].lstrip().startswith(">"):
                quote.append(lines[i].lstrip()[1:].strip())
                i += 1
            flush(quote, BlockType.QUOTE)
            continue

        # paragraph
        para = []
        while i < n and lines[i].strip() and not _HEADING.match(lines[i]) \
                and not lines[i].lstrip().startswith("```") \
                and not _ULIST.match(lines[i]) and not _OLIST.match(lines[i]) \
                and not lines[i].lstrip().startswith(">"):
            para.append(lines[i])
            i += 1
        flush(para, BlockType.PARAGRAPH)

    return specs
