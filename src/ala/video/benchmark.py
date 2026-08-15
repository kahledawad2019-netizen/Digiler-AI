"""Stage 16 — Video Adapter benchmark (real corpus content, isolated index).

No real video files ship with the repo and no ASR/OCR libs are installed, so the
benchmark builds a **real WebVTT transcript from real corpus lecture text** (words
timed at a realistic ~150 wpm — the timestamps are synthesised and labelled as
such; real audio would use the FasterWhisper backend), then runs the full video
pipeline into an **isolated** index and verifies the thing that matters:
**timestamps survive end-to-end** — into chunk metadata, retrieval, and the
``m:ss`` citation / ``#t=`` deep link. Production index untouched.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ala.config.settings import Settings
from ala.video.models import VideoConfig
from ala.video.transcript import parse_captions

_WPS = 2.5           # ~150 words / minute


def run_video_benchmark(settings: Settings, *, out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage16_video")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="ala_video_"))
    vtt, src_rid, n_words = _make_vtt(settings, tmp)

    stg, ingestor, catalog = _isolated(settings, tmp)
    try:
        outcome = ingestor.ingest_video(vtt, title="Sample Lecture (real text, timed transcript)")

        from ala.retrieval.chunking.store import ChunkStore
        metas = ChunkStore(stg.derived_path).load_meta(outcome.resource_id, "child")
        with_ts = [m for m in metas if m.timestamp is not None]
        coverage = round(len(with_ts) / len(metas), 4) if metas else 0.0

        # retrieval: a phrase from the transcript returns a timestamped segment
        cues = parse_captions(vtt.read_text(encoding="utf-8"))
        mid = cues[len(cues) // 2].text if cues else "neural network"
        query = " ".join(mid.split()[:6])
        hits = ingestor._incremental.bm25_index.search(query, top_k=5)
        hit_meta = next((m for m in metas if hits and m.chunk_id == hits[0][0]), None)
        retrieved_ts = hit_meta.timestamp if hit_meta else None

        # citation: build the explorer node for that segment → m:ss + #t= link
        citation = _citation(stg, catalog, hit_meta) if hit_meta else {}

        segments = [{"start": round(c.start, 1), "end": round(c.end, 1),
                     "clock": c.clock, "words": len(c.text.split())} for c in cues]
        payload = {
            "source_resource": src_rid, "n_words": n_words, "duration_s": round(outcome.duration, 1),
            "n_cues": outcome.n_cues, "n_segments": outcome.n_segments,
            "n_children": len(metas), "timestamp_coverage": coverage,
            "retrieval": {"query": query, "returned_timestamp": retrieved_ts,
                          "clock": _clock(retrieved_ts) if retrieved_ts is not None else None},
            "citation": citation, "timings_ms": outcome.timings_ms, "total_ms": outcome.total_ms,
            "segments": segments,
        }
    finally:
        ingestor.close()
        catalog.close()

    (out / "video.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
    from ala.video import viz
    viz.render_all(payload, figs)
    (out / "VIDEO.md").write_text(_markdown(payload), encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
def _make_vtt(settings: Settings, tmp: Path) -> tuple[Path, str, int]:
    """Real lecture text → WebVTT with realistic (synthesised) timestamps."""
    from ala.retrieval.chunking.store import ChunkStore
    derived = settings.derived_path
    store = ChunkStore(derived)
    src_rid, words = "", []
    for f in sorted(derived.glob("technical.applied-dl.*/chunks/children.text.jsonl")) or \
            sorted(derived.glob("*/chunks/children.text.jsonl")):
        rid = f.parent.parent.name
        texts = store.load_text(rid, "child")
        joined = " ".join(texts.values()).split()
        if len(joined) >= 300:
            src_rid, words = rid, joined[:600]
            break
    lines = ["WEBVTT", ""]
    t = 0.0
    i = 0
    while i < len(words):
        cue = words[i:i + 9]
        dur = len(cue) / _WPS
        lines += [f"{_clock(t, ms=True)} --> {_clock(t + dur, ms=True)}", " ".join(cue), ""]
        t += dur
        i += 9
    path = tmp / "sample-lecture.vtt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path, src_rid, len(words)


def _isolated(settings: Settings, tmp: Path):
    from ala.catalog.repository import KnowledgeCatalog
    from ala.graph.store import GraphStore
    from ala.ingestion.pipeline import IngestionPipeline
    from ala.registry.registry import ResourceRegistry
    from ala.retrieval.bm25.index import BM25Index
    from ala.retrieval.chunking.service import ChunkingService
    from ala.retrieval.chunking.store import ChunkStore
    from ala.retrieval.embedding.factory import get_embedder
    from ala.retrieval.embedding.pipeline import EmbeddingService
    from ala.retrieval.vectorstore.indexer import VectorIndexer
    from ala.retrieval.vectorstore.qdrant_store import QdrantVectorStore
    from ala.research.ingest import IncrementalIngestor
    from ala.video.ingest import VideoIngestor

    stg = settings.model_copy(update={"paths": settings.paths.model_copy(update={
        "derived_dir": str(tmp / "derived"), "raw_dir": str(tmp / "raw"),
        "catalog_db": str(tmp / "catalog.db")})})
    reg = ResourceRegistry.from_settings(stg)
    embedder = get_embedder("hashing")           # fast + offline for the benchmark
    vs = QdrantVectorStore(":memory:", "video_bench"); vs.ensure_collection(embedder.dim)
    incremental = IncrementalIngestor(
        stg, pipeline=IngestionPipeline.default(stg), chunking=ChunkingService(stg, reg),
        embedding=EmbeddingService(stg, embedder=embedder, registry=reg, vector_store=None),
        vector_indexer=VectorIndexer(stg, vs, "hashing", registry=reg),
        bm25_index=BM25Index(), bm25_path=tmp / "bm25",
        graph_store=GraphStore(tmp / "graph.db"), embedder=embedder,
        chunk_store=ChunkStore(stg.derived_path))
    ingestor = VideoIngestor(stg, config=VideoConfig(), incremental=incremental, registry=reg)
    return stg, ingestor, KnowledgeCatalog.from_settings(stg)


def _citation(stg, catalog, meta) -> dict:
    from ala.explorer.explorer import CitationExplorer
    from ala.explorer.resolver import CitationResolver
    from ala.retrieval.evidence.models import EvidenceItem, EvidencePackage
    item = EvidenceItem(rank=0, chunk_id=meta.chunk_id, text="segment", retrieval_score=0.9,
                        confidence=0.9, resource_id=meta.resource_id, timestamp=meta.timestamp,
                        source_type="video", citation="")
    idx = CitationExplorer(CitationResolver(stg, catalog)).build(
        EvidencePackage(query="video", normalized_query="video", items=[item]))
    n = idx.nodes[0]
    return {"cid": n.cid, "source_type": n.source_type, "locator": n.locator,
            "link": n.link, "resolvable": n.resolvable}


def _clock(sec: float, ms: bool = False) -> str:
    if sec is None:
        return ""
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}" if ms else f"{int(m)}:{int(s):02d}"


def _markdown(p: dict) -> str:
    c = p["citation"]; r = p["retrieval"]
    tim = "\n".join(f"| {k} | {v} |" for k, v in p["timings_ms"].items())
    return "\n".join([
        "# Stage 16 — Video Adapter: Benchmark",
        "",
        f"Transcript built from real lecture text (`{p['source_resource']}`, {p['n_words']} words) "
        f"timed at ~150 wpm → **{p['duration_s']} s** video, **{p['n_cues']} cues** → "
        f"**{p['n_segments']} scene segments** → **{p['n_children']} child chunks**.",
        "",
        "## Timestamp preservation (the core claim)",
        "",
        "| metric | value |",
        "|---|---|",
        f"| child chunks carrying a timestamp | **{p['timestamp_coverage']}** |",
        f"| retrieval query | `{r['query']}` |",
        f"| returned segment timestamp | **{r['clock']}** ({r['returned_timestamp']} s) |",
        f"| citation source type | {c.get('source_type')} |",
        f"| citation locator | **{c.get('locator')}** |",
        f"| citation deep link | `{c.get('link')}` (resolvable: {c.get('resolvable')}) |",
        "",
        "## Ingest per-stage latency (isolated index)",
        "",
        "| stage | ms |",
        "|---|---|",
        tim,
        f"| **total** | **{p['total_ms']}** |",
        "",
        "## Figures (`figures/`)",
        "`video_pipeline` · `timestamp_coverage` · `segment_timeline` · `ingest_timeline`.",
        "",
        "## Honest notes",
        "- No real video/ASR here: the transcript is **real lecture text with synthesised "
        "(150 wpm) timestamps** to exercise the timestamp-preserving pipeline end-to-end. Real "
        "audio uses the `faster-whisper`/`whisper` backends; captions (YouTube/lecture VTT) use "
        "the offline `caption` path unchanged.",
        "- Timestamp granularity is the chunker's time window (≈3 min), so a citation points to the "
        "start of the segment window, not the exact word.",
        "- The benchmark ingests into an isolated `:memory:` index; production is untouched.",
        "",
    ])
