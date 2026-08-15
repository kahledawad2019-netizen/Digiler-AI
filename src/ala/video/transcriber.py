"""Transcriber abstraction (config-selected, never hardcoded).

Real backends: ``faster-whisper`` / ``whisper`` (local ASR on the video's audio)
behind the same interface as ``caption`` (use existing WebVTT/SRT/JSON captions —
the offline default, no ML dependency). ``disabled`` yields nothing. Every backend
returns timestamped ``VideoCue``s; missing optional deps raise a clear message and
never crash the pipeline (fall back to captions if present).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from ala.video.models import VideoConfig, VideoCue

log = logging.getLogger("ala.video.transcriber")


@runtime_checkable
class Transcriber(Protocol):
    name: str
    def transcribe(self, source: str | Path) -> list[VideoCue]: ...


class DisabledTranscriber:
    name = "disabled"
    def transcribe(self, source: str | Path) -> list[VideoCue]:
        return []


class CaptionTranscriber:
    """Read an existing caption/transcript file (offline default)."""
    name = "caption"

    def transcribe(self, source: str | Path) -> list[VideoCue]:
        from ala.video.transcript import load_transcript
        p = Path(source)
        if p.suffix.lower() not in (".vtt", ".srt", ".json"):
            # look for a sidecar caption next to the media file
            for ext in (".vtt", ".srt", ".json"):
                cand = p.with_suffix(ext)
                if cand.is_file():
                    p = cand
                    break
            else:
                return []
        return load_transcript(p).cues


class FasterWhisperTranscriber:
    """Local ASR via faster-whisper (real; requires the optional dependency)."""
    name = "faster-whisper"

    def __init__(self, model: str = "base", device: str = "cpu") -> None:
        self.model = model
        self.device = device

    def transcribe(self, source: str | Path) -> list[VideoCue]:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            log.warning("faster-whisper not installed; install extras or use captions")
            return CaptionTranscriber().transcribe(source)
        model = WhisperModel(self.model, device=self.device, compute_type="int8")
        segments, _info = model.transcribe(str(source))
        return [VideoCue(start=float(s.start), end=float(s.end), text=s.text.strip())
                for s in segments if s.text.strip()]


class WhisperTranscriber:
    """Local ASR via openai-whisper (real; requires the optional dependency)."""
    name = "whisper"

    def __init__(self, model: str = "base") -> None:
        self.model = model

    def transcribe(self, source: str | Path) -> list[VideoCue]:
        try:
            import whisper
        except ImportError:
            log.warning("whisper not installed; falling back to captions")
            return CaptionTranscriber().transcribe(source)
        result = whisper.load_model(self.model).transcribe(str(source))
        return [VideoCue(start=float(s["start"]), end=float(s["end"]), text=s["text"].strip())
                for s in result.get("segments", []) if s["text"].strip()]


def make_transcriber(config: VideoConfig) -> Transcriber:
    t = config.transcriber.lower()
    if t == "faster-whisper":
        return FasterWhisperTranscriber(config.whisper_model)
    if t == "whisper":
        return WhisperTranscriber(config.whisper_model)
    if t == "disabled":
        return DisabledTranscriber()
    return CaptionTranscriber()
