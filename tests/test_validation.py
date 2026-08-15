"""Tests for the validation pipeline."""

from __future__ import annotations

from ala.core.enums import ExtractionMethod, ProcessingStatus, StageStatus
from ala.metadata.validation import (
    ValidationContext,
    ValidationPipeline,
    ValidationStatus,
)


def _ctx(**kw):
    base = dict(
        check_files=False,
        supported_languages={"en", "ar"},
        valid_tracks={"technical", "nontechnical"},
        valid_courses={"dmv", "aiml", "eng"},
    )
    base.update(kw)
    return ValidationContext(**base)


def test_valid_record_passes(make_meta):
    result = ValidationPipeline().run(make_meta(), _ctx())
    assert result.ok
    assert result.status == ValidationStatus.VALID


def test_unknown_track_is_error(make_meta):
    m = make_meta(track="technical", course="dmv")
    m.track = "does-not-exist"
    result = ValidationPipeline().run(m, _ctx())
    assert not result.ok
    assert any(i.rule == "taxonomy" for i in result.errors)


def test_indexed_without_embeddings_is_error(make_meta):
    m = make_meta()
    m.status.processing_status = ProcessingStatus.INDEXED
    m.status.embedding_status = StageStatus.PENDING  # inconsistent
    result = ValidationPipeline().run(m, _ctx())
    assert not result.ok
    assert any(i.rule == "stage_consistency" for i in result.errors)


def test_ocr_method_without_ocr_status_is_warning(make_meta):
    m = make_meta()
    m.provenance.extraction_method = ExtractionMethod.OCR
    m.status.ocr_status = StageStatus.NOT_REQUIRED
    result = ValidationPipeline().run(m, _ctx())
    assert result.status == ValidationStatus.WARNING
    assert result.ok  # warnings don't block


def test_missing_file_is_error_when_checking_disk(make_meta, tmp_path):
    m = make_meta()
    m.file.file_path = "definitely/not/here.pdf"
    result = ValidationPipeline().run(m, _ctx(check_files=True, project_root=tmp_path))
    assert any(i.rule == "file_exists" for i in result.errors)
