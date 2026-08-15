"""Stage 16 — Video Adapter.

Turns videos (YouTube / MP4 / recorded lectures) into first-class, **timestamped**
LearningResources that flow through the *existing* pipeline: transcript (STT or
captions) + optional slide OCR → scene segmentation → timestamped ContentBlocks →
chunking (already timestamp-aware) → embedding → Qdrant → BM25 → concept graph →
GraphRAG. Video citations preserve `t_start` end-to-end (payload → evidence →
`m:ss` citation → Citation Explorer `#t=` link). Additive: STT/OCR/download
backends are config-selected seams; the offline path parses real WebVTT/SRT
captions with the stdlib.
"""

from ala.video.adapter import VideoAdapter
from ala.video.ingest import VideoIngestor
from ala.video.models import VideoConfig, VideoCue, VideoInfo, VideoTranscript
from ala.video.transcriber import CaptionTranscriber, Transcriber

__all__ = [
    "VideoAdapter", "VideoIngestor", "VideoTranscript", "VideoCue", "VideoInfo",
    "VideoConfig", "Transcriber", "CaptionTranscriber",
]
