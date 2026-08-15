"""Stages 8-10: Academic Structure, Metadata Enrichment, Resource Packaging."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ala.core.enums import ProcessingStatus
from ala.fabric.content import BlockType
from ala.fabric.learning_resource import LearningResource
from ala.ingestion.context import PipelineContext
from ala.ingestion.result import ResourcePackage
from ala.ingestion.stages.base import BaseStage
from ala.ingestion.text.academic import AcademicStructureDetector

_WORD = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "her",
    "was", "one", "our", "out", "day", "get", "has", "him", "his", "how", "man",
    "new", "now", "old", "see", "two", "way", "who", "boy", "did", "its", "let",
    "put", "say", "she", "too", "use", "this", "that", "with", "from", "have",
    "will", "your", "they", "them", "then", "than", "when", "what", "which",
    "into", "also", "such", "each", "these", "those", "there", "their", "about",
}
_WORDS_PER_MIN = 200   # average reading speed for study-time estimate


class AcademicStructureStage(BaseStage):
    """Stage 8 — detect academic structure and enrich metadata."""

    name = "academic_structure"

    def __init__(self, detector: AcademicStructureDetector | None = None) -> None:
        self.detector = detector

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        detector = self.detector or AcademicStructureDetector(ctx.config.academic)
        structure = detector.detect(resource)
        meta = resource.metadata

        if meta.week is None and structure.week is not None:
            meta.week = structure.week
        if not meta.lecture and structure.lecture:
            meta.lecture = structure.lecture
        if not meta.topics and structure.topics:
            meta.topics = structure.topics[:20]
        if not meta.subtopics and structure.subtopics:
            meta.subtopics = structure.subtopics[:40]

        ctx.analysis["academic"] = structure.to_dict()
        ctx.add_outcome(
            self.name,
            f"week={structure.week} lecture={structure.lecture} "
            f"topics={len(structure.topics)} examples={len(structure.examples)}",
        )
        return resource


class MetadataEnrichmentStage(BaseStage):
    """Stage 9 — keywords, study-time estimate, content statistics."""

    name = "metadata_enrichment"

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        meta = resource.metadata
        full_text = resource.text()

        if not meta.pedagogy.keywords:
            meta.pedagogy.keywords = _top_keywords(full_text, k=12)

        words = len(full_text.split())
        if meta.academic.estimated_study_time_min is None and words:
            meta.academic.estimated_study_time_min = max(1, round(words / _WORDS_PER_MIN))

        stats = _block_stats(resource)
        stats["word_count"] = words
        ctx.analysis["stats"] = stats
        ctx.add_outcome(self.name, f"keywords={len(meta.pedagogy.keywords)} words={words}", **stats)
        return resource


class ResourcePackagingStage(BaseStage):
    """Stage 10 — assemble the ResourcePackage and persist to derived/."""

    name = "resource_packaging"
    critical = True

    def __init__(self, derived_root: str | Path) -> None:
        self.derived_root = Path(derived_root)

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        meta = resource.metadata
        if meta.status.processing_status != ProcessingStatus.FAILED.value:
            meta.status.processing_status = ProcessingStatus.EXTRACTED.value

        package = ResourcePackage(
            resource_id=meta.resource_id,
            resource=resource,
            clean_text=resource.text(),
            language=ctx.analysis.get("language", {}),
            academic=ctx.analysis.get("academic", {}),
            processing_history=[s.model_dump(mode="json") for s in meta.provenance.history],
            validation={
                "status": str(meta.status.validation_status),
                "outcomes": [o.to_dict() for o in ctx.outcomes],
            },
            stats=ctx.analysis.get("stats", {}),
        )
        resource.save(self.derived_root)          # canonical fabric object
        package.save(self.derived_root)            # milestone deliverable bundle
        ctx.analysis["package"] = package
        ctx.add_outcome(self.name, f"packaged -> {self.derived_root / meta.resource_id}")
        return resource


# --------------------------------------------------------------------------- #
def _top_keywords(text: str, k: int) -> list[str]:
    counts = Counter(
        w.lower() for w in _WORD.findall(text) if w.lower() not in _STOPWORDS
    )
    return [w for w, _ in counts.most_common(k)]


def _block_stats(resource: LearningResource) -> dict:
    by_type: Counter[str] = Counter(str(b.type) for b in resource.blocks)
    return {
        "block_count": resource.block_count,
        "by_type": dict(by_type),
        "heading_count": by_type.get(BlockType.HEADING.value, 0),
        "char_count": sum(len(b.text) for b in resource.blocks),
    }
