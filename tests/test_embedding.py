"""Stage 4 — embedding pipeline tests (dependency-free path)."""

from __future__ import annotations

import numpy as np
import pytest

from ala.fabric.content import BlockType
from ala.fabric.learning_resource import LearningResource
from ala.retrieval.embedding import (
    EmbeddingCache,
    EmbeddingService,
    EmbeddingStore,
    HashingEmbedder,
)
from ala.retrieval.embedding.benchmark import benchmark_embedder, results_markdown
from ala.retrieval.embedding.factory import available_models, get_embedder


def test_hashing_embedder_is_deterministic_normalized_and_semantic():
    e = HashingEmbedder(dim=256)
    va, vb, vc = e.embed_documents(
        ["cats and dogs", "cats and dogs are pets", "quantum chromodynamics theory"]
    )
    a, b, c = np.array(va), np.array(vb), np.array(vc)
    assert len(va) == 256
    assert abs(np.linalg.norm(a) - 1.0) < 1e-6           # L2 normalized
    assert a @ b > a @ c                                  # similar texts are closer
    assert e.embed_query("cats and dogs") == va           # deterministic


def test_factory_and_registry():
    assert isinstance(get_embedder("hashing"), HashingEmbedder)
    assert {"hashing", "e5-small", "bge-m3", "minilm"} <= set(available_models())
    with pytest.raises(KeyError):
        get_embedder("does-not-exist")


def test_cache_persists_across_instances(tmp_path):
    c = EmbeddingCache(tmp_path, "model@v1")
    assert c.get("h1") is None
    c.put("h1", [0.1, 0.2, 0.3])
    c.flush()
    reloaded = EmbeddingCache(tmp_path, "model@v1")
    assert reloaded.get("h1") == [0.1, 0.2, 0.3]


def test_store_roundtrip_and_manifest(tmp_path, make_meta):
    from ala.retrieval.embedding.models import EmbeddingRecord

    recs = [
        EmbeddingRecord(chunk_id="r::c0", resource_id="r", vector=[0.1, 0.2],
                        model_id="hashing", version="v1", dim=2, content_hash="h0"),
        EmbeddingRecord(chunk_id="r::c1", resource_id="r", vector=[0.3, 0.4],
                        model_id="hashing", version="v1", dim=2, content_hash="h1"),
    ]
    store = EmbeddingStore(tmp_path)
    store.save("r", "hashing", "v1", 2, recs)
    man = store.load_manifest("r", "hashing")
    assert man.count == 2 and man.dim == 2 and man.version == "v1"
    ids, mat = store.load_matrix("r", "hashing")
    assert ids == ["r::c0", "r::c1"] and mat.shape == (2, 2)


def test_benchmark_produces_metrics():
    texts = [f"lesson text about topic {i % 3} and databases" for i in range(30)]
    labels = [str(i % 3) for i in range(30)]
    r = benchmark_embedder(HashingEmbedder(dim=128), texts, labels=labels)
    assert r.n_texts == 30 and r.dim == 128
    assert r.embed_time_s >= 0 and r.texts_per_s > 0
    assert r.coherence_gap is not None
    assert "model" in results_markdown([r])


def test_embedding_service_end_to_end(settings, tmp_path, mem_catalog, make_meta):
    from ala.registry.registry import ResourceRegistry
    from ala.retrieval.chunking import ChunkingService, ChunkStore

    scoped = settings.model_copy(update={"project_root": tmp_path})
    registry = ResourceRegistry(scoped, mem_catalog)
    src = tmp_path / "x.md"
    src.write_text("# Keys\n\nbody", encoding="utf-8")
    meta = registry.register(src, track="technical", course="dmv", module="w03", title="X")

    lr = LearningResource(metadata=meta)
    long_text = " ".join(f"Sentence {i} about databases and foreign keys." for i in range(40))
    lr.add_block(long_text, block_type=BlockType.PARAGRAPH, section_path=["Keys"])
    ChunkingService(scoped, registry=registry).chunk_resource(lr)

    svc = EmbeddingService(scoped, registry=registry)      # default = hashing (from config)
    records = svc.embed_resource(meta.resource_id)
    assert records and all(len(r.vector) == svc.embedder.dim for r in records)

    # manifest persisted with model/version/dim/count
    man = EmbeddingStore(scoped.derived_path).load_manifest(meta.resource_id, svc.embedder.model_id)
    assert man.count == len(records)

    # chunk metadata stamped with embedding provenance
    children = ChunkStore(scoped.derived_path).load_meta(meta.resource_id, "child")
    assert all(c.embedding_model == "hashing" and c.embedding_version for c in children)

    # resource status advanced to 'embedded'
    assert registry.catalog.get(meta.resource_id).status.processing_status == "embedded"

    # incremental: second run is a no-op
    assert svc.embed_resource(meta.resource_id) == []
