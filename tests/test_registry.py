"""Tests for the ResourceRegistry orchestrator."""

from __future__ import annotations

import pytest

from ala.core.enums import ProcessingStatus, StageStatus
from ala.core.exceptions import DuplicateResourceError
from ala.metadata.sidecar import sidecar_path


def test_register_creates_metadata_catalog_row_and_sidecar(registry_factory, tmp_path, sample_file):
    reg = registry_factory(tmp_path)
    meta = reg.register(
        sample_file, track="technical", course="dmv", module="w03",
        title="Constraints and Relationships", doc_type="lesson_page",
    )
    assert meta.resource_id == "technical.dmv.w03.constraints-and-relationships"
    assert meta.lifecycle.version == 1
    assert len(meta.file.sha256) == 64
    assert meta.retrieval.chunk_strategy == "section"          # doc-type-aware default
    assert reg.catalog.exists(meta.resource_id)
    assert sidecar_path(sample_file).is_file()                 # JSON beside the resource


def test_slides_get_slide_chunk_strategy(registry_factory, tmp_path, sample_file):
    reg = registry_factory(tmp_path)
    meta = reg.register(
        sample_file, track="technical", course="aiml", module="l06",
        title="KNN", doc_type="lecture_slides",
    )
    assert meta.retrieval.chunk_strategy == "slide"


def test_duplicate_registration_raises(registry_factory, tmp_path, sample_file):
    reg = registry_factory(tmp_path)
    reg.register(sample_file, track="technical", course="dmv", module="w03", title="X")
    with pytest.raises(DuplicateResourceError):
        reg.register(sample_file, track="technical", course="dmv", module="w03", title="X")


def test_update_bumps_version_and_flags_content_change(registry_factory, tmp_path, sample_file):
    reg = registry_factory(tmp_path)
    reg.register(sample_file, track="technical", course="dmv", module="w03", title="X")

    sample_file.write_text("EDITED CONTENT — different bytes.\n", encoding="utf-8")
    meta2 = reg.register(
        sample_file, track="technical", course="dmv", module="w03", title="X", update=True
    )
    assert meta2.lifecycle.version == 2
    assert meta2.status.processing_status == ProcessingStatus.PENDING.value

    events = {e["event_type"] for e in reg.catalog.get_events(meta2.resource_id)}
    assert "content_changed" in events


def test_set_status_transitions(registry_factory, tmp_path, sample_file):
    reg = registry_factory(tmp_path)
    m = reg.register(sample_file, track="technical", course="dmv", module="w03", title="X")
    reg.set_status(
        m.resource_id,
        processing_status=ProcessingStatus.INDEXED,
        embedding_status=StageStatus.DONE,
        chunk_count=12,
        embedder_version="multilingual-e5-small",
        mark_indexed_now=True,
    )
    updated = reg.get(m.resource_id)
    assert updated.status.processing_status == ProcessingStatus.INDEXED.value
    assert updated.retrieval.chunk_count == 12
    assert updated.lifecycle.embedder_version == "multilingual-e5-small"
    assert updated.last_indexed_at is not None


def test_unknown_track_fails_validation(registry_factory, tmp_path, sample_file):
    reg = registry_factory(tmp_path)
    from ala.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        reg.register(sample_file, track="bogus", course="dmv", module="w03", title="X")
