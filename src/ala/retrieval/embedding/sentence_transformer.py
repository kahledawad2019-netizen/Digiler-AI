"""SentenceTransformerEmbedder — production transformer backend.

Supports multilingual-e5-small, bge-m3, and multilingual MiniLM through the
model registry. sentence-transformers/torch are imported lazily, so importing
this module never requires the heavy dependency; it is only needed when a
transformer model is actually instantiated. Model weights download once and are
cached by huggingface-hub.

e5 requires "query: " / "passage: " prefixes — applied automatically from the
model spec, so callers use the same ``embed_documents``/``embed_query`` contract.
"""

from __future__ import annotations

from ala.retrieval.embedding.config import MODEL_SPECS, ModelSpec
from ala.core.exceptions import AlaError


class EmbedderUnavailableError(AlaError):
    """sentence-transformers is not installed."""


class SentenceTransformerEmbedder:
    def __init__(self, spec: ModelSpec, device: str = "cpu", normalize: bool = True) -> None:
        if spec.hf_name is None:
            raise ValueError(f"{spec.key} is not a transformer model")
        self.spec = spec
        self.model_id = spec.key
        self.device = device
        self.normalize = normalize
        self._model = None
        self._dim = spec.dim
        self.version = f"st:{spec.hf_name}"

    @classmethod
    def from_key(cls, key: str, device: str = "cpu", normalize: bool = True) -> "SentenceTransformerEmbedder":
        if key not in MODEL_SPECS:
            raise KeyError(f"unknown model '{key}'; known: {sorted(MODEL_SPECS)}")
        return cls(MODEL_SPECS[key], device=device, normalize=normalize)

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - env-dependent
                raise EmbedderUnavailableError(
                    "sentence-transformers is not installed. Install the models extra: "
                    'pip install -e ".[models]"'
                ) from exc
            self._model = SentenceTransformer(self.spec.hf_name, device=self.device)
            # method was renamed in newer sentence-transformers; support both
            get_dim = getattr(self._model, "get_embedding_dimension", None) or \
                self._model.get_sentence_embedding_dimension
            self._dim = get_dim()
            # pin the exact library version for reproducibility
            import sentence_transformers as st
            self.version = f"st{st.__version__}:{self.spec.hf_name}"
        return self._model

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        prepared = [self.spec.doc_prefix + t for t in texts]
        vecs = self.model.encode(
            prepared, batch_size=batch_size or 32,
            normalize_embeddings=self.normalize, convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vecs.tolist()

    def embed_query(self, text: str) -> list[float]:
        vec = self.model.encode(
            self.spec.query_prefix + text,
            normalize_embeddings=self.normalize, convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vec.tolist()
