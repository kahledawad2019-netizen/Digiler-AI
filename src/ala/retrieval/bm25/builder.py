"""Build/refresh the BM25 index from the ingested corpus chunks.

Reads child-chunk text + metadata from the ChunkStore (the same derived artifacts
the dense pipeline uses) so BM25 and dense retrieval index exactly the same units.
"""

from __future__ import annotations

import logging

from ala.config.settings import Settings
from ala.retrieval.bm25.index import BM25Index
from ala.retrieval.chunking.store import ChunkStore
from ala.retrieval.vectorstore.payload import build_payload

log = logging.getLogger("ala.retrieval.bm25")


def build_bm25_from_corpus(settings: Settings, index: BM25Index | None = None,
                           k1: float = 1.5, b: float = 0.75,
                           min_token_len: int = 2) -> BM25Index:
    index = index or BM25Index(k1=k1, b=b, min_token_len=min_token_len)
    chunk_store = ChunkStore(settings.derived_path)
    derived = settings.derived_path
    for children_meta in sorted(derived.glob("*/chunks/children.meta.jsonl")):
        rid = children_meta.parent.parent.name
        metas = {m.chunk_id: m for m in chunk_store.load_meta(rid, "child")}
        texts = chunk_store.load_text(rid, "child")
        for cid, meta in metas.items():
            text = texts.get(cid, "")
            if text.strip():
                index.add(cid, text, payload=build_payload(meta))
    log.info("Built BM25 index: %s", index.stats())
    return index
