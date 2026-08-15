"""Tests for the Resource Fabric (LearningResource + adapters)."""

from __future__ import annotations

from ala.core.enums import DocType
from ala.fabric import Anchor, BlockType, ContentBlock, LearningResource, PlainTextAdapter


def test_anchor_render():
    assert Anchor(page=14).render() == "p.14"
    assert Anchor(slide=7).render() == "slide 7"
    assert Anchor(t_start=754).render() == "12:34"
    assert Anchor(cell=3).render() == "cell 3"
    assert Anchor().render() == ""


def test_add_block_assigns_id_and_order(make_meta):
    lr = LearningResource.from_metadata(make_meta())
    b0 = lr.add_block("Foreign keys enforce integrity.", block_type=BlockType.PARAGRAPH)
    b1 = lr.add_block("Primary keys are unique.")
    assert b0.block_id.endswith("#b0000") and b1.order == 1
    assert lr.block_count == 2
    assert "Primary keys" in lr.text()


def test_by_type_and_languages(make_meta):
    lr = LearningResource.from_metadata(make_meta())
    lr.add_block("Heading", block_type=BlockType.HEADING)
    lr.add_block("Body", language="en")
    assert len(lr.by_type(BlockType.HEADING)) == 1
    assert lr.languages() == {"en"}


def test_round_trip_and_derived_save_load(make_meta, tmp_path):
    lr = LearningResource.from_metadata(make_meta())
    lr.add_block("Alpha")
    lr.add_block("Beta")
    restored = LearningResource.from_dict(lr.to_dict())
    assert restored == lr

    lr.save(tmp_path)
    reloaded = LearningResource.load(tmp_path, lr.resource_id)
    assert reloaded.block_count == 2
    assert reloaded.metadata.resource_id == lr.resource_id


def test_plain_text_adapter_produces_unified_resource(make_meta, tmp_path):
    src = tmp_path / "note.md"
    src.write_text("# Constraints\n\nA primary key is unique.\n\nA foreign key links tables.\n",
                   encoding="utf-8")
    meta = make_meta(doc_type=DocType.LESSON_PAGE)

    adapter = PlainTextAdapter()
    assert adapter.can_handle(src)
    lr = adapter.load(src, meta)

    headings = lr.by_type(BlockType.HEADING)
    assert len(headings) == 1 and headings[0].text == "Constraints"
    # heading breadcrumb propagates to following paragraphs
    paras = lr.by_type(BlockType.PARAGRAPH)
    assert all(p.section_path == ["Constraints"] for p in paras)
    # processing lineage recorded even on the trivial path
    assert any(s.step == "extract" and s.tool == "plain_text"
               for s in lr.metadata.provenance.history)


def test_adapter_satisfies_protocol():
    from ala.fabric import SourceAdapter
    assert isinstance(PlainTextAdapter(), SourceAdapter)
