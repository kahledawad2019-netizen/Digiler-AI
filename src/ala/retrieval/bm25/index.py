"""BM25Index — a pure-Python Okapi BM25 inverted index.

Production features: incremental add/update (re-adding a doc replaces it),
delete, rebuild, metadata filtering, and save/load to ``data/bm25/<name>/``.
Scoring is Okapi BM25:

    score(d,q) = Σ_t idf(t) · tf(t,d)·(k1+1) / (tf(t,d) + k1·(1 − b + b·|d|/avgdl))
    idf(t)     = ln(1 + (N − df(t) + 0.5) / (df(t) + 0.5))

A forward map (doc → its terms) is kept so deletes are O(terms in doc), not
O(vocabulary).
"""

from __future__ import annotations

import json
import math
import pickle
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ala.retrieval.bm25.tokenizer import tokenize


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75, min_token_len: int = 2) -> None:
        self.k1 = k1
        self.b = b
        self.min_token_len = min_token_len
        self._postings: dict[str, dict[str, int]] = defaultdict(dict)   # term -> {doc_id: tf}
        self._doc_terms: dict[str, list[str]] = {}                       # doc_id -> unique terms
        self._doc_len: dict[str, int] = {}
        self._payloads: dict[str, dict] = {}
        self._total_len = 0

    # -- properties ------------------------------------------------------- #
    @property
    def n_docs(self) -> int:
        return len(self._doc_len)

    @property
    def avgdl(self) -> float:
        return self._total_len / self.n_docs if self.n_docs else 0.0

    def payload(self, doc_id: str) -> dict:
        return self._payloads.get(doc_id, {})

    # -- mutation --------------------------------------------------------- #
    def add(self, doc_id: str, text: str, payload: dict | None = None) -> None:
        if doc_id in self._doc_len:
            self.delete(doc_id)                       # update = replace
        tokens = tokenize(text, min_len=self.min_token_len)
        tf = Counter(tokens)
        for term, count in tf.items():
            self._postings[term][doc_id] = count
        self._doc_terms[doc_id] = list(tf.keys())
        self._doc_len[doc_id] = len(tokens)
        self._payloads[doc_id] = payload or {}
        self._total_len += len(tokens)

    def add_many(self, items) -> int:
        n = 0
        for doc_id, text, payload in items:
            self.add(doc_id, text, payload)
            n += 1
        return n

    def delete(self, doc_id: str) -> bool:
        if doc_id not in self._doc_len:
            return False
        for term in self._doc_terms.pop(doc_id):
            postings = self._postings.get(term)
            if postings and doc_id in postings:
                del postings[doc_id]
                if not postings:
                    del self._postings[term]
        self._total_len -= self._doc_len.pop(doc_id)
        self._payloads.pop(doc_id, None)
        return True

    def rebuild(self, items) -> int:
        self.__init__(self.k1, self.b, self.min_token_len)
        return self.add_many(items)

    # -- query ------------------------------------------------------------ #
    def search(self, query: str, top_k: int = 10,
               filters: dict[str, Any] | None = None) -> list[tuple[str, float]]:
        q_terms = tokenize(query, min_len=self.min_token_len)
        if not q_terms or self.n_docs == 0:
            return []
        n = self.n_docs
        avgdl = self.avgdl or 1.0
        scores: dict[str, float] = defaultdict(float)
        for term in set(q_terms):
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = math.log(1 + (n - len(postings) + 0.5) / (len(postings) + 0.5))
            for doc_id, tf in postings.items():
                if filters and not self._match(self._payloads.get(doc_id, {}), filters):
                    continue
                dl = self._doc_len[doc_id]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / avgdl)
                scores[doc_id] += idf * (tf * (self.k1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_k]

    @staticmethod
    def _match(payload: dict, filters: dict[str, Any]) -> bool:
        for key, want in filters.items():
            val = payload.get(key)
            wants = set(want) if isinstance(want, (list, tuple, set)) else {want}
            have = set(val) if isinstance(val, list) else {val}
            if not (wants & have):
                return False
        return True

    # -- persistence ------------------------------------------------------ #
    def save(self, directory: str | Path) -> Path:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        state = {
            "k1": self.k1, "b": self.b, "min_token_len": self.min_token_len,
            "postings": {t: dict(p) for t, p in self._postings.items()},
            "doc_terms": self._doc_terms, "doc_len": self._doc_len,
            "payloads": self._payloads, "total_len": self._total_len,
        }
        with (d / "index.pkl").open("wb") as fh:
            pickle.dump(state, fh, protocol=pickle.HIGHEST_PROTOCOL)
        (d / "meta.json").write_text(json.dumps(self.stats(), indent=2), encoding="utf-8")
        return d

    @classmethod
    def load(cls, directory: str | Path) -> "BM25Index":
        d = Path(directory)
        with (d / "index.pkl").open("rb") as fh:
            state = pickle.load(fh)
        idx = cls(state["k1"], state["b"], state["min_token_len"])
        idx._postings = defaultdict(dict, {t: dict(p) for t, p in state["postings"].items()})
        idx._doc_terms = state["doc_terms"]
        idx._doc_len = state["doc_len"]
        idx._payloads = state["payloads"]
        idx._total_len = state["total_len"]
        return idx

    def stats(self) -> dict:
        return {
            "docs": self.n_docs,
            "vocabulary": len(self._postings),
            "total_tokens": self._total_len,
            "avgdl": round(self.avgdl, 2),
            "k1": self.k1,
            "b": self.b,
        }
