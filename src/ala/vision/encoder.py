"""Vision backends behind interfaces (config-selected, real + guarded).

``VisionEncoder`` (CLIP → cross-modal image vectors), ``Captioner`` (BLIP → caption)
and ``ImageOCR`` (tesseract → on-image text). All optional deps are imported lazily
and their absence degrades gracefully (empty result) — never a crash. The offline
default is ``disabled`` for each; the FigureExtractor path needs none of them.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from ala.vision.models import VisionConfig

log = logging.getLogger("ala.vision")


# -- image → caption -------------------------------------------------------- #
@runtime_checkable
class Captioner(Protocol):
    name: str
    def caption(self, image: str | Path) -> str: ...


class DisabledCaptioner:
    name = "disabled"
    def caption(self, image: str | Path) -> str:
        return ""


class BlipCaptioner:
    name = "blip"

    def __init__(self, model: str = "Salesforce/blip-image-captioning-base") -> None:
        self.model = model

    def caption(self, image: str | Path) -> str:
        try:
            from PIL import Image
            from transformers import BlipForConditionalGeneration, BlipProcessor
        except ImportError:
            log.warning("transformers/Pillow not installed; caption disabled")
            return ""
        proc = BlipProcessor.from_pretrained(self.model)
        mdl = BlipForConditionalGeneration.from_pretrained(self.model)
        inputs = proc(Image.open(image).convert("RGB"), return_tensors="pt")
        return proc.decode(mdl.generate(**inputs, max_new_tokens=40)[0], skip_special_tokens=True)


# -- image → text (OCR) ----------------------------------------------------- #
@runtime_checkable
class ImageOCR(Protocol):
    name: str
    def ocr_image(self, image: str | Path) -> str: ...


class DisabledImageOCR:
    name = "disabled"
    def ocr_image(self, image: str | Path) -> str:
        return ""


class TesseractImageOCR:
    name = "tesseract"

    def ocr_image(self, image: str | Path) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            log.warning("pytesseract/Pillow not installed; OCR disabled")
            return ""
        return " ".join(pytesseract.image_to_string(Image.open(image)).split())


# -- image → vector (cross-modal) ------------------------------------------- #
@runtime_checkable
class VisionEncoder(Protocol):
    name: str
    def encode_image(self, image: str | Path) -> list[float]: ...


class DisabledVisionEncoder:
    name = "disabled"
    def encode_image(self, image: str | Path) -> list[float]:
        return []


class ClipVisionEncoder:
    name = "clip"

    def __init__(self, model: str = "ViT-B-32") -> None:
        self.model = model

    def encode_image(self, image: str | Path) -> list[float]:
        try:
            import open_clip
            import torch
            from PIL import Image
        except ImportError:
            log.warning("open_clip/torch not installed; CLIP encoder disabled")
            return []
        model, _, preprocess = open_clip.create_model_and_transforms(self.model, pretrained="openai")
        with torch.no_grad():
            vec = model.encode_image(preprocess(Image.open(image).convert("RGB")).unsqueeze(0))
            vec = vec / vec.norm(dim=-1, keepdim=True)
        return vec.squeeze(0).tolist()


def make_captioner(cfg: VisionConfig) -> Captioner:
    return BlipCaptioner(cfg.blip_model) if cfg.captioner.lower() == "blip" else DisabledCaptioner()


def make_ocr(cfg: VisionConfig) -> ImageOCR:
    return TesseractImageOCR() if cfg.ocr.lower() == "tesseract" else DisabledImageOCR()


def make_encoder(cfg: VisionConfig) -> VisionEncoder:
    return ClipVisionEncoder(cfg.clip_model) if cfg.encoder.lower() == "clip" else DisabledVisionEncoder()
