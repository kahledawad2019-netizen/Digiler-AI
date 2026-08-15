"""Stage 17 — Vision RAG tests."""

from __future__ import annotations

import json

import pytest

from ala.config.settings import load_settings
from ala.fabric.content import BlockType
from ala.vision.adapter import VisionAdapter
from ala.vision.encoder import (DisabledCaptioner, DisabledImageOCR, make_captioner,
                                make_encoder, make_ocr)
from ala.vision.figures import FigureExtractor
from ala.vision.loader import FigureArtifactLoader, ImageLoader
from ala.vision.models import ImageKind, VisionConfig


# -- figure extraction ------------------------------------------------------ #
def test_extract_figure_table_kinds():
    text = ("As we see, Figure 3: a convolutional layer applies learned filters over the image. "
            "Table 1: accuracy of each model on the test set. "
            "Diagram 2: the overall system architecture and its modules.")
    figs = FigureExtractor().extract(text, source_resource="r1", page=4)
    kinds = {f.kind for f in figs}
    assert ImageKind.FIGURE.value in kinds and ImageKind.TABLE.value in kinds
    assert ImageKind.DIAGRAM.value in kinds
    fig3 = next(f for f in figs if f.number == "3")
    assert "convolutional" in fig3.caption.lower() and fig3.page == 4


def test_extract_skips_bare_reference_and_handles_decimals():
    figs = FigureExtractor().extract("See Figure 1 above. Figure 2.1: gradient descent path over the loss surface.")
    assert [f.number for f in figs] == ["2.1"]               # bare "Figure 1" skipped; decimal kept


def test_extract_from_chunks_dedupes():
    mt = [(1, "r", "Figure 1: a plot of the loss curve during training epochs."),
          (2, "r", "Figure 1: a plot of the loss curve during training epochs.")]  # dup
    assert len(FigureExtractor().extract_from_chunks(mt)) == 1


# -- loaders ---------------------------------------------------------------- #
def test_figure_artifact_loader_pages(tmp_path):
    art = tmp_path / "r.figures.jsonl"
    art.write_text("\n".join(json.dumps(f) for f in [
        {"kind": "figure", "number": "1", "caption": "a neural net", "page": 5, "source": "r"},
        {"kind": "table", "number": "2", "caption": "results table", "page": 7, "source": "r"}]),
        encoding="utf-8")
    specs = FigureArtifactLoader()._parse(art)
    assert len(specs) == 2 and specs[0].block_type == BlockType.IMAGE_CAPTION
    assert specs[0].anchor.page == 5 and "neural net" in specs[0].text


def test_image_loader_minimal_block_offline(tmp_path):
    img = tmp_path / "architecture-diagram.png"; img.write_bytes(b"\x89PNG\r\n")
    specs = ImageLoader(VisionConfig())._parse(img)          # disabled caption/ocr
    assert specs[0].block_type == BlockType.IMAGE_CAPTION
    assert specs[0].meta["image_kind"] == ImageKind.DIAGRAM.value   # kind from filename
    assert "diagram" in specs[0].text.lower()


# -- seams ------------------------------------------------------------------ #
def test_backend_selection_and_disabled():
    assert make_captioner(VisionConfig()).name == "disabled"
    assert make_ocr(VisionConfig()).name == "disabled"
    assert make_encoder(VisionConfig()).name == "disabled"
    assert make_captioner(VisionConfig(captioner="blip")).name == "blip"
    assert DisabledCaptioner().caption("x") == "" and DisabledImageOCR().ocr_image("x") == ""


def test_vision_adapter_kind_from_filename():
    a = VisionAdapter(VisionConfig())
    assert a.describe("my-screenshot.png").kind == ImageKind.SCREENSHOT.value
    assert a.describe("loss-chart.jpg").kind == ImageKind.CHART.value


# -- real corpus integration ------------------------------------------------ #
def test_ingest_figures_real(tmp_path):
    settings = load_settings(None)
    from ala.retrieval.chunking.store import ChunkStore
    prod = ChunkStore(settings.derived_path)
    ex = FigureExtractor()
    src_rid = None
    for f in sorted(settings.derived_path.glob("*/chunks/children.text.jsonl"))[:120]:
        rid = f.parent.parent.name
        texts = prod.load_text(rid, "child")
        mt = [(m.page, rid, texts.get(m.chunk_id, "")) for m in prod.load_meta(rid, "child")]
        if ex.extract_from_chunks(mt):
            src_rid = rid
            break
    if src_rid is None:
        pytest.skip("no captioned figures found in corpus sample")

    from ala.graph.store import GraphStore
    from ala.ingestion.pipeline import IngestionPipeline
    from ala.registry.registry import ResourceRegistry
    from ala.retrieval.bm25.index import BM25Index
    from ala.retrieval.chunking.service import ChunkingService
    from ala.retrieval.embedding.factory import get_embedder
    from ala.retrieval.embedding.pipeline import EmbeddingService
    from ala.retrieval.vectorstore.indexer import VectorIndexer
    from ala.retrieval.vectorstore.qdrant_store import QdrantVectorStore
    from ala.research.ingest import IncrementalIngestor
    from ala.vision.ingest import VisionIngestor

    stg = settings.model_copy(update={"paths": settings.paths.model_copy(update={
        "derived_dir": str(tmp_path / "derived"), "raw_dir": str(tmp_path / "raw"),
        "catalog_db": str(tmp_path / "catalog.db")})})
    reg = ResourceRegistry.from_settings(stg)
    emb = get_embedder("hashing")
    vs = QdrantVectorStore(":memory:", "t_vis"); vs.ensure_collection(emb.dim)
    incr = IncrementalIngestor(
        stg, pipeline=IngestionPipeline.default(stg), chunking=ChunkingService(stg, reg),
        embedding=EmbeddingService(stg, embedder=emb, registry=reg, vector_store=None),
        vector_indexer=VectorIndexer(stg, vs, "hashing", registry=reg),
        bm25_index=BM25Index(), bm25_path=tmp_path / "bm25",
        graph_store=GraphStore(tmp_path / "graph.db"), embedder=emb,
        chunk_store=ChunkStore(stg.derived_path))
    ing = VisionIngestor(stg, config=VisionConfig(), incremental=incr, registry=reg, source_store=prod)
    try:
        out = ing.ingest_figures(src_rid)
        assert out.ok and out.n_figures >= 1 and out.n_children >= 1
        metas = ChunkStore(stg.derived_path).load_meta(out.resource_id, "child")
        assert metas and any("[" in (t or "") for t in
                             ChunkStore(stg.derived_path).load_text(out.resource_id, "child").values())
    finally:
        vs.close(); reg.close()
