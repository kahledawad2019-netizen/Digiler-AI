"""Stage 6 — BM25 index tests."""

from __future__ import annotations

from ala.retrieval.bm25 import BM25Index, BM25Retriever, tokenize


def test_tokenize_lowercases_and_filters_short():
    assert tokenize("Hello, WORLD! a") == ["hello", "world"]


def test_build_and_score_ranking():
    idx = BM25Index()
    idx.add("d1", "the cat sat on the mat", {"course": "x"})
    idx.add("d2", "the dog sat on the log", {"course": "y"})
    idx.add("d3", "quantum physics and relativity", {"course": "x"})
    res = idx.search("cat mat", top_k=3)
    assert res[0][0] == "d1"
    assert idx.n_docs == 3 and idx.stats()["vocabulary"] > 0


def test_metadata_filtering():
    idx = BM25Index()
    idx.add("d1", "cat", {"course": "x"})
    idx.add("d2", "cat", {"course": "y"})
    assert [c for c, _ in idx.search("cat", top_k=5, filters={"course": "y"})] == ["d2"]
    # any-of + list-valued payloads
    idx.add("d3", "cat", {"topics": ["sql", "keys"]})
    assert [c for c, _ in idx.search("cat", top_k=5, filters={"topics": ["keys"]})] == ["d3"]


def test_update_and_delete():
    idx = BM25Index()
    idx.add("d1", "cat cat cat", {})
    idx.add("d1", "dog", {})                     # update (replace)
    assert idx.n_docs == 1
    assert idx.search("cat") == []
    assert idx.search("dog")[0][0] == "d1"
    assert idx.delete("d1") is True and idx.n_docs == 0


def test_persistence_roundtrip(tmp_path):
    idx = BM25Index()
    idx.add("d1", "foreign key primary key referential integrity", {"course": "dmv"})
    idx.add("d2", "convolutional neural network", {"course": "applied-dl"})
    idx.save(tmp_path)
    loaded = BM25Index.load(tmp_path)
    assert loaded.n_docs == 2
    assert loaded.search("foreign key")[0][0] == "d1"
    assert loaded.payload("d1")["course"] == "dmv"


def test_retriever_adapter():
    idx = BM25Index()
    idx.add("d1", "cat mat", {"resource_id": "r"})
    r = BM25Retriever(idx).retrieve("cat", top_k=1)
    assert r[0].chunk_id == "d1" and r[0].source == "bm25"
    assert r[0].component_scores["bm25"] > 0
