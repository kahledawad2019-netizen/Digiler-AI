"""Shared loader scaffolding.

A concrete loader only implements ``_parse(path) -> list[BlockSpec]``; the base
class turns those specs into a ``LearningResource`` with stable block ids, sets
the extraction method, and enforces optional-dependency presence with a clear
error.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

from ala.core.enums import ExtractionMethod
from ala.fabric.content import Anchor, BlockType
from ala.fabric.learning_resource import LearningResource
from ala.ingestion.errors import LoaderError
from ala.metadata.schema import ResourceMetadata


@dataclass
class BlockSpec:
    """A loader's intermediate description of one content block."""

    text: str
    block_type: BlockType = BlockType.PARAGRAPH
    section_path: list[str] = field(default_factory=list)
    anchor: Anchor = field(default_factory=Anchor)
    language: str | None = None
    meta: dict = field(default_factory=dict)


class BaseLoader:
    """Template-method base for all loaders."""

    name: str = "base"
    extensions: tuple[str, ...] = ()
    doc_types: tuple[str, ...] = ()
    extraction_method: ExtractionMethod = ExtractionMethod.NONE
    requires: tuple[str, ...] = ()          # importable module names required

    # -- SourceAdapter contract ------------------------------------------ #
    def can_handle(self, path: Path) -> bool:
        return Path(path).suffix.lower() in self.extensions

    def load(self, path: Path, metadata: ResourceMetadata) -> LearningResource:
        self._ensure_deps()
        path = Path(path)
        resource = LearningResource.from_metadata(metadata)
        for spec in self._parse(path):
            if spec.text is None:
                continue
            resource.add_block(
                spec.text,
                block_type=spec.block_type,
                anchor=spec.anchor,
                section_path=spec.section_path,
                language=spec.language,
                meta=spec.meta,
            )
        metadata.provenance.extraction_method = self.extraction_method
        return resource

    # -- to implement ----------------------------------------------------- #
    def _parse(self, path: Path) -> list[BlockSpec]:  # pragma: no cover - abstract
        raise NotImplementedError

    # -- helpers ---------------------------------------------------------- #
    def _ensure_deps(self) -> None:
        missing = []
        for mod in self.requires:
            try:
                importlib.import_module(mod)
            except ImportError:
                missing.append(mod)
        if missing:
            raise LoaderError(
                f"{self.name} loader requires missing package(s): {', '.join(missing)}. "
                f"Install with: pip install -e \".[ingestion]\""
            )
