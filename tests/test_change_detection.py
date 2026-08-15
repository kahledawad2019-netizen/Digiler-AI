"""Tests for change detection / incremental-indexing support."""

from __future__ import annotations

from ala.registry.change_detection import ChangeDetector, ChangeType


def _register(reg, path):
    return reg.register(path, track="technical", course="dmv", module="w03", title="Lesson")


def test_unchanged_after_registration(registry_factory, tmp_path, sample_file):
    reg = registry_factory(tmp_path)
    m = _register(reg, sample_file)
    det = ChangeDetector(reg.catalog, tmp_path)
    assert det.classify(m.resource_id) == ChangeType.UNCHANGED
    # Freshly registered => PENDING => it DOES need (initial) processing.
    assert det.needs_reprocessing(m.resource_id) is True

    # Once indexed and still unchanged on disk => no reprocessing needed.
    from ala.core.enums import ProcessingStatus, StageStatus

    reg.set_status(
        m.resource_id,
        processing_status=ProcessingStatus.INDEXED,
        embedding_status=StageStatus.DONE,
        chunk_count=3,
    )
    assert det.needs_reprocessing(m.resource_id) is False


def test_modified_detected(registry_factory, tmp_path, sample_file):
    reg = registry_factory(tmp_path)
    m = _register(reg, sample_file)
    sample_file.write_text("changed bytes\n", encoding="utf-8")
    det = ChangeDetector(reg.catalog, tmp_path)
    assert det.classify(m.resource_id) == ChangeType.MODIFIED
    assert det.needs_reprocessing(m.resource_id) is True


def test_missing_detected(registry_factory, tmp_path, sample_file):
    reg = registry_factory(tmp_path)
    m = _register(reg, sample_file)
    sample_file.unlink()
    det = ChangeDetector(reg.catalog, tmp_path)
    assert det.classify(m.resource_id) == ChangeType.MISSING


def test_scan_reports_new_modified_missing(registry_factory, tmp_path):
    reg = registry_factory(tmp_path)
    a = tmp_path / "a.txt"
    a.write_text("alpha\n", encoding="utf-8")
    _register(reg, a)

    # b is on disk but never registered -> NEW
    b = tmp_path / "b.txt"
    b.write_text("beta\n", encoding="utf-8")

    # modify a -> MODIFIED
    a.write_text("alpha-2\n", encoding="utf-8")

    det = ChangeDetector(reg.catalog, tmp_path)
    report = det.scan(root=tmp_path)

    assert report.summary()["modified"] == 1
    new_names = {p.name for p in report.new}
    assert "b.txt" in new_names
    # sidecar files must never be treated as content
    assert not any(".meta." in p.name for p in report.new)
    assert report.to_reprocess()  # the modified resource is queued
