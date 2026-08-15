"""LearningResource — the one object the whole platform speaks.

It *composes* (never duplicates) the catalog descriptor ``ResourceMetadata`` and
adds the unified content: an ordered list of ``ContentBlock``. Loaders (Task 7)
produce it; chunkers/embedders/graph-builders consume it. The descriptor is
persisted in the catalog; the (potentially large) content is persisted under
``knowledge_base/derived/<resource_id>/`` — regenerable, never the source of
truth.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ala.fabric.content import Anchor, BlockType, ContentBlock
from ala.metadata.schema import ResourceMetadata

_DERIVED_FILENAME = "learning_resource.json"


class LearningResource(BaseModel):
    """Unified representation of a single learning resource (any source type)."""

    model_config = ConfigDict(extra="forbid")

    metadata: ResourceMetadata
    blocks: list[ContentBlock] = Field(default_factory=list)
    raw_text: str | None = None          # optional cached full text
    warnings: list[str] = Field(default_factory=list)  # extraction issues

    # -- proxies to the descriptor (read-only convenience) ---------------- #
    @property
    def resource_id(self) -> str:
        return self.metadata.resource_id

    @property
    def doc_type(self) -> str:
        return str(self.metadata.doc_type)

    @property
    def language(self) -> str:
        return str(self.metadata.language)

    # -- construction ----------------------------------------------------- #
    @classmethod
    def from_metadata(cls, metadata: ResourceMetadata) -> "LearningResource":
        return cls(metadata=metadata)

    def add_block(
        self,
        text: str,
        *,
        block_type: BlockType = BlockType.PARAGRAPH,
        anchor: Anchor | None = None,
        section_path: list[str] | None = None,
        language: str | None = None,
        meta: dict | None = None,
    ) -> ContentBlock:
        """Append a block, auto-assigning a stable id and reading order."""
        order = len(self.blocks)
        block = ContentBlock(
            block_id=f"{self.resource_id}#b{order:04d}",
            order=order,
            type=block_type,
            text=text,
            language=language,
            anchor=anchor or Anchor(),
            section_path=section_path or [],
            meta=meta or {},
        )
        self.blocks.append(block)
        return block

    # -- access ----------------------------------------------------------- #
    @property
    def block_count(self) -> int:
        return len(self.blocks)

    def text(self, sep: str = "\n\n") -> str:
        """Concatenated block text (or the cached raw_text if no blocks)."""
        if self.blocks:
            return sep.join(b.text for b in self.blocks if b.text.strip())
        return self.raw_text or ""

    def by_type(self, block_type: BlockType) -> list[ContentBlock]:
        want = str(block_type)
        return [b for b in self.blocks if str(b.type) == want]

    def languages(self) -> set[str]:
        """Distinct languages across blocks (falls back to the resource language)."""
        langs = {str(b.language) for b in self.blocks if b.language}
        return langs or {self.language}

    # -- serialization ---------------------------------------------------- #
    def to_dict(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> "LearningResource":
        return cls.model_validate(data)

    def save(self, derived_root: str | Path) -> Path:
        """Persist to ``<derived_root>/<resource_id>/learning_resource.json``."""
        out_dir = Path(derived_root) / self.resource_id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / _DERIVED_FILENAME
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, derived_root: str | Path, resource_id: str) -> "LearningResource":
        path = Path(derived_root) / resource_id / _DERIVED_FILENAME
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
