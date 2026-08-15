"""Stage 2 & 3 — chunking + chunk-metadata tests."""

from __future__ import annotations

import json

from ala.fabric.content import Anchor, BlockType
from ala.fabric.learning_resource import LearningResource
from ala.retrieval.chunking import (
    ChunkingConfig,
    ChunkKind,
    ChunkStore,
    ChunkType,
    ParentChildChunker,
)
from ala.retrieval.chunking.splitter import RecursiveTextSplitter
from ala.retrieval.chunking.tokenizer import WordTokenCounter


def test_splitter_respects_size_and_overlap():
    counter = WordTokenCounter(tokens_per_word=1.0)
    splitter = RecursiveTextSplitter(max_tokens=10, overlap_tokens=3, counter=counter)
    text = " ".join(f"word{i}." for i in range(40))
    parts = splitter.split(text)
    assert len(parts) > 1
    assert all(counter.count(p) <= 10 for p in parts)
    assert parts[0].split()[-1] in parts[1]        # overlap carried forward


def test_parent_child_no_orphans_and_citations(make_meta):
    lr = LearningResource.from_metadata(make_meta())
    long_text = " ".join(f"Sentence number {i} about databases and keys." for i in range(60))
    lr.add_block("Intro", block_type=BlockType.HEADING, section_path=["Intro"])
    lr.add_block(long_text, block_type=BlockType.PARAGRAPH, section_path=["Intro"])

    cfg = ChunkingConfig(parent_target_tokens=200, child_target_tokens=40,
                         child_overlap_tokens=8, min_chunk_tokens=5)
    cs = ParentChildChunker(cfg).chunk(lr)

    assert cs.parents and len(cs.children) > 1
    parent_ids = {p.chunk_id for p in cs.parents}
    for child in cs.children:
        assert child.metadata.parent_id in parent_ids          # no orphans
        assert child.metadata.resource_id == lr.resource_id
        assert child.metadata.kind == ChunkKind.CHILD
        assert child.metadata.section_path == ["Intro"]
        assert child.metadata.heading == "Intro"
    for parent in cs.parents:
        assert parent.metadata.child_ids                       # every parent has children


def test_slide_grouping_sets_slide_and_type(make_meta):
    lr = LearningResource.from_metadata(make_meta())
    lr.add_block("KNN", block_type=BlockType.HEADING, anchor=Anchor(slide=1), section_path=["KNN"])
    lr.add_block("A classifier.", block_type=BlockType.PARAGRAPH, anchor=Anchor(slide=1),
                 section_path=["KNN"])
    lr.add_block("SVM", block_type=BlockType.HEADING, anchor=Anchor(slide=2), section_path=["SVM"])
    cs = ParentChildChunker().chunk(lr)
    assert {p.metadata.slide for p in cs.parents} == {1, 2}
    assert all(c.metadata.chunk_type == ChunkType.SLIDE for c in cs.children)


def test_prose_parent_records_page_range(make_meta):
    lr = LearningResource.from_metadata(make_meta())
    lr.add_block("Para A.", block_type=BlockType.PARAGRAPH, anchor=Anchor(page=1))
    lr.add_block("Para B.", block_type=BlockType.PARAGRAPH, anchor=Anchor(page=2))
    cs = ParentChildChunker(ChunkingConfig(parent_target_tokens=500)).chunk(lr)
    parent = cs.parents[0]
    assert parent.metadata.page == 1 and parent.metadata.page_end == 2


def test_metadata_carries_enrichment_and_reserved_fields(make_meta):
    meta = make_meta()
    meta.topics = ["sql"]
    meta.pedagogy.keywords = ["key"]
    meta.pedagogy.learning_objectives = ["understand keys"]
    lr = LearningResource(metadata=meta)
    lr.add_block("content about keys", block_type=BlockType.PARAGRAPH)
    child = ParentChildChunker().chunk(lr).children[0]
    assert child.metadata.topics == ["sql"]
    assert "key" in child.metadata.keywords
    assert child.metadata.learning_objectives == ["understand keys"]
    assert child.metadata.embedding_version is None      # reserved for Stage 4
    assert child.metadata.scores.dense is None           # reserved for Stage 5
    assert child.metadata.graph_node_ids == []           # reserved for Stage 6


def test_store_separates_metadata_from_text(make_meta, tmp_path):
    lr = LearningResource.from_metadata(make_meta())
    lr.add_block("Alpha content here.", block_type=BlockType.PARAGRAPH)
    cs = ParentChildChunker().chunk(lr)
    store = ChunkStore(tmp_path)
    d = store.save(cs)

    assert (d / "children.meta.jsonl").is_file() and (d / "children.text.jsonl").is_file()
    meta_row = json.loads((d / "children.meta.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "text" not in meta_row                        # metadata stored without text
    reloaded = store.load_chunkset(lr.resource_id)
    assert reloaded.children[0].text == "Alpha content here."
    assert reloaded.children[0].metadata.chunk_id == cs.children[0].chunk_id


def test_chunking_service_updates_status(make_meta, tmp_path, settings, mem_catalog):
    from ala.registry.registry import ResourceRegistry
    from ala.retrieval.chunking import ChunkingService

    scoped = settings.model_copy(update={"project_root": tmp_path})
    registry = ResourceRegistry(scoped, mem_catalog)
    src = tmp_path / "x.md"
    src.write_text("# H\n\nbody text here about keys", encoding="utf-8")
    meta = registry.register(src, track="technical", course="dmv", module="w03", title="X")

    lr = LearningResource(metadata=meta)
    lr.add_block("body text here about keys", block_type=BlockType.PARAGRAPH, section_path=["H"])
    cs = ChunkingService(scoped, registry=registry).chunk_resource(lr)

    assert cs.children
    reloaded = registry.catalog.get(meta.resource_id)
    assert reloaded.status.processing_status == "chunked"
    assert reloaded.retrieval.chunk_count == len(cs.children)
    assert reloaded.retrieval.child_chunk_ids == cs.child_ids
