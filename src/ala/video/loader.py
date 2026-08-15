"""VideoTranscriptLoader — WebVTT/SRT/JSON transcript → timestamped ContentBlocks.

A standard ``BaseLoader``, so a video transcript flows through the *exact* same
ingestion → DIR → chunking path as every other resource; the only difference is
each block carries an ``Anchor(t_start, t_end)`` instead of a page/slide. The
timestamp-aware chunker (already present) groups these by time window and every
child chunk inherits ``timestamp`` → payload → evidence → ``m:ss`` citation.
"""

from __future__ import annotations

from pathlib import Path

from ala.core.enums import DocType, ExtractionMethod
from ala.fabric.content import Anchor, BlockType
from ala.ingestion.loaders.base import BaseLoader, BlockSpec
from ala.video.models import VideoConfig
from ala.video.segmenter import SceneSegmenter
from ala.video.transcript import load_transcript


class VideoTranscriptLoader(BaseLoader):
    name = "video-transcript"
    extensions = (".vtt", ".srt")
    doc_types = (DocType.VIDEO.value,)
    extraction_method = ExtractionMethod.NATIVE_TEXT

    def __init__(self, config: VideoConfig | None = None) -> None:
        self.config = config or VideoConfig()

    def _parse(self, path: Path) -> list[BlockSpec]:
        transcript = load_transcript(path)
        segments = SceneSegmenter(self.config).segment(transcript.cues)
        specs: list[BlockSpec] = []
        for seg in segments:
            btype = BlockType.IMAGE_CAPTION if seg.kind == "ocr" else BlockType.TRANSCRIPT_SEGMENT
            specs.append(BlockSpec(
                text=seg.text,
                block_type=btype,
                anchor=Anchor(t_start=round(seg.start, 2), t_end=round(seg.end, 2)),
                meta={"modality": "video", "cue_kind": seg.kind, "clock": seg.clock},
            ))
        return specs
