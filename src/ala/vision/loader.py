"""Vision loaders — images and extracted-figure artifacts → IMAGE_CAPTION blocks.

* ``ImageLoader`` — a standalone image (.png/.jpg/…) → one ``IMAGE_CAPTION`` block
  (caption + OCR via the configured seams).
* ``FigureArtifactLoader`` — a ``.figures.jsonl`` artifact (produced by the
  FigureExtractor) → one page-anchored ``IMAGE_CAPTION`` block per figure/table, so
  each figure is individually retrievable and citable by page.

Both are standard ``BaseLoader``s, so the resource flows through the existing
ingestion → chunking → embedding → graph path unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

from ala.core.enums import DocType, ExtractionMethod
from ala.fabric.content import Anchor, BlockType
from ala.ingestion.loaders.base import BaseLoader, BlockSpec
from ala.vision.adapter import VisionAdapter
from ala.vision.models import VisionConfig


class ImageLoader(BaseLoader):
    name = "image"
    extensions = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff")
    doc_types = (DocType.OTHER.value,)
    extraction_method = ExtractionMethod.OCR if hasattr(ExtractionMethod, "OCR") \
        else ExtractionMethod.NATIVE_TEXT

    def __init__(self, config: VisionConfig | None = None, adapter: VisionAdapter | None = None) -> None:
        self.config = config or VisionConfig()
        self.adapter = adapter or VisionAdapter(self.config)

    def _parse(self, path: Path) -> list[BlockSpec]:
        asset = self.adapter.describe(path)
        text = asset.block_text() or f"[image] {path.stem}"
        return [BlockSpec(text=text, block_type=BlockType.IMAGE_CAPTION,
                          anchor=Anchor(char_start=0),
                          meta={"modality": "image", "image_kind": asset.kind,
                                "image_path": str(path)})]


class FigureArtifactLoader(BaseLoader):
    name = "figures"
    extensions = (".jsonl",)
    doc_types = (DocType.REFERENCE.value,)
    extraction_method = ExtractionMethod.NATIVE_TEXT

    def _parse(self, path: Path) -> list[BlockSpec]:
        specs: list[BlockSpec] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            f = json.loads(line)
            page = f.get("page")
            specs.append(BlockSpec(
                text=f"[{f['kind']}] {f['kind'].title()} {f['number']}: {f['caption']}",
                block_type=BlockType.IMAGE_CAPTION,
                anchor=Anchor(page=int(page) if page is not None else None),
                meta={"modality": "image", "image_kind": f["kind"],
                      "figure_number": f["number"], "source_resource": f.get("source", "")}))
        return specs
