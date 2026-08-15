"""EvidenceValidator — guarantee a package is well-formed before it reaches the LLM.

Checks ordering, score/confidence ranges, citation ↔ source-type consistency
(pdf⇒page, slide⇒slide, video⇒timestamp), required fields, and missing text.
Same ERROR/WARNING model as the metadata validation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ala.retrieval.evidence.models import EvidencePackage, SourceType


class Level(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class EvidenceIssue:
    level: Level
    where: str
    message: str


@dataclass
class EvidenceValidationResult:
    issues: list[EvidenceIssue] = field(default_factory=list)

    @property
    def errors(self):
        return [i for i in self.issues if i.level is Level.ERROR]

    @property
    def warnings(self):
        return [i for i in self.issues if i.level is Level.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors


class EvidenceValidator:
    _SRC_REQUIRES = {
        SourceType.PDF.value: "page",
        SourceType.SLIDE.value: "slide",
        SourceType.VIDEO.value: "timestamp",
    }

    def validate(self, package: EvidencePackage) -> EvidenceValidationResult:
        r = EvidenceValidationResult()
        if not (0.0 <= package.overall_confidence <= 1.0):
            r.issues.append(EvidenceIssue(Level.ERROR, "package", "overall_confidence out of [0,1]"))
        if not package.items:
            r.issues.append(EvidenceIssue(Level.WARNING, "package", "no evidence items"))

        prev = None
        for i, it in enumerate(package.items):
            w = f"item[{i}]"
            if prev is not None and it.fused_score > prev + 1e-9:
                r.issues.append(EvidenceIssue(Level.ERROR, w, "items not sorted by fused_score desc"))
            prev = it.fused_score

            if not (0.0 <= it.confidence <= 1.0):
                r.issues.append(EvidenceIssue(Level.ERROR, w, "confidence out of [0,1]"))
            if not it.resource_id:
                r.issues.append(EvidenceIssue(Level.ERROR, w, "missing resource_id"))
            if not it.citation:
                r.issues.append(EvidenceIssue(Level.ERROR, w, "missing citation"))
            if not it.text.strip():
                r.issues.append(EvidenceIssue(Level.WARNING, w, "empty text (unresolved chunk?)"))

            required = self._SRC_REQUIRES.get(it.source_type)
            if required and getattr(it, required) is None:
                r.issues.append(EvidenceIssue(
                    Level.ERROR, w, f"source_type '{it.source_type}' but '{required}' is missing"))
        return r
