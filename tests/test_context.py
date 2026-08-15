"""Tests for the Project Context (Task 5)."""

from __future__ import annotations

import yaml

from ala.context.service import ProjectContextService


def test_build_merges_declared_and_taxonomy(settings, mem_catalog):
    ctx = ProjectContextService(settings, mem_catalog).build()

    assert ctx.build_version == settings.build.version
    assert ctx.schema_version == "2.0.0"
    assert ctx.architecture_baseline == "V3"

    names = {c.name for c in ctx.components}
    assert {"Resource Fabric", "Knowledge Catalog", "Resource Registry"} <= names
    assert "Resource Registry" in ctx.implemented()
    assert "Learning Agent" in ctx.agents         # kind==agent projection
    assert "Web Search" in ctx.tools              # kind==tool projection

    course_ids = {c.course for c in ctx.courses}   # live from taxonomy
    assert {"dmv", "aiml", "eng"} <= course_ids


def test_kb_status_reflects_catalog(settings, mem_catalog, make_meta):
    assert ProjectContextService(settings, mem_catalog).build().knowledge_base.total_resources == 0
    mem_catalog.upsert_resource(make_meta())
    kb = ProjectContextService(settings, mem_catalog).build().knowledge_base
    assert kb.total_resources == 1
    assert kb.pending == 1                         # default processing_status


def test_refresh_writes_yaml_snapshot(settings, mem_catalog, tmp_path):
    scoped = settings.model_copy(deep=True)
    scoped.paths.project_context = str(tmp_path / "project_context.yaml")
    svc = ProjectContextService(scoped, mem_catalog)

    ctx = svc.refresh()
    out = tmp_path / "project_context.yaml"
    assert out.is_file()
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["architecture_baseline"] == "V3"
    assert "components" in data and "knowledge_base" in data
    assert ctx.summary_line().startswith("ALA v")


def test_registry_on_change_hook_fires(registry_factory, tmp_path, sample_file):
    calls = {"n": 0}
    reg = registry_factory(tmp_path)
    reg.on_change = lambda: calls.__setitem__("n", calls["n"] + 1)
    reg.register(sample_file, track="technical", course="dmv", module="w03", title="X")
    assert calls["n"] == 1                          # fired on registration
