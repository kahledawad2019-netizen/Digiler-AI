"""ProjectContextService — builds and publishes the Project Context.

`build()` merges three sources into a live ProjectContext:
    1. platform.yaml  -> build/schema versions
    2. context.declared.yaml -> components + model/subsystem statuses
    3. the catalog + taxonomy -> live knowledge-base status + courses

`refresh()` writes the snapshot to contexts/project_context.yaml. It is wired as
the Registry's `on_change` hook so the published context updates automatically
whenever a resource is registered or its status changes (Task 5 requirement),
while `build()` always reflects live state on demand.
"""

from __future__ import annotations

import logging

import yaml

from ala.catalog.repository import KnowledgeCatalog
from ala.config.settings import Settings
from ala.context.models import (
    ComponentInfo,
    ConfigurationInfo,
    CourseInfo,
    KnowledgeBaseStatus,
    ProjectContext,
)
from ala.core.enums import ProcessingStatus

log = logging.getLogger("ala.context")


class ProjectContextService:
    def __init__(self, settings: Settings, catalog: KnowledgeCatalog) -> None:
        self.settings = settings
        self.catalog = catalog

    # ------------------------------------------------------------------ #
    def build(self) -> ProjectContext:
        declared = self._load_declared()
        config = ConfigurationInfo(**declared.get("configuration", {}))
        components = [ComponentInfo(**c) for c in declared.get("components", [])]

        return ProjectContext(
            build_version=self.settings.build.version,
            architecture_baseline=self.settings.build.architecture_baseline,
            schema_version=self.settings.build.schema_version,
            configuration=config,
            components=components,
            agents=[c.name for c in components if c.kind == "agent"],
            tools=[c.name for c in components if c.kind == "tool"],
            courses=self._courses(),
            knowledge_base=self._kb_status(),
        )

    def refresh(self) -> ProjectContext:
        """Build and write the snapshot to disk. Never raises to its caller."""
        ctx = self.build()
        try:
            path = self.settings.abspath(self.settings.paths.project_context)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                yaml.safe_dump(ctx.to_dict(), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            log.info("Project context refreshed: %s", ctx.summary_line())
        except OSError as exc:  # a publish failure must never break the caller
            log.warning("Could not write project_context.yaml: %s", exc)
        return ctx

    # ------------------------------------------------------------------ #
    def _load_declared(self) -> dict:
        path = self.settings.abspath(self.settings.paths.declared_context)
        if not path.is_file():
            log.warning("Declared context missing: %s", path)
            return {}
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _courses(self) -> list[CourseInfo]:
        out: list[CourseInfo] = []
        for track in self.settings.tracks.get("tracks", []):
            for course in track.get("courses", []):
                out.append(
                    CourseInfo(
                        track=track["id"],
                        course=course["id"],
                        title=course.get("title", course["id"]),
                        modules=len(course.get("modules", [])),
                    )
                )
        return out

    def _kb_status(self) -> KnowledgeBaseStatus:
        stats = self.catalog.statistics()
        by_proc = stats.get("by_processing_status", {})
        return KnowledgeBaseStatus(
            total_resources=stats.get("total_resources", 0),
            total_bytes=stats.get("total_bytes", 0),
            indexed=by_proc.get(ProcessingStatus.INDEXED.value, 0),
            pending=by_proc.get(ProcessingStatus.PENDING.value, 0),
            by_course=stats.get("by_course", {}),
            by_language=stats.get("by_language", {}),
            by_processing_status=by_proc,
            by_doc_type=stats.get("by_doc_type", {}),
            last_updated=stats.get("last_updated"),
        )

    # ------------------------------------------------------------------ #
    @classmethod
    def from_settings(cls, settings: Settings) -> "ProjectContextService":
        catalog = KnowledgeCatalog.from_settings(settings)
        catalog.initialize()
        return cls(settings, catalog)
