"""Loader tests — one per supported document type."""

from __future__ import annotations

from pathlib import Path

import pytest

from ala.fabric.content import BlockType
from ala.ingestion.errors import UnsupportedResourceError
from ala.ingestion.loaders import (
    DocxLoader,
    HtmlLoader,
    MarkdownLoader,
    NotebookLoader,
    PdfLoader,
    PptxLoader,
    TextLoader,
    default_loaders,
)
from ala.ingestion.loaders.markdown_parse import parse_markdown_blocks


def _types(lr):
    return [b.type for b in lr.blocks]


def test_text_loader(tmp_path, make_meta):
    p = tmp_path / "a.txt"
    p.write_text("Para one.\n\nPara two here.", encoding="utf-8")
    lr = TextLoader().load(p, make_meta())
    assert lr.block_count == 2
    assert all(b.type == BlockType.PARAGRAPH.value for b in lr.blocks)
    assert lr.blocks[0].anchor.char_start == 0


def test_markdown_loader_preserves_structure(tmp_path, make_meta):
    md = (
        "# Title\n\nIntro para.\n\n## Sub\n\n- a\n- b\n\n"
        "```python\nx = 1\n```\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    )
    p = tmp_path / "a.md"
    p.write_text(md, encoding="utf-8")
    lr = MarkdownLoader().load(p, make_meta())
    t = _types(lr)
    assert BlockType.HEADING.value in t
    assert BlockType.LIST.value in t
    assert BlockType.CODE.value in t
    assert BlockType.TABLE.value in t
    assert any(b.section_path[-1:] == ["Sub"] for b in lr.blocks)


def test_markdown_parse_sections_and_links():
    specs = parse_markdown_blocks("# H1\n\nSee [x](http://e.com).\n\n## H2\n\nbody")
    body = [s for s in specs if s.text == "body"][0]
    assert body.section_path == ["H1", "H2"]
    para = [s for s in specs if "See" in s.text][0]
    assert para.meta.get("links") and para.meta["links"][0]["url"] == "http://e.com"


def test_html_loader(tmp_path, make_meta):
    html = (
        "<html><body><h1>Heading</h1>"
        "<p>Para with <a href='http://e.com'>link</a>.</p>"
        "<ul><li>x</li><li>y</li></ul>"
        "<script>ignore()</script></body></html>"
    )
    p = tmp_path / "a.html"
    p.write_text(html, encoding="utf-8")
    lr = HtmlLoader().load(p, make_meta())
    t = _types(lr)
    assert BlockType.HEADING.value in t and BlockType.PARAGRAPH.value in t and BlockType.LIST.value in t
    para = [b for b in lr.blocks if b.type == BlockType.PARAGRAPH.value][0]
    assert para.meta.get("links")
    assert all("ignore" not in b.text for b in lr.blocks)  # script stripped


def test_notebook_loader(tmp_path, make_meta, make_notebook):
    p = make_notebook(tmp_path / "n.ipynb")
    lr = NotebookLoader().load(p, make_meta())
    assert any(b.type == BlockType.HEADING.value for b in lr.blocks)
    code = [b for b in lr.blocks if b.type == BlockType.CODE.value]
    assert code and code[0].anchor.cell is not None


def test_docx_loader(tmp_path, make_meta, make_docx):
    p = make_docx(tmp_path / "d.docx")
    lr = DocxLoader().load(p, make_meta())
    t = _types(lr)
    assert BlockType.HEADING.value in t and BlockType.TABLE.value in t


def test_pptx_loader(tmp_path, make_meta, make_pptx):
    p = make_pptx(tmp_path / "s.pptx")
    lr = PptxLoader().load(p, make_meta())
    assert any(b.type == BlockType.HEADING.value for b in lr.blocks)
    assert all(b.anchor.slide == 1 for b in lr.blocks)


def test_pdf_loader_build_with_injected_pages(make_meta):
    # DI seam: inject page texts so no real PDF file is needed for the unit test.
    loader = PdfLoader(
        page_extractor=lambda p: ["Intro line\n\nBody paragraph here.", "Second page text."]
    )
    lr = loader.load(Path("fake.pdf"), make_meta())
    assert lr.block_count == 3
    assert lr.blocks[0].anchor.page == 1
    assert lr.blocks[-1].anchor.page == 2


def test_pptx_loader_handles_ppsx(tmp_path, make_meta, make_pptx):
    import zipfile

    # Build a genuine .ppsx (PowerPoint Show) by swapping the pptx content-type.
    pptx_path = make_pptx(tmp_path / "s.pptx")
    ppsx_path = tmp_path / "s.ppsx"
    with zipfile.ZipFile(pptx_path) as src, \
            zipfile.ZipFile(ppsx_path, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.namelist():
            data = src.read(item)
            if item == "[Content_Types].xml":
                data = data.replace(b"presentationml.presentation.main+xml",
                                    b"presentationml.slideshow.main+xml")
            out.writestr(item, data)

    loader = PptxLoader()
    assert loader.can_handle(ppsx_path)
    lr = loader.load(ppsx_path, make_meta())
    assert lr.block_count > 0
    assert any(b.type == BlockType.HEADING.value for b in lr.blocks)


def test_loader_registry_selects_and_rejects():
    reg = default_loaders()
    assert reg.select(Path("a.md")).name == "markdown"
    assert reg.select(Path("a.PDF")).name == "pdf"     # case-insensitive
    with pytest.raises(UnsupportedResourceError):
        reg.select(Path("a.xyz"))
