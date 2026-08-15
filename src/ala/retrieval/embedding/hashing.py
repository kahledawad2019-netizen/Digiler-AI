"""HashingEmbedder — a real, dependency-free embedding backend.

Feature hashing (a.k.a. the hashing trick) over word tokens + character n-grams:
each feature is hashed to a signed bucket, buckets are accumulated, and the
vector is L2-normalized. This is a genuine, deterministic embedding technique —
similar texts share features and get higher cosine similarity — not a mock. It
lets the entire retrieval stack run and be tested offline; the transformer
models are the higher-quality production backends selected via config.

Determinism: uses BLAKE2b (stable across processes), not Python's salted hash.
"""

from __future__ import annotations

import hashlib
import math
import re

_WORD = re.compile(r"\w+", re.UNICODE)


class HashingEmbedder:
    model_id = "hashing"

    def __init__(self, dim: int = 384, char_ngrams: tuple[int, int] = (3, 5)) -> None:
        self.dim = dim
        self.char_ngrams = char_ngrams
        self.version = f"hashing-ngram-v1-d{dim}-c{char_ngrams[0]}{char_ngrams[1]}"

    # -- Embedder interface ---------------------------------------------- #
    def embed_documents(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    # -- internals -------------------------------------------------------- #
    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feature in self._features(text or ""):
            idx, sign = self._bucket(feature)
            vec[idx] += sign
        return _l2_normalize(vec)

    def _features(self, text: str):
        low = text.lower()
        for tok in _WORD.findall(low):
            yield f"w:{tok}"
        compact = re.sub(r"\s+", " ", low)
        lo, hi = self.char_ngrams
        for n in range(lo, hi + 1):
            if len(compact) < n:
                continue
            for i in range(len(compact) - n + 1):
                yield f"c{n}:{compact[i:i + n]}"

    def _bucket(self, feature: str) -> tuple[int, int]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        h = int.from_bytes(digest, "big")
        idx = h % self.dim
        sign = 1 if (h >> 63) & 1 else -1
        return idx, sign


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]
