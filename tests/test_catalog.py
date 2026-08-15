"""Tests for the KnowledgeCatalog repository."""

from __future__ import annotations

from ala.core.enums import DocType, Language, RecordStatus


def test_upsert_get_exists(mem_catalog, make_meta):
    m = make_meta()
    assert not mem_catalog.exists(m.resource_id)
    mem_catalog.upsert_resource(m)
    assert mem_catalog.exists(m.resource_id)
    assert mem_catalog.get(m.resource_id) == m


def test_find_by_sha256(mem_catalog, make_meta):
    m = make_meta()
    mem_catalog.upsert_resource(m)
    hits = mem_catalog.find_by_sha256("a" * 64)
    assert len(hits) == 1 and hits[0]["resource_id"] == m.resource_id


def test_filter_and_search(mem_catalog, make_meta):
    mem_catalog.upsert_resource(make_meta("technical.dmv.w03.a", doc_type=DocType.LESSON_PAGE))
    mem_catalog.upsert_resource(
        make_meta("technical.aiml.l06.b", course="aiml", module="l06", title="KNN lecture",
                  doc_type=DocType.LECTURE_SLIDES)
    )
    assert len(mem_catalog.filter(course="aiml")) == 1
    assert len(mem_catalog.filter(doc_type="lesson_page")) == 1
    assert len(mem_catalog.search("KNN")) == 1


def test_statistics(mem_catalog, make_meta):
    mem_catalog.upsert_resource(make_meta("technical.dmv.w03.a"))
    mem_catalog.upsert_resource(
        make_meta("technical.aiml.l06.b", course="aiml", module="l06", language=Language.AR)
    )
    stats = mem_catalog.statistics()
    assert stats["total_resources"] == 2
    assert stats["by_course"] == {"dmv": 1, "aiml": 1}
    assert stats["by_language"]["ar"] == 1


def test_events_and_supersede(mem_catalog, make_meta):
    old = make_meta("technical.dmv.w03.v1")
    new = make_meta("technical.dmv.w03.v2")
    mem_catalog.upsert_resource(old)
    mem_catalog.upsert_resource(new)
    mem_catalog.record_event(old.resource_id, "registered", version=1)
    mem_catalog.mark_superseded(old.resource_id, new.resource_id)

    reloaded = mem_catalog.get(old.resource_id)
    assert reloaded.lifecycle.record_status == RecordStatus.SUPERSEDED.value
    assert reloaded.lifecycle.superseded_by == new.resource_id
    assert any(e["event_type"] == "registered" for e in mem_catalog.get_events(old.resource_id))


def test_list_all_respects_record_status(mem_catalog, make_meta):
    mem_catalog.upsert_resource(make_meta("technical.dmv.w03.a"))
    mem_catalog.upsert_resource(make_meta("technical.dmv.w03.b"))
    mem_catalog.mark_superseded("technical.dmv.w03.a", "technical.dmv.w03.b")
    assert len(mem_catalog.list_all(record_status="active")) == 1
    assert len(mem_catalog.list_all(record_status=None)) == 2
