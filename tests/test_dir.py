"""Stage 1 — DIR tests."""

from __future__ import annotations

from ala.fabric.content import BlockType
from ala.fabric.learning_resource import LearningResource
from ala.retrieval.dir import build_document_ir


def _doc(make_meta) -> LearningResource:
    lr = LearningResource.from_metadata(make_meta())
    lr.add_block("Databases", block_type=BlockType.HEADING, section_path=["Databases"])
    lr.add_block("A table stores rows.", block_type=BlockType.PARAGRAPH, section_path=["Databases"])
    lr.add_block("Keys", block_type=BlockType.HEADING, section_path=["Databases", "Keys"])
    lr.add_block("A primary key is unique.", block_type=BlockType.PARAGRAPH,
                 section_path=["Databases", "Keys"])
    lr.add_block("SELECT * FROM t;", block_type=BlockType.CODE,
                 section_path=["Databases", "Keys"],
                 meta={"links": [{"text": "docs", "url": "http://x"}]})
    return lr


def test_section_tree_is_nested(make_meta):
    ir = build_document_ir(_doc(make_meta))
    assert len(ir.sections) == 1
    databases = ir.sections[0]
    assert databases.heading == "Databases"
    assert any(child.heading == "Keys" for child in databases.children)


def test_typed_accessors(make_meta):
    ir = build_document_ir(_doc(make_meta))
    assert len(ir.headings()) == 2
    assert len(ir.paragraphs()) == 2
    assert len(ir.code_blocks()) == 1
    links = ir.hyperlinks()
    assert links and links[0]["url"] == "http://x"


def test_coverage_flags_present_elements(make_meta):
    ir = build_document_ir(_doc(make_meta))
    cov = ir.coverage()
    for key in ("sections", "headings", "paragraphs", "code", "hyperlinks", "anchors", "language"):
        assert cov[key] is True
