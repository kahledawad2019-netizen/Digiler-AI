"""Stage 5 — Qdrant vector store tests (in-memory, no server)."""

from __future__ import annotations

import pytest

from ala.retrieval.vectorstore import QdrantVectorStore, VectorPoint
from ala.retrieval.vectorstore.qdrant_store import VectorStoreError


def _store(dim=3):
    s = QdrantVectorStore(":memory:", "t", "cosine", dim=dim)
    s.ensure_collection(dim, recreate=True)
    return s


def test_upsert_search_and_count():
    s = _store(3)
    assert s.upsert([
        VectorPoint("r::c0", [1, 0, 0], {"resource_id": "r", "course": "dmv"}),
        VectorPoint("r::c1", [0, 1, 0], {"resource_id": "r", "course": "dmv"}),
        VectorPoint("r2::c0", [0.9, 0.1, 0], {"resource_id": "r2", "course": "aiml"}),
    ]) == 3
    assert s.count() == 3
    hits = s.search([1, 0, 0], top_k=2)
    assert hits[0].chunk_id == "r::c0" and hits[0].score > 0.9
    s.close()


def test_metadata_filtering_value_and_any():
    s = _store(3)
    s.upsert([
        VectorPoint("r::c0", [1, 0, 0], {"resource_id": "r", "course": "dmv"}),
        VectorPoint("r2::c0", [1, 0, 0], {"resource_id": "r2", "course": "aiml"}),
    ])
    only = s.search([1, 0, 0], top_k=5, filters={"course": "aiml"})
    assert len(only) == 1 and only[0].payload["course"] == "aiml"
    both = s.search([1, 0, 0], top_k=5, filters={"course": ["dmv", "aiml"]})
    assert len(both) == 2
    s.close()


def test_delete_by_id_and_by_resource():
    s = _store(3)
    s.upsert([
        VectorPoint("r::c0", [1, 0, 0], {"resource_id": "r"}),
        VectorPoint("r::c1", [0, 1, 0], {"resource_id": "r"}),
        VectorPoint("r2::c0", [0, 0, 1], {"resource_id": "r2"}),
    ])
    assert s.delete(["r::c0"]) == 1 and s.count() == 2
    assert s.delete_by_resource("r") == 1 and s.count() == 1
    s.close()


def test_upsert_is_idempotent():
    s = _store(3)
    p = [VectorPoint("r::c0", [1, 0, 0], {"resource_id": "r"})]
    s.upsert(p)
    s.upsert(p)                       # same chunk_id -> same point -> update, not duplicate
    assert s.count() == 1
    s.close()


def test_vector_validation_rejects_bad_vectors():
    s = _store(3)
    with pytest.raises(VectorStoreError):
        s.upsert([VectorPoint("x", [1, 0], {})])          # wrong dim
    with pytest.raises(VectorStoreError):
        s.search([1, 0])                                   # wrong dim
    s.close()


def test_health_and_stats():
    s = _store(3)
    s.upsert([VectorPoint("r::c0", [1, 0, 0], {})])
    h = s.health()
    assert h["ok"] and h["points"] == 1
    st = s.stats()
    assert st["points"] == 1 and st["dim"] == 3
    s.close()


def test_payload_and_point_id():
    from ala.retrieval.chunking.models import ChunkKind, ChunkMetadata, ChunkType
    from ala.retrieval.vectorstore.payload import build_payload, point_id

    m = ChunkMetadata(chunk_id="technical.dmv.w03.x::c0", resource_id="technical.dmv.w03.x",
                      kind=ChunkKind.CHILD, order=0, chunk_type=ChunkType.PARAGRAPH,
                      page=5, heading="Keys")
    pl = build_payload(m)
    assert pl["track"] == "technical" and pl["course"] == "dmv" and pl["page"] == 5
    assert pl["chunk_id"] == m.chunk_id
    assert point_id("a") == point_id("a") and point_id("a") != point_id("b")


def test_embedding_service_populates_qdrant(settings, tmp_path, mem_catalog, make_meta):
    from ala.fabric.content import BlockType
    from ala.fabric.learning_resource import LearningResource
    from ala.registry.registry import ResourceRegistry
    from ala.retrieval.chunking import ChunkingService
    from ala.retrieval.embedding import EmbeddingService

    scoped = settings.model_copy(update={"project_root": tmp_path})
    registry = ResourceRegistry(scoped, mem_catalog)
    src = tmp_path / "x.md"
    src.write_text("# H\n\nbody", encoding="utf-8")
    meta = registry.register(src, track="technical", course="dmv", module="w03", title="X")
    lr = LearningResource(metadata=meta)
    lr.add_block(" ".join(f"Sentence {i} about databases." for i in range(30)),
                 block_type=BlockType.PARAGRAPH, section_path=["H"])
    ChunkingService(scoped, registry=registry).chunk_resource(lr)

    store = QdrantVectorStore(":memory:", "c", "cosine")
    EmbeddingService(scoped, registry=registry, vector_store=store).embed_resource(meta.resource_id)

    assert store.count() > 0
    assert registry.catalog.get(meta.resource_id).status.vector_status == "done"
    store.close()
