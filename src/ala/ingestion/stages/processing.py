"""Stages 5-7: Cleaning & Normalization, Language Detection, Structural Parsing."""

from __future__ import annotations

from ala.fabric.content import BlockType
from ala.fabric.learning_resource import LearningResource
from ala.ingestion.context import PipelineContext
from ala.ingestion.stages.base import BaseStage
from ala.ingestion.text import normalize
from ala.ingestion.text.language import LanguageDetector, ScriptLanguageDetector


class CleaningNormalizationStage(BaseStage):
    """Stage 5 — normalize block text (type-aware) and strip page headers/footers."""

    name = "normalization"

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        cfg = ctx.config.normalization

        # (a) type-aware per-block normalization
        for block in resource.blocks:
            block.text = normalize.normalize_block_text(
                block.text, block_type=block.type, config=cfg
            )

        # (b) cross-page header/footer removal (blocks carrying a page anchor)
        removed = 0
        if cfg.remove_repeated_headers_footers:
            page_lines: dict[int, list[str]] = {}
            for block in resource.blocks:
                page = block.anchor.page
                if page is None:
                    continue
                lines = block.text.split("\n")
                page_lines.setdefault(page, [])
                if lines:
                    page_lines[page].append(lines[0])
                    page_lines[page].append(lines[-1])
            repeated = normalize.find_repeated_lines(
                list(page_lines.values()), cfg.header_footer_min_page_ratio
            )
            if repeated:
                for block in resource.blocks:
                    if block.anchor.page is None:
                        continue
                    kept = [ln for ln in block.text.split("\n") if ln.strip() not in repeated]
                    new_text = "\n".join(kept).strip()
                    if new_text != block.text:
                        removed += 1
                        block.text = new_text

        # drop blocks emptied by normalization
        resource.blocks = [b for b in resource.blocks if b.text.strip()]
        ctx.add_outcome(self.name, f"normalized {len(resource.blocks)} blocks; "
                                   f"stripped header/footer from {removed}")
        return resource


class LanguageDetectionStage(BaseStage):
    """Stage 6 — detect language + confidence (resource-level and per block)."""

    name = "language_detection"

    def __init__(self, detector: LanguageDetector | None = None) -> None:
        self.detector = detector or ScriptLanguageDetector()

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        result = self.detector.detect(resource.text())
        min_conf = ctx.config.language.min_confidence

        if result.confidence >= min_conf and result.language in ctx.settings.metadata.supported_languages:
            resource.metadata.language = result.language

        # per-block language (captures code-switching) for blocks with enough letters
        for block in resource.blocks:
            if len(block.text) >= 20:
                br = self.detector.detect(block.text)
                block.language = br.language
                block.meta["lang_confidence"] = br.confidence

        ctx.analysis["language"] = {
            "code": result.language,
            "confidence": result.confidence,
            "scores": result.scores,
        }
        ctx.add_outcome(self.name, f"language={result.language} conf={result.confidence}",
                        **ctx.analysis["language"])
        return resource


class StructuralParsingStage(BaseStage):
    """Stage 7 — refine structure: promote heading-like paragraphs (e.g. from PDF).

    Loaders that carry real structure (docx/pptx/html/markdown) already tag
    headings; this stage rescues headings from formats that don't (pdf/text).
    """

    name = "structural_parsing"

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        promoted = 0
        for block in resource.blocks:
            if block.type == BlockType.PARAGRAPH.value and _looks_like_heading(block.text):
                block.type = BlockType.HEADING.value
                block.meta["promoted_heading"] = True
                promoted += 1
        ctx.add_outcome(self.name, f"promoted {promoted} heading(s)")
        return resource


def _looks_like_heading(text: str) -> bool:
    t = text.strip()
    if not t or "\n" in t:
        return False
    words = t.split()
    if len(t) > 70 or len(words) > 10:
        return False
    if t[-1] in ".!?,;:":
        return False
    if not t[0].isalnum():
        return False
    if t.isupper():
        return True
    # Mostly-capitalized short phrase (Title Case, allowing small words).
    capitalized = sum(1 for w in words if w[:1].isupper())
    return len(words) <= 8 and capitalized / len(words) >= 0.6
