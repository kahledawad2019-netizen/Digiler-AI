# Stage 16 — Video Adapter: Benchmark

Transcript built from real lecture text (`technical.applied-dl.course-project.course-project-description`, 600 words) timed at ~150 wpm → **240.0 s** video, **67 cues** → **4 scene segments** → **6 child chunks**.

## Timestamp preservation (the core claim)

| metric | value |
|---|---|
| child chunks carrying a timestamp | **1.0** |
| retrieval query | `breaches, or non-standard liabilities in corporate` |
| returned segment timestamp | **0:00** (0.0 s) |
| citation source type | video |
| citation locator | **0:00** |
| citation deep link | `file:///C:/Windows/Temp/ala_video_lvosacyn/raw/video/lectures/vid/sample-lecture-real-text-timed-transcript.vtt#t=0` (resolvable: True) |

## Ingest per-stage latency (isolated index)

| stage | ms |
|---|---|
| transcribe | 13.2 |
| loader | 67.1 |
| chunk | 7.6 |
| embed | 75.4 |
| qdrant | 184.6 |
| bm25 | 5.7 |
| graph | 62.2 |
| **total** | **417.4** |

## Figures (`figures/`)
`video_pipeline` · `timestamp_coverage` · `segment_timeline` · `ingest_timeline`.

## Honest notes
- No real video/ASR here: the transcript is **real lecture text with synthesised (150 wpm) timestamps** to exercise the timestamp-preserving pipeline end-to-end. Real audio uses the `faster-whisper`/`whisper` backends; captions (YouTube/lecture VTT) use the offline `caption` path unchanged.
- Timestamp granularity is the chunker's time window (≈3 min), so a citation points to the start of the segment window, not the exact word.
- The benchmark ingests into an isolated `:memory:` index; production is untouched.
