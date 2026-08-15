"""Frame OCR abstraction — extract on-screen/slide text from video frames.

Real backend: ``tesseract`` (opencv frame sampling + pytesseract) with slide-change
detection (dedupe consecutive identical text). ``disabled`` (default) yields
nothing — the speech transcript alone is used. Optional deps are imported lazily;
absence never crashes the pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from ala.video.models import VideoConfig, VideoCue

log = logging.getLogger("ala.video.ocr")


@runtime_checkable
class FrameOCR(Protocol):
    name: str
    def ocr(self, source: str | Path) -> list[VideoCue]: ...


class DisabledOCR:
    name = "disabled"
    def ocr(self, source: str | Path) -> list[VideoCue]:
        return []


class TesseractOCR:
    """Sample frames every N seconds, OCR them, emit deduped slide-text cues."""
    name = "tesseract"

    def __init__(self, interval: float = 30.0) -> None:
        self.interval = interval

    def ocr(self, source: str | Path) -> list[VideoCue]:
        try:
            import cv2
            import pytesseract
        except ImportError:
            log.warning("opencv/pytesseract not installed; skipping slide OCR")
            return []
        cap = cv2.VideoCapture(str(source))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        out: list[VideoCue] = []
        prev = ""
        frame_no = 0
        step = int(self.interval * fps)
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            if frame_no % max(1, step) == 0:
                text = pytesseract.image_to_string(frame).strip()
                if text and text[:40] != prev[:40]:          # slide change
                    t = frame_no / fps
                    out.append(VideoCue(start=t, end=t + self.interval, text=text, kind="ocr"))
                    prev = text
            frame_no += 1
        cap.release()
        return out


def make_ocr(config: VideoConfig) -> FrameOCR:
    return TesseractOCR(config.ocr_frame_interval) if config.ocr.lower() == "tesseract" \
        else DisabledOCR()
