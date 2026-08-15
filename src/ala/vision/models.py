"""Vision-RAG value types + configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from ala.core.enums import _StrEnum


class ImageKind(_StrEnum):
    FIGURE = "figure"
    TABLE = "table"
    DIAGRAM = "diagram"
    CHART = "chart"
    SCREENSHOT = "screenshot"
    IMAGE = "image"


@dataclass
class VisionConfig:
    encoder: str = "disabled"           # disabled | clip  (cross-modal vectors)
    captioner: str = "disabled"         # disabled | blip  (image → caption)
    ocr: str = "disabled"               # disabled | tesseract (image → text)
    clip_model: str = "ViT-B-32"
    blip_model: str = "Salesforce/blip-image-captioning-base"
    min_caption_words: int = 3          # a figure marker needs a real caption
    max_caption_chars: int = 220
    track: str = "vision"
    course: str = "figures"

    @classmethod
    def from_settings(cls, settings) -> "VisionConfig":
        v = (getattr(settings, "vision", None) or {}) if settings else {}
        return cls(
            encoder=str(v.get("encoder", "disabled")),
            captioner=str(v.get("captioner", "disabled")),
            ocr=str(v.get("ocr", "disabled")),
            clip_model=str(v.get("clip_model", "ViT-B-32")),
            blip_model=str(v.get("blip_model", "Salesforce/blip-image-captioning-base")),
            min_caption_words=int(v.get("min_caption_words", 3)),
            max_caption_chars=int(v.get("max_caption_chars", 220)),
            track=str(v.get("track", "vision")),
            course=str(v.get("course", "figures")),
        )


@dataclass
class ImageAsset:
    """A standalone image to be captioned/OCR'd into a searchable block."""
    path: str
    kind: str = ImageKind.IMAGE.value
    caption: str = ""
    ocr_text: str = ""
    alt: str = ""

    def block_text(self) -> str:
        parts = [f"[{self.kind}]"]
        if self.caption:
            parts.append(self.caption)
        if self.ocr_text:
            parts.append(self.ocr_text)
        if not self.caption and not self.ocr_text and self.alt:
            parts.append(self.alt)
        return " ".join(parts).strip()
