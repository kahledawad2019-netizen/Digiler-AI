# Stage 16 — Video Adapter

Turns videos (YouTube / MP4 / recorded lectures) into first-class, **timestamped**
LearningResources that flow through the *existing* pipeline. The decisive property:
`t_start` survives end-to-end — into chunk metadata, the vector/BM25 payload,
evidence, the `m:ss` citation and the Citation Explorer `#t=` deep link — with **no
change** to the retrieval/graph/GraphRAG stack. Fully additive. Package:
[`src/ala/video/`](../src/ala/video/).

## Why it's mostly reuse

The Resource Fabric already models video: `Anchor.t_start/t_end`,
`BlockType.TRANSCRIPT_SEGMENT`, the **timestamp-aware chunker** (groups transcript
blocks by time window), and `ChunkMetadata.timestamp` → `build_payload` →
`EvidenceItem.timestamp`. So the Video Adapter only had to produce **timestamped
`ContentBlock`s**; everything downstream was already built.

## Architecture

```
video (YouTube / MP4 / .vtt)
   │  VideoAdapter
   ├─ Transcriber (captions | faster-whisper | whisper)  → speech cues (t_start,t_end)
   └─ FrameOCR (tesseract, optional)                     → slide cues  (t_start)
   │  SceneSegmenter → coherent timestamped scene segments
   ▼  VideoTranscriptLoader (.vtt/.srt) → LearningResource with t_start anchors
   ▼  VideoIngestor → IncrementalIngestor.ingest_resource
        chunk (timestamp-aware) → embed → Qdrant → BM25 → concept graph
   ▼  GraphRAG → evidence.timestamp → "m:ss" citation → Citation Explorer #t= link
```

## Components

- **VideoAdapter** ([adapter.py](../src/ala/video/adapter.py)) — source → transcript;
  local caption/media file or a YouTube URL (yt-dlp seam).
- **Transcriber** ([transcriber.py](../src/ala/video/transcriber.py)) — config-selected:
  `caption` (offline default, reads WebVTT/SRT/JSON), `faster-whisper`, `whisper`,
  `disabled`. Real ASR backends behind the interface; missing deps fall back to
  captions, never crash.
- **FrameOCR** ([ocr.py](../src/ala/video/ocr.py)) — `tesseract` (opencv frame
  sampling + slide-change detection) or `disabled`.
- **SceneSegmenter** ([segmenter.py](../src/ala/video/segmenter.py)) — merges cues
  into ~child-sized segments at word-count / pause boundaries; keeps `start`/`end`.
- **VideoTranscriptLoader** ([loader.py](../src/ala/video/loader.py)) — a standard
  `BaseLoader` for `.vtt`/`.srt` emitting `TRANSCRIPT_SEGMENT` blocks with
  `Anchor(t_start,t_end)`.
- **VideoIngestor** ([ingest.py](../src/ala/video/ingest.py)) — writes the transcript
  as a WebVTT raw artifact, builds the resource, and reuses
  `IncrementalIngestor.ingest_resource` (added additively in Stage 14) for
  chunk→embed→Qdrant→BM25→graph.

## Transcript I/O

[transcript.py](../src/ala/video/transcript.py) parses **WebVTT / SRT / JSON**
(rolling-caption de-duplication for YouTube auto-captions) and writes WebVTT — all
stdlib, so the timestamped path is fully offline.

## CLI

```powershell
ala video lecture.vtt --title "Week 6 — CNNs"          # caption file → timestamped resource
ala video https://youtu.be/xxxx                         # YouTube (needs yt-dlp)
ala video lecture.mp4                                   # ASR (needs faster-whisper)
ala video --benchmark
```

## Configuration (`config/platform.yaml → video`)

`transcriber` · `whisper_model` · `ocr` · `segment_target_words` ·
`segment_max_gap` · `ocr_frame_interval` · `track` · `course`.

## Benchmark (real corpus text, isolated index) — `reports/stage16_video/`

Real lecture text (600 words) timed at ~150 wpm → 240 s video, 67 cues → 4 scene
segments → 6 child chunks.

| metric | value |
|---|---|
| **child chunks carrying a timestamp** | **1.00** |
| retrieval returns a timestamped segment | ✓ (`0:00`) |
| citation source type | **video** |
| citation locator | **`0:00`** |
| citation deep link | `…/sample-lecture.vtt#t=0` (resolvable ✓) |
| ingest total | 417 ms (transcribe 13 · loader 67 · chunk 8 · embed 75 · qdrant 185 · bm25 6 · graph 62) |

**Timestamps survive end-to-end**, and the video citation is a clickable `#t=`
deep link — exactly the requirement.

## Visualizations (`figures/`)

`video_pipeline` · `timestamp_coverage` · `segment_timeline` · `ingest_timeline`.

## Tests

[`tests/test_video.py`](../tests/test_video.py) — WebVTT/SRT/JSON parsing +
round-trip, scene segmentation (word/gap boundaries, OCR slide cues), loader
(timestamped `TRANSCRIPT_SEGMENT` blocks), transcriber selection + caption
reading, and a **real isolated ingestion** verifying every video child chunk keeps
its timestamp. Full suite **180 passed**.

## Limitations (honest)

- **No real audio/ASR in the benchmark** — the transcript is *real lecture text with
  synthesised (150 wpm) timestamps* to exercise the pipeline; real videos use the
  `faster-whisper`/`whisper` backends (installable extras) and real captions use the
  offline `caption` path unchanged. yt-dlp / opencv / pytesseract are optional seams.
- **Timestamp granularity** is the chunker's time window (~3 min), so a citation
  points to the start of the segment window, not the exact spoken word. Finer
  granularity would tune the chunker's `_TIME_WINDOW_SEC` (a deliberate, unchanged
  constant here).
- Slide OCR needs opencv + pytesseract + the media file; disabled by default.

## Extension hooks

- **Vision RAG (17):** slide frames become `IMAGE_CAPTION` blocks via the same OCR
  seam; image embeddings plug in as a new modality.
- **Citation Explorer (15):** `#t=` links now light up automatically (the code path
  existed; this stage exercises it).
- **Student Model (18):** "videos watched" events reference these resource ids +
  timestamps.
