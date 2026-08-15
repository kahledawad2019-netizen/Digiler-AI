"""Embedding configuration + the model registry.

``MODEL_SPECS`` is the single source of truth for how each supported model is
loaded (HF name, dimension, and the query/passage prefixes it expects). Adding a
model is a data edit here, not a code change.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from ala.config.settings import Settings


@dataclass(frozen=True)
class ModelSpec:
    key: str
    hf_name: str | None       # None for the dependency-free hashing embedder
    dim: int
    query_prefix: str = ""
    doc_prefix: str = ""
    multilingual: bool = True
    note: str = ""


# The models the platform supports. e5 REQUIRES its "query:"/"passage:" prefixes.
MODEL_SPECS: dict[str, ModelSpec] = {
    "hashing": ModelSpec("hashing", None, 384, note="dependency-free char-ngram feature hashing"),
    "e5-small": ModelSpec(
        "e5-small", "intfloat/multilingual-e5-small", 384,
        query_prefix="query: ", doc_prefix="passage: ",
        note="default production model (multilingual, 118M params)",
    ),
    "bge-m3": ModelSpec(
        "bge-m3", "BAAI/bge-m3", 1024,
        note="highest-quality multilingual tier (568M params, ~2.3GB)",
    ),
    "minilm": ModelSpec(
        "minilm", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 384,
        note="fast multilingual baseline (118M params)",
    ),
}


class EmbeddingConfig(BaseModel):
    default_model: str = "hashing"
    batch_size: int = 32
    normalize: bool = True
    use_cache: bool = True
    hashing_dim: int = 384
    device: str = "cpu"

    @classmethod
    def from_settings(cls, settings: Settings) -> "EmbeddingConfig":
        return cls(**(settings.retrieval or {}).get("embedding", {}))
