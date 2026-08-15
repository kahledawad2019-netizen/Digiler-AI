"""Video-adapter value types + configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VideoCue:
    """One timed segment (speech or on-screen/OCR text)."""
    start: float                    # seconds
    end: float
    text: str
    kind: str = "speech"            # speech | ocr

    @property
    def clock(self) -> str:
        m, s = divmod(int(self.start), 60)
        return f"{m}:{s:02d}"


@dataclass
class VideoInfo:
    title: str
    source: str                     # url or file path
    kind: str = "video"             # youtube | mp4 | lecture | caption
    duration: float = 0.0
    language: str = "en"


@dataclass
class VideoTranscript:
    info: VideoInfo
    cues: list[VideoCue] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.info.duration or (max((c.end for c in self.cues), default=0.0))

    def text(self) -> str:
        return " ".join(c.text for c in self.cues)

    def to_dict(self) -> dict:
        return {"info": self.info.__dict__,
                "cues": [c.__dict__ for c in self.cues], "duration": self.duration}


@dataclass
class VideoConfig:
    transcriber: str = "caption"        # caption | faster-whisper | whisper | disabled
    whisper_model: str = "base"
    ocr: str = "disabled"               # disabled | tesseract
    segment_target_words: int = 160     # ~child-chunk size per scene segment
    segment_max_gap: float = 8.0        # seconds pause → new segment
    ocr_frame_interval: float = 30.0    # sample a frame every N seconds for OCR
    track: str = "video"
    course: str = "lectures"

    @classmethod
    def from_settings(cls, settings) -> "VideoConfig":
        v = (getattr(settings, "video", None) or {}) if settings else {}
        return cls(
            transcriber=str(v.get("transcriber", "caption")),
            whisper_model=str(v.get("whisper_model", "base")),
            ocr=str(v.get("ocr", "disabled")),
            segment_target_words=int(v.get("segment_target_words", 160)),
            segment_max_gap=float(v.get("segment_max_gap", 8.0)),
            ocr_frame_interval=float(v.get("ocr_frame_interval", 30.0)),
            track=str(v.get("track", "video")),
            course=str(v.get("course", "lectures")),
        )
