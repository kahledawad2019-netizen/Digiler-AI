"""Validation pipeline (Task 1 — "Validation Pipeline").

An extensible set of rules (Open/Closed: add a rule class, don't edit the
runner) that check a ResourceMetadata for structural, referential, integrity,
and state-machine consistency. Rules are pure functions of (metadata, context)
returning issues, so they are trivially unit-testable.

Two severities:
    ERROR   -> the record is not safe to index (validation_status = INVALID)
    WARNING -> usable but flagged (validation_status = WARNING)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

from ala.core.enums import (
    ExtractionMethod,
    ProcessingStatus,
    StageStatus,
    ValidationStatus,
)
from ala.core.hashing import sha256_file
from ala.metadata.schema import ResourceMetadata


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    rule: str
    severity: Severity
    message: str


@dataclass
class ValidationContext:
    """Everything a rule might need beyond the metadata itself."""

    project_root: Path | None = None          # to resolve relative file paths
    supported_languages: set[str] = field(default_factory=lambda: {"en", "ar"})
    valid_tracks: set[str] = field(default_factory=set)
    valid_courses: set[str] = field(default_factory=set)
    check_files: bool = True                    # touch the filesystem?
    verify_hash: bool = False                   # recompute sha256 (slower)


@dataclass
class ValidationResult:
    resource_id: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def status(self) -> ValidationStatus:
        if self.errors:
            return ValidationStatus.INVALID
        if self.warnings:
            return ValidationStatus.WARNING
        return ValidationStatus.VALID


class ValidationRule(Protocol):
    name: str

    def check(self, meta: ResourceMetadata, ctx: ValidationContext) -> list[ValidationIssue]:
        ...


# --------------------------------------------------------------------------- #
# Concrete rules
# --------------------------------------------------------------------------- #
class RequiredFieldsRule:
    name = "required_fields"

    def check(self, meta, ctx):
        issues = []
        if not meta.title.strip():
            issues.append(ValidationIssue(self.name, Severity.ERROR, "title is empty"))
        if not meta.file.file_name.strip():
            issues.append(ValidationIssue(self.name, Severity.ERROR, "file.file_name is empty"))
        if not meta.file.sha256:
            issues.append(
                ValidationIssue(self.name, Severity.WARNING, "file.sha256 not computed")
            )
        return issues


class LanguageRule:
    name = "language_supported"

    def check(self, meta, ctx):
        if str(meta.language) not in ctx.supported_languages:
            return [
                ValidationIssue(
                    self.name,
                    Severity.ERROR,
                    f"language '{meta.language}' not in supported {sorted(ctx.supported_languages)}",
                )
            ]
        return []


class TaxonomyRule:
    name = "taxonomy"

    def check(self, meta, ctx):
        issues = []
        if ctx.valid_tracks and meta.track not in ctx.valid_tracks:
            issues.append(
                ValidationIssue(self.name, Severity.ERROR, f"unknown track '{meta.track}'")
            )
        if ctx.valid_courses and meta.course not in ctx.valid_courses:
            issues.append(
                ValidationIssue(self.name, Severity.ERROR, f"unknown course '{meta.course}'")
            )
        return issues


class FileExistsRule:
    name = "file_exists"

    def check(self, meta, ctx):
        if not ctx.check_files or ctx.project_root is None:
            return []
        path = (ctx.project_root / meta.file.file_path).resolve()
        if not path.is_file():
            return [
                ValidationIssue(
                    self.name, Severity.ERROR, f"file not found on disk: {meta.file.file_path}"
                )
            ]
        return []


class HashIntegrityRule:
    name = "hash_integrity"

    def check(self, meta, ctx):
        if not (ctx.verify_hash and ctx.check_files and ctx.project_root):
            return []
        if not meta.file.sha256:
            return []
        path = (ctx.project_root / meta.file.file_path).resolve()
        if not path.is_file():
            return []  # FileExistsRule already reports this
        actual = sha256_file(path)
        if actual != meta.file.sha256:
            return [
                ValidationIssue(
                    self.name,
                    Severity.ERROR,
                    "sha256 mismatch: file on disk differs from recorded hash "
                    "(resource changed but not re-registered)",
                )
            ]
        return []


class StageConsistencyRule:
    """Guards the processing state machine so statuses can't lie."""

    name = "stage_consistency"

    def check(self, meta, ctx):
        issues = []
        s = meta.status
        # OCR method implies OCR must have run (or be running).
        if (
            meta.provenance.extraction_method == ExtractionMethod.OCR
            and s.ocr_status in {StageStatus.NOT_REQUIRED}
        ):
            issues.append(
                ValidationIssue(
                    self.name,
                    Severity.WARNING,
                    "extraction_method=ocr but ocr_status=not_required",
                )
            )
        # INDEXED implies embeddings done and chunks exist.
        if s.processing_status == ProcessingStatus.INDEXED:
            if s.embedding_status != StageStatus.DONE:
                issues.append(
                    ValidationIssue(
                        self.name,
                        Severity.ERROR,
                        "processing_status=indexed but embedding_status!=done",
                    )
                )
            if meta.retrieval.chunk_count <= 0:
                issues.append(
                    ValidationIssue(
                        self.name,
                        Severity.ERROR,
                        "processing_status=indexed but chunk_count=0",
                    )
                )
        return issues


class SchemaVersionRule:
    name = "schema_version"

    def __init__(self, supported: set[str]) -> None:
        self.supported = supported

    def check(self, meta, ctx):
        if meta.schema_version not in self.supported:
            return [
                ValidationIssue(
                    self.name,
                    Severity.WARNING,
                    f"schema_version {meta.schema_version} not in supported {sorted(self.supported)}",
                )
            ]
        return []


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
class ValidationPipeline:
    """Runs an ordered list of rules and aggregates their issues."""

    def __init__(self, rules: list[ValidationRule] | None = None) -> None:
        self.rules = rules if rules is not None else default_rules()

    def run(self, meta: ResourceMetadata, ctx: ValidationContext | None = None) -> ValidationResult:
        ctx = ctx or ValidationContext(check_files=False)
        result = ValidationResult(resource_id=meta.resource_id)
        for rule in self.rules:
            result.issues.extend(rule.check(meta, ctx))
        return result


def default_rules(supported_schema: set[str] | None = None) -> list[ValidationRule]:
    from ala.metadata.schema import SCHEMA_VERSION

    return [
        RequiredFieldsRule(),
        LanguageRule(),
        TaxonomyRule(),
        FileExistsRule(),
        HashIntegrityRule(),
        StageConsistencyRule(),
        SchemaVersionRule(supported_schema or {SCHEMA_VERSION}),
    ]
