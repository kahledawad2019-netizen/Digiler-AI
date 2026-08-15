"""Typed ingestion configuration (parsed from platform.yaml `ingestion:`).

Keeps the pipeline configurable (no hardcoded limits, cues, or toggles) while
giving stages a typed object instead of a raw dict.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ala.config.settings import Settings


class NormalizationConfig(BaseModel):
    unicode_form: str = "NFC"
    strip_smart_quotes: bool = True
    collapse_whitespace: bool = True
    join_broken_lines: bool = True
    remove_repeated_headers_footers: bool = True
    header_footer_min_page_ratio: float = 0.5


class LanguageConfig(BaseModel):
    default: str = "en"
    min_confidence: float = 0.5


class AcademicConfig(BaseModel):
    week_patterns: list[str] = Field(default_factory=lambda: [r"week\s*0*(\d+)"])
    lecture_patterns: list[str] = Field(
        default_factory=lambda: [r"lecture\s*0*(\d+)", r"lesson\s*0*(\d+)", r"session\s*0*(\d+)"]
    )
    example_cues: list[str] = Field(default_factory=lambda: ["example"])
    exercise_cues: list[str] = Field(default_factory=lambda: ["exercise", "practice"])
    assignment_cues: list[str] = Field(default_factory=lambda: ["assignment", "homework", "project"])
    lab_cues: list[str] = Field(default_factory=lambda: ["lab", "workshop"])
    reference_cues: list[str] = Field(default_factory=lambda: ["reference", "bibliography"])


class PipelineConfig(BaseModel):
    max_file_mb: int = 150
    supported_extensions: list[str] = Field(
        default_factory=lambda: [
            ".pdf", ".pptx", ".docx", ".txt", ".md", ".markdown", ".html", ".htm", ".ipynb"
        ]
    )
    max_retries: int = 1
    normalization: NormalizationConfig = Field(default_factory=NormalizationConfig)
    language: LanguageConfig = Field(default_factory=LanguageConfig)
    academic: AcademicConfig = Field(default_factory=AcademicConfig)

    @classmethod
    def from_settings(cls, settings: Settings) -> "PipelineConfig":
        return cls(**(settings.ingestion or {}))
