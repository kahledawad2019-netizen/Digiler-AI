"""Each pipeline stage tested independently (resource-in / resource-out)."""

from __future__ import annotations

import pytest

from ala.fabric.content import Anchor, BlockType
from ala.fabric.learning_resource import LearningResource
from ala.ingestion.config import PipelineConfig
from ala.ingestion.context import IngestionJob, PipelineContext, ResourceClassification
from ala.ingestion.errors import ValidationFailedError
from ala.ingestion.stages import (
    AcademicStructureStage,
    CleaningNormalizationStage,
    FileValidationStage,
    LanguageDetectionStage,
    MetadataEnrichmentStage,
    ResourcePackagingStage,
    StructuralParsingStage,
)


def _ctx(settings, tmp_path):
    cls = ResourceClassification(track="technical", course="dmv", module="w03", title="X")
    job = IngestionJob(tmp_path / "x.md", cls)
    return PipelineContext(settings, PipelineConfig.from_settings(settings), job)


def _res(make_meta, **kw):
    return LearningResource.from_metadata(make_meta(**kw))


def test_normalization_stage_cleans_text(settings, tmp_path, make_meta):
    ctx = _ctx(settings, tmp_path)
    lr = _res(make_meta)
    lr.add_block("“Hi”   there", block_type=BlockType.PARAGRAPH)
    out = CleaningNormalizationStage().process(lr, ctx)
    assert out.blocks[0].text == '"Hi" there'


def test_normalization_stage_removes_repeated_headers(settings, tmp_path, make_meta):
    ctx = _ctx(settings, tmp_path)
    lr = _res(make_meta)
    for pg in (1, 2, 3):
        lr.add_block(f"CONFIDENTIAL\nPage body {pg}", block_type=BlockType.PARAGRAPH,
                     anchor=Anchor(page=pg))
    out = CleaningNormalizationStage().process(lr, ctx)
    assert all("CONFIDENTIAL" not in b.text for b in out.blocks)
    assert any("Page body" in b.text for b in out.blocks)


def test_language_stage_sets_language(settings, tmp_path, make_meta):
    ctx = _ctx(settings, tmp_path)
    lr = _res(make_meta, language="ar")           # start wrong on purpose
    lr.add_block("This is a long English sentence about databases and foreign keys.")
    LanguageDetectionStage().process(lr, ctx)
    assert lr.metadata.language == "en"
    assert ctx.analysis["language"]["code"] == "en"


def test_structural_stage_promotes_headings(settings, tmp_path, make_meta):
    ctx = _ctx(settings, tmp_path)
    lr = _res(make_meta)
    lr.add_block("Introduction to SQL Constraints", block_type=BlockType.PARAGRAPH)
    lr.add_block("This is a normal sentence that ends with a period.",
                 block_type=BlockType.PARAGRAPH)
    StructuralParsingStage().process(lr, ctx)
    assert lr.blocks[0].type == BlockType.HEADING.value
    assert lr.blocks[1].type == BlockType.PARAGRAPH.value


def test_academic_stage_enriches_metadata(settings, tmp_path, make_meta):
    ctx = _ctx(settings, tmp_path)
    lr = _res(make_meta, title="Week 5 Overview")
    lr.add_block("Clustering", block_type=BlockType.HEADING)
    AcademicStructureStage().process(lr, ctx)
    assert lr.metadata.week == 5
    assert "Clustering" in lr.metadata.topics
    assert ctx.analysis["academic"]["week"] == 5


def test_enrichment_stage(settings, tmp_path, make_meta):
    ctx = _ctx(settings, tmp_path)
    lr = _res(make_meta)
    lr.add_block("database database keys index index index tables joins")
    MetadataEnrichmentStage().process(lr, ctx)
    assert lr.metadata.pedagogy.keywords
    assert lr.metadata.academic.estimated_study_time_min >= 1
    assert ctx.analysis["stats"]["block_count"] == 1


def test_packaging_stage_persists_and_marks_extracted(settings, tmp_path, make_meta):
    ctx = _ctx(settings, tmp_path)
    lr = _res(make_meta)
    lr.add_block("content")
    ResourcePackagingStage(tmp_path / "derived").process(lr, ctx)
    assert lr.metadata.status.processing_status == "extracted"
    assert (tmp_path / "derived" / lr.resource_id / "package.json").is_file()
    assert ctx.analysis["package"].clean_text == "content"


def test_file_validation_rejects_unsupported(settings, tmp_path, make_meta):
    ctx = _ctx(settings, tmp_path)
    bad = tmp_path / "a.xyz"
    bad.write_text("x", encoding="utf-8")
    ctx.job.source_path = bad
    with pytest.raises(ValidationFailedError):
        FileValidationStage().process(_res(make_meta), ctx)
