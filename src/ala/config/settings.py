"""Typed settings loaded from ``config/platform.yaml`` + taxonomy files.

The rest of the platform depends on this module rather than on raw file paths or
literals. Paths in the YAML are project-root-relative and resolved to absolute
here exactly once.

Resolution order for the config file:
    1. explicit ``config_path`` argument
    2. ``ALA_CONFIG`` environment variable
    3. ``<project_root>/config/platform.yaml``
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ala.core.exceptions import ConfigError


# --------------------------------------------------------------------------- #
# Project-root discovery
# --------------------------------------------------------------------------- #
def find_project_root(start: Path | None = None) -> Path:
    """Walk upward from ``start`` (or cwd, then this file) to find the repo root.

    The root is the first ancestor containing ``pyproject.toml``. This works for
    both an editable install and running straight from a checkout.
    """
    candidates = [start] if start else []
    candidates += [Path.cwd(), Path(__file__).resolve()]
    for base in candidates:
        base = base.resolve()
        for parent in [base, *base.parents]:
            if (parent / "pyproject.toml").is_file():
                return parent
    raise ConfigError("Could not locate project root (no pyproject.toml found upward).")


# --------------------------------------------------------------------------- #
# Config sub-models (mirror platform.yaml)
# --------------------------------------------------------------------------- #
class BuildConfig(BaseModel):
    version: str = "0.0.0"
    architecture_baseline: str = "V3"
    schema_version: str = "1.0.0"


class PathsConfig(BaseModel):
    knowledge_base_root: str
    raw_dir: str
    derived_dir: str
    incoming_dir: str
    quarantine_dir: str
    taxonomy_dir: str
    catalog_db: str
    schemas_dir: str
    legacy_corpus: str
    contexts_dir: str = "contexts"
    declared_context: str = "contexts/context.declared.yaml"
    project_context: str = "contexts/project_context.yaml"


class CatalogConfig(BaseModel):
    journal_mode: str = "WAL"
    store_full_json: bool = True


class SidecarConfig(BaseModel):
    format: str = "json"
    suffix: str = ".meta.json"


class MetadataConfig(BaseModel):
    supported_languages: list[str] = Field(default_factory=lambda: ["en"])
    default_language: str = "en"
    pipeline_version: str = "0.1.0"


class ChangeDetectionConfig(BaseModel):
    strategy: str = "sha256"
    hash_chunk_bytes: int = 1024 * 1024


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


class Settings(BaseModel):
    """Fully-resolved runtime settings. Immutable after load."""

    project_root: Path
    config_path: Path
    build: BuildConfig
    paths: PathsConfig
    catalog: CatalogConfig
    sidecar: SidecarConfig
    metadata: MetadataConfig
    change_detection: ChangeDetectionConfig
    logging: LoggingConfig

    # Parsed taxonomy (loaded lazily from taxonomy_dir).
    tracks: dict[str, Any] = Field(default_factory=dict)
    languages: dict[str, Any] = Field(default_factory=dict)

    # Raw ingestion block (parsed into PipelineConfig by the ingestion package).
    ingestion: dict[str, Any] = Field(default_factory=dict)

    # Raw retrieval block (parsed into ChunkingConfig etc. by the retrieval package).
    retrieval: dict[str, Any] = Field(default_factory=dict)

    # Raw graph block (concept-graph config).
    graph: dict[str, Any] = Field(default_factory=dict)

    # Raw GraphRAG block (Stage 12 generation-layer config).
    graphrag: dict[str, Any] = Field(default_factory=dict)

    # Raw Research-Mode block (Stage 14 web-search + knowledge-growth config).
    research: dict[str, Any] = Field(default_factory=dict)

    # Raw Video-Adapter block (Stage 16 transcription/OCR/segmentation config).
    video: dict[str, Any] = Field(default_factory=dict)

    # Raw Vision-RAG block (Stage 17) + Student-Model block (Stage 18).
    vision: dict[str, Any] = Field(default_factory=dict)
    student: dict[str, Any] = Field(default_factory=dict)

    # Raw Learning-Analytics-Dashboard block (Stage 19) + Study-Planner block (Stage 20).
    dashboard: dict[str, Any] = Field(default_factory=dict)
    planner: dict[str, Any] = Field(default_factory=dict)

    # Raw RL-Adaptive-Learning block (Stage 21 contextual-bandit policy).
    rl: dict[str, Any] = Field(default_factory=dict)

    # Raw AI-Agents block (Stage 22) + Function-Calling block (Stage 23).
    agents: dict[str, Any] = Field(default_factory=dict)
    tools: dict[str, Any] = Field(default_factory=dict)

    # Raw LLM block (production Ollama provider abstraction).
    llm: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    # -- absolute path helpers -------------------------------------------- #
    def abspath(self, rel: str) -> Path:
        """Resolve a project-root-relative path to absolute."""
        p = Path(rel)
        return p if p.is_absolute() else (self.project_root / p)

    @property
    def catalog_db_path(self) -> Path:
        return self.abspath(self.paths.catalog_db)

    @property
    def raw_path(self) -> Path:
        return self.abspath(self.paths.raw_dir)

    @property
    def derived_path(self) -> Path:
        return self.abspath(self.paths.derived_dir)

    @property
    def legacy_corpus_path(self) -> Path:
        return self.abspath(self.paths.legacy_corpus)

    def valid_track_ids(self) -> set[str]:
        return {t["id"] for t in self.tracks.get("tracks", [])}

    def valid_course_ids(self) -> set[str]:
        ids: set[str] = set()
        for t in self.tracks.get("tracks", []):
            ids.update(c["id"] for c in t.get("courses", []))
        return ids


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #
def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Malformed YAML in {path}: {exc}") from exc


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load and validate settings. See module docstring for resolution order."""
    root = find_project_root()
    if config_path is None:
        env = os.environ.get("ALA_CONFIG")
        config_path = Path(env) if env else (root / "config" / "platform.yaml")
    config_path = Path(config_path)
    if not config_path.is_absolute():
        config_path = root / config_path

    raw = _read_yaml(config_path)

    settings = Settings(
        project_root=root,
        config_path=config_path,
        build=BuildConfig(**raw.get("build", {})),
        paths=PathsConfig(**raw["paths"]),
        catalog=CatalogConfig(**raw.get("catalog", {})),
        sidecar=SidecarConfig(**raw.get("sidecar", {})),
        metadata=MetadataConfig(**raw.get("metadata", {})),
        change_detection=ChangeDetectionConfig(**raw.get("change_detection", {})),
        logging=LoggingConfig(**raw.get("logging", {})),
        ingestion=raw.get("ingestion", {}),
        retrieval=raw.get("retrieval", {}),
        graph=raw.get("graph", {}),
        graphrag=raw.get("graphrag", {}),
        research=raw.get("research", {}),
        video=raw.get("video", {}),
        vision=raw.get("vision", {}),
        student=raw.get("student", {}),
        dashboard=raw.get("dashboard", {}),
        planner=raw.get("planner", {}),
        rl=raw.get("rl", {}),
        agents=raw.get("agents", {}),
        tools=raw.get("tools", {}),
        llm=raw.get("llm", {}),
    )

    # Load taxonomy files (best-effort; absence is a config error only when used).
    tax_dir = settings.abspath(settings.paths.taxonomy_dir)
    tracks_file = tax_dir / "tracks.yaml"
    langs_file = tax_dir / "languages.yaml"
    if tracks_file.is_file():
        settings.tracks = _read_yaml(tracks_file)
    if langs_file.is_file():
        settings.languages = _read_yaml(langs_file)

    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide cached settings for convenience in scripts/CLI."""
    return load_settings()
