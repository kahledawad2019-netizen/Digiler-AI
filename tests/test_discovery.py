"""Discovery classification + resource_id uniqueness."""

from __future__ import annotations

from ala.ingestion.discovery import ResourceDiscovery


def test_discovery_infers_classification_from_path(settings, tmp_path):
    scoped = settings.model_copy(update={"project_root": tmp_path})
    d = tmp_path / "knowledge_base" / "raw" / "technical" / "dmv" / "w03"
    d.mkdir(parents=True)
    (d / "constraints.md").write_text("# H\n\nbody", encoding="utf-8")
    jobs = ResourceDiscovery(scoped).discover()
    assert len(jobs) == 1
    c = jobs[0].classification
    assert (c.track, c.course, c.module) == ("technical", "dmv", "w03")


def test_discovery_dedupes_colliding_resource_ids(settings, tmp_path):
    scoped = settings.model_copy(update={"project_root": tmp_path})
    base = tmp_path / "knowledge_base" / "raw" / "technical" / "applied-stats" / "w02"
    base.mkdir(parents=True)
    # a chapter's slide deck and its PDF export share a stem -> would collide
    (base / "ch2-probability.pdf").write_text("x", encoding="utf-8")
    (base / "ch2-probability.pptx").write_text("x", encoding="utf-8")
    jobs = ResourceDiscovery(scoped).discover()
    slugs = sorted(j.classification.slug for j in jobs)
    assert slugs == ["ch2-probability", "ch2-probability-2"]   # disambiguated
