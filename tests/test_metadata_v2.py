"""Tests for the Milestone 1.5 metadata additions."""

from __future__ import annotations

from ala.core.enums import RelationSource, RelationType, SourceTier, StageStatus
from ala.metadata.schema import ResourceMetadata, VideoInfo, WebInfo


def test_academic_block_defaults_and_set(make_meta):
    m = make_meta()
    assert m.academic.lab_required is False
    m.academic.course_code = "DS201"
    m.academic.instructor = "Dr. X"
    row = m.to_catalog_row()
    assert row["course_code"] == "DS201"
    assert row["instructor"] == "Dr. X"
    assert row["lab_required"] == 0


def test_difficulty_score_lives_in_pedagogy(make_meta):
    m = make_meta()
    m.pedagogy.difficulty_score = 0.8
    assert m.to_catalog_row()["difficulty_score"] == 0.8


def test_processing_history_appends(make_meta):
    m = make_meta()
    m.add_processing_step("extract", tool="pypdf", version="4.2", duration_ms=120)
    m.add_processing_step("embed", tool="e5", status=StageStatus.DONE)
    steps = m.provenance.history
    assert [s.step for s in steps] == ["extract", "embed"]
    assert steps[0].tool == "pypdf" and steps[0].duration_ms == 120


def test_typed_relationships_dedupe(make_meta):
    m = make_meta()
    m.add_relationship(RelationType.DEPENDS_ON, "technical.dmv.w02.ddl")
    m.add_relationship(RelationType.DEPENDS_ON, "technical.dmv.w02.ddl")  # dup ignored
    m.add_relationship(
        RelationType.SIMILAR_TO, "technical.dmv.w04.dml", source=RelationSource.DERIVED,
        confidence=0.9,
    )
    assert len(m.relationships) == 2
    sim = [r for r in m.relationships if r.type == RelationType.SIMILAR_TO][0]
    assert sim.source == RelationSource.DERIVED and sim.confidence == 0.9


def test_video_and_web_are_nullable_and_flagged(make_meta):
    plain = make_meta()
    assert plain.video is None and plain.web is None
    assert plain.to_catalog_row()["has_video"] == 0

    vid = make_meta("technical.aiml.l06.knn-video", video=VideoInfo(
        video_id="abc", channel="Digilians", asr_source="whisper"))
    assert vid.to_catalog_row()["has_video"] == 1

    web = make_meta("technical.dmv.ref.pandas-web", web=WebInfo(
        domain="pandas.pydata.org", source_tier=SourceTier.OFFICIAL))
    assert web.web.source_tier == SourceTier.OFFICIAL.value


def test_v2_round_trip(make_meta):
    m = make_meta(video=VideoInfo(video_id="x"))
    m.add_relationship(RelationType.EXTENDS, "technical.dmv.w01.intro")
    m.add_processing_step("ocr", tool="tesseract")
    restored = ResourceMetadata.from_dict(m.to_dict())
    assert restored == m
