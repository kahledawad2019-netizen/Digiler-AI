"""VideoIngestor — video → first-class, searchable LearningResource.

Obtains the transcript (VideoAdapter), writes it as a WebVTT raw artifact, builds
metadata + a timestamped LearningResource via the VideoTranscriptLoader, then runs
the **existing** downstream (chunk → embed → Qdrant → BM25 → concept graph) via
``IncrementalIngestor.ingest_resource`` — no pipeline duplicated. Timestamps flow
through to GraphRAG citations automatically.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from ala.config.settings import Settings
from ala.core import ids
from ala.core.enums import DocType, Role
from ala.video.adapter import VideoAdapter
from ala.video.loader import VideoTranscriptLoader
from ala.video.models import VideoConfig, VideoTranscript
from ala.video.transcript import write_vtt


@dataclass
class VideoIngestOutcome:
    resource_id: str
    n_cues: int
    n_segments: int
    duration: float
    timings_ms: dict = field(default_factory=dict)
    total_ms: float = 0.0
    searchable: bool = False
    ok: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class VideoIngestor:
    def __init__(self, settings: Settings, *, config: VideoConfig | None = None,
                 adapter: VideoAdapter | None = None, incremental=None, registry=None) -> None:
        self.settings = settings
        self.config = config or VideoConfig.from_settings(settings)
        self.adapter = adapter or VideoAdapter(self.config)
        self._incremental = incremental
        self._registry = registry

    # ------------------------------------------------------------------ #
    def ingest_video(self, source: str | Path, *, title: str | None = None,
                     module: str = "vid") -> VideoIngestOutcome:
        t: dict = {}
        t0 = time.perf_counter()

        with _timer(t, "transcribe"):
            transcript = self.adapter.transcribe(source, title=title)
        if not transcript.cues:
            return VideoIngestOutcome("", 0, 0, 0.0, t,
                                      round((time.perf_counter() - t0) * 1000, 1), False, False)

        vtt_path = self._write_vtt(transcript, module)
        reg = self._registry or self._make_registry()
        with _timer(t, "loader"):
            meta = reg.build_metadata(
                vtt_path, track=self.config.track, course=self.config.course, module=module,
                title=transcript.info.title, doc_type=DocType.VIDEO, role=Role.MATERIAL,
                language="en", update=True, strict=False)
            resource = VideoTranscriptLoader(self.config).load(vtt_path, meta)
            n_segments = len(resource.blocks)
            reg.commit(resource.metadata)

        incremental = self._incremental or self._make_incremental()
        outcome = incremental.ingest_resource(resource, _timings=t, _t0=t0)
        return VideoIngestOutcome(
            resource_id=outcome.resource_id, n_cues=len(transcript.cues), n_segments=n_segments,
            duration=round(transcript.duration, 1), timings_ms=outcome.timings_ms,
            total_ms=outcome.total_ms, searchable=outcome.ok, ok=outcome.ok)

    # ------------------------------------------------------------------ #
    def _write_vtt(self, transcript: VideoTranscript, module: str) -> Path:
        dest = self.settings.raw_path / self.config.track / self.config.course / module
        dest.mkdir(parents=True, exist_ok=True)
        slug = ids.slugify(transcript.info.title)[:60] or "video"
        path = dest / f"{slug}.vtt"
        path.write_text(write_vtt(transcript), encoding="utf-8")
        return path

    def _make_registry(self):
        from ala.registry.registry import ResourceRegistry
        self._registry = ResourceRegistry.from_settings(self.settings)
        return self._registry

    def _make_incremental(self):
        from ala.research.ingest import IncrementalIngestor
        self._incremental = IncrementalIngestor.from_settings(self.settings)
        return self._incremental

    def close(self) -> None:
        if self._registry is not None:
            self._registry.close()


class _timer:
    def __init__(self, store: dict, key: str) -> None:
        self.store, self.key = store, key

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.store[self.key] = round((time.perf_counter() - self.t0) * 1000, 1)
