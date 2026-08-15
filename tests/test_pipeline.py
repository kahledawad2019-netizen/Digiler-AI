"""End-to-end ingestion pipeline integration tests."""

from __future__ import annotations

from ala.core.enums import DocType
from ala.ingestion import IngestionStatus, ResourceClassification


def _cls(title, module="w03", doc_type=DocType.LESSON_PAGE):
    return ResourceClassification(
        track="technical", course="dmv", module=module, title=title, doc_type=doc_type
    )


def test_full_pipeline_markdown(ingest_pipeline_factory, tmp_path):
    src = tmp_path / "lesson.md"
    src.write_text(
        "# Week 3 Constraints\n\nA primary key is unique.\n\n"
        "## Foreign Keys\n\n- enforce integrity\n- reference a table\n",
        encoding="utf-8",
    )
    pipe = ingest_pipeline_factory(tmp_path)
    res = pipe.ingest_path(src, _cls("Week 3 Constraints"))

    assert res.status == IngestionStatus.SUCCESS
    assert res.resource.block_count >= 3
    assert res.resource.metadata.language == "en"
    assert res.resource.metadata.status.processing_status == "extracted"
    assert res.resource.metadata.week == 3

    # package + fabric object persisted to derived/
    derived = tmp_path / "knowledge_base" / "derived" / res.resource_id
    assert (derived / "package.json").is_file()
    assert (derived / "learning_resource.json").is_file()
    assert res.package is not None and res.package.language["code"] == "en"

    # registry + catalog updated
    assert pipe.registry.catalog.exists(res.resource_id)

    # processing history captured every stage
    steps = [s.step for s in res.resource.metadata.provenance.history]
    assert "content_extraction" in steps and "resource_packaging" in steps


def test_full_pipeline_docx(ingest_pipeline_factory, tmp_path, make_docx):
    src = make_docx(tmp_path / "d.docx")
    res = ingest_pipeline_factory(tmp_path).ingest_path(src, _cls("Constraints"))
    assert res.ok
    assert any(b.type == "heading" for b in res.resource.blocks)
    assert any(b.type == "table" for b in res.resource.blocks)


def test_full_pipeline_pptx(ingest_pipeline_factory, tmp_path, make_pptx):
    src = make_pptx(tmp_path / "s.pptx")
    res = ingest_pipeline_factory(tmp_path).ingest_path(
        src, _cls("KNN", module="l06", doc_type=DocType.LECTURE_SLIDES)
    )
    assert res.ok
    assert all(b.anchor.slide == 1 for b in res.resource.blocks)


def test_unsupported_file_fails_gracefully(ingest_pipeline_factory, tmp_path):
    src = tmp_path / "x.xyz"
    src.write_text("nope", encoding="utf-8")
    res = ingest_pipeline_factory(tmp_path).ingest_path(src, _cls("x"))
    assert res.status == IngestionStatus.FAILED
    assert res.errors                      # structured error recorded — no crash


def test_directory_ingestion_isolates_failures(ingest_pipeline_factory, tmp_path):
    base = tmp_path / "knowledge_base" / "raw" / "technical" / "dmv"
    (base / "w03").mkdir(parents=True)
    (base / "w03" / "good.md").write_text("# Good\n\nbody text", encoding="utf-8")
    (base / "w04").mkdir(parents=True)
    (base / "w04" / "broken.docx").write_bytes(b"not really a docx")  # will fail extraction

    results = ingest_pipeline_factory(tmp_path).ingest_directory()
    assert len(results) == 2
    statuses = {r.status for r in results}
    assert IngestionStatus.SUCCESS in statuses     # good.md succeeded
    assert IngestionStatus.FAILED in statuses      # broken.docx failed, didn't crash the batch
