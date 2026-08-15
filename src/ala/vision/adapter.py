"""VisionAdapter — a standalone image → structured, searchable ImageAsset.

Caption (BLIP) + OCR (tesseract) + kind classification into an ``ImageAsset`` whose
``block_text()`` becomes an ``IMAGE_CAPTION`` block. Backends are config-selected
seams; offline, an image with no caption/OCR still yields an honest minimal block
(``[image] <filename>``) rather than a fabricated description.
"""

from __future__ import annotations

from pathlib import Path

from ala.vision.encoder import make_captioner, make_ocr
from ala.vision.models import ImageAsset, ImageKind, VisionConfig

_KIND_HINTS = {
    "screenshot": ImageKind.SCREENSHOT, "screen": ImageKind.SCREENSHOT,
    "diagram": ImageKind.DIAGRAM, "architecture": ImageKind.DIAGRAM, "flow": ImageKind.DIAGRAM,
    "chart": ImageKind.CHART, "plot": ImageKind.CHART, "graph": ImageKind.CHART,
    "table": ImageKind.TABLE, "figure": ImageKind.FIGURE, "fig": ImageKind.FIGURE,
}


class VisionAdapter:
    def __init__(self, config: VisionConfig | None = None, captioner=None, ocr=None) -> None:
        self.config = config or VisionConfig()
        self.captioner = captioner or make_captioner(self.config)
        self.ocr = ocr or make_ocr(self.config)

    def describe(self, image: str | Path) -> ImageAsset:
        p = Path(image)
        return ImageAsset(
            path=str(p), kind=self._kind(p.stem),
            caption=self.captioner.caption(p), ocr_text=self.ocr.ocr_image(p),
            alt=p.stem.replace("-", " ").replace("_", " "))

    @staticmethod
    def _kind(stem: str) -> str:
        low = stem.lower()
        for hint, kind in _KIND_HINTS.items():
            if hint in low:
                return kind.value
        return ImageKind.IMAGE.value
