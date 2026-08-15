"""Embedder factory — resolve a model key to a concrete Embedder.

Retrieval code asks for an embedder by key; the factory returns the dependency-
free hashing embedder or a lazily-loaded transformer embedder. This is the one
place model selection happens.
"""

from __future__ import annotations

from ala.retrieval.embedding.base import Embedder
from ala.retrieval.embedding.config import MODEL_SPECS
from ala.retrieval.embedding.hashing import HashingEmbedder


def get_embedder(key: str = "hashing", *, device: str = "cpu",
                 normalize: bool = True, hashing_dim: int = 384) -> Embedder:
    if key not in MODEL_SPECS:
        raise KeyError(f"unknown embedding model '{key}'; known: {sorted(MODEL_SPECS)}")
    if key == "hashing":
        return HashingEmbedder(dim=hashing_dim)
    # transformer backends (lazy import happens on first use)
    from ala.retrieval.embedding.sentence_transformer import SentenceTransformerEmbedder
    return SentenceTransformerEmbedder.from_key(key, device=device, normalize=normalize)


def available_models() -> list[str]:
    return list(MODEL_SPECS.keys())


def transformer_available() -> bool:
    """True if sentence-transformers can be imported in this environment."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False
