"""Stage 16 — Video Adapter tests.

Unit tests (transcript parsing, segmentation, loader, transcriber) are synthetic;
the ingestion test runs the real pipeline offline into an isolated index and
verifies timestamps survive into chunk metadata (the core guarantee).
"""

from __future__ import annotations

from pathlib import Path

from ala.config.settings import load_settings
from ala.fabric.content import BlockType
from ala.video.loader import VideoTranscriptLoader
from ala.video.models import VideoConfig
from ala.video.segmenter import SceneSegmenter
from ala.video.transcriber import CaptionTranscriber, DisabledTranscriber, make_transcriber
from ala.video.transcript import parse_captions, parse_json, write_vtt
from ala.video.models import VideoCue, VideoInfo, VideoTranscript

_VTT = """WEBVTT

00:00:00.000 --> 00:00:04.000
Gradient descent minimises a loss function.

00:00:04.000 --> 00:00:09.500
It follows the negative gradient to train neural networks.

00:00:30.000 --> 00:00:34.000
Convolutional neural networks use pooling for images.
"""

_SRT = """1
00:00:00,000 --> 00:00:03,000
Hello world.

2
00:00:03,000 --> 00:00:06,000
Second line here.
"""


# -- transcript parsing ----------------------------------------------------- #
def test_parse_webvtt_timestamps():
    cues = parse_captions(_VTT)
    assert len(cues) == 3
    assert cues[0].start == 0.0 and cues[1].start == 4.0 and cues[2].start == 30.0
    assert "gradient" in cues[0].text.lower() and cues[0].clock == "0:00"


def test_parse_srt():
    cues = parse_captions(_SRT)
    assert len(cues) == 2 and cues[1].start == 3.0


def test_parse_json_and_roundtrip():
    cues = parse_json('[{"start":1.0,"end":2.0,"text":"one"},{"start":2.0,"end":3.0,"text":"two"}]')
    assert [c.text for c in cues] == ["one", "two"]
    vtt = write_vtt(VideoTranscript(VideoInfo("t", "s"), cues))
    assert "-->" in vtt and "one" in vtt
    assert len(parse_captions(vtt)) == 2                     # round-trips


# -- segmentation ----------------------------------------------------------- #
def test_scene_segmentation_by_gap():
    cues = parse_captions(_VTT)
    segs = SceneSegmenter(VideoConfig(segment_target_words=100, segment_max_gap=8.0)).segment(cues)
    # the 20s gap before the 3rd cue forces a new segment
    assert len(segs) == 2
    assert segs[0].start == 0.0 and segs[1].start == 30.0


def test_ocr_cue_marked_as_slide():
    cues = [VideoCue(0, 4, "spoken words here now", "speech"),
            VideoCue(2, 5, "SLIDE TITLE TEXT", "ocr")]
    segs = SceneSegmenter(VideoConfig()).segment(cues)
    assert any(s.text.startswith("[slide]") for s in segs)


# -- loader ----------------------------------------------------------------- #
def test_loader_emits_timestamped_blocks(tmp_path):
    f = tmp_path / "lecture.vtt"; f.write_text(_VTT, encoding="utf-8")
    specs = VideoTranscriptLoader(VideoConfig(segment_target_words=100))._parse(f)
    assert specs and all(s.anchor.t_start is not None for s in specs)
    assert specs[0].block_type == BlockType.TRANSCRIPT_SEGMENT
    assert specs[0].anchor.t_start == 0.0


# -- transcriber selection -------------------------------------------------- #
def test_transcriber_selection_and_caption(tmp_path):
    assert make_transcriber(VideoConfig(transcriber="disabled")).name == "disabled"
    assert make_transcriber(VideoConfig()).name == "caption"
    assert DisabledTranscriber().transcribe("x") == []
    f = tmp_path / "c.vtt"; f.write_text(_VTT, encoding="utf-8")
    assert len(CaptionTranscriber().transcribe(f)) == 3


# -- real pipeline (isolated) ----------------------------------------------- #
def test_video_ingest_preserves_timestamps(tmp_path):
    settings = load_settings(None)
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

    # a longer transcript so several timestamped chunks are produced
    lines = ["WEBVTT", ""]
    t = 0.0
    for i in range(40):
        lines += [f"00:00:{int(t):02d}.000 --> 00:00:{int(t)+3:02d}.000",
                  f"segment {i} about neural networks gradient descent and convolution training", ""]
        t += 3
    vtt = tmp_path / "lec.vtt"; vtt.write_text("\n".join(lines), encoding="utf-8")

    stg = settings.model_copy(update={"paths": settings.paths.model_copy(update={
        "derived_dir": str(tmp_path / "derived"), "raw_dir": str(tmp_path / "raw"),
        "catalog_db": str(tmp_path / "catalog.db")})})
    reg = ResourceRegistry.from_settings(stg)
    emb = get_embedder("hashing")
    vs = QdrantVectorStore(":memory:", "t_vid"); vs.ensure_collection(emb.dim)
    incr = IncrementalIngestor(
        stg, pipeline=IngestionPipeline.default(stg), chunking=ChunkingService(stg, reg),
        embedding=EmbeddingService(stg, embedder=emb, registry=reg, vector_store=None),
        vector_indexer=VectorIndexer(stg, vs, "hashing", registry=reg),
        bm25_index=BM25Index(), bm25_path=tmp_path / "bm25",
        graph_store=GraphStore(tmp_path / "graph.db"), embedder=emb,
        chunk_store=ChunkStore(stg.derived_path))
    ing = VideoIngestor(stg, config=VideoConfig(), incremental=incr, registry=reg)
    try:
        out = ing.ingest_video(vtt, title="Neural Networks Lecture")
        assert out.ok and out.n_segments >= 1
        metas = ChunkStore(stg.derived_path).load_meta(out.resource_id, "child")
        assert metas and all(m.timestamp is not None for m in metas)   # timestamps preserved
        assert incr.bm25_index.search("gradient descent convolution", top_k=3)  # searchable
    finally:
        vs.close(); reg.close()
