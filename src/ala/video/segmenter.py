"""SceneSegmenter — merge fine caption cues into coherent, timestamped segments.

Consecutive speech cues are grouped until the segment reaches the target word
count or a pause longer than ``segment_max_gap`` opens (a natural scene/topic
boundary). Each segment keeps its ``start``/``end`` so timestamps survive into
chunking and citations. OCR (slide) cues are interleaved by time.
"""

from __future__ import annotations

from ala.video.models import VideoConfig, VideoCue


class SceneSegmenter:
    def __init__(self, config: VideoConfig | None = None) -> None:
        self.config = config or VideoConfig()

    def segment(self, cues: list[VideoCue]) -> list[VideoCue]:
        speech = sorted([c for c in cues if c.kind == "speech"], key=lambda c: c.start)
        ocr = sorted([c for c in cues if c.kind == "ocr"], key=lambda c: c.start)
        cfg = self.config
        out: list[VideoCue] = []
        buf: list[VideoCue] = []
        words = 0

        def flush():
            nonlocal buf, words
            if buf:
                out.append(VideoCue(start=buf[0].start, end=buf[-1].end,
                                    text=" ".join(c.text for c in buf).strip(), kind="speech"))
            buf = []
            words = 0

        for c in speech:
            if buf and (c.start - buf[-1].end > cfg.segment_max_gap or
                        words >= cfg.segment_target_words):
                flush()
            buf.append(c)
            words += len(c.text.split())
        flush()

        # attach each OCR cue as its own segment (slide text with its timestamp)
        for c in ocr:
            out.append(VideoCue(start=c.start, end=c.end, text=f"[slide] {c.text}", kind="ocr"))
        return sorted(out, key=lambda c: c.start)
