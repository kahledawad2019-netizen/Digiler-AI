"""EmbeddingStore — versioned persistence of vectors + manifest.

Layout under ``knowledge_base/derived/<resource_id>/embeddings/``:
    <model_id>.jsonl           {chunk_id, vector} per child chunk
    <model_id>.manifest.json   EmbeddingManifest (model, version, dim, count, timestamps)

Vectors are stored as JSONL (portable, diff-able, numpy-free to write); a numpy
matrix is materialized on demand for search. One file per model so multiple
embedding models can coexist for the same resource (needed for benchmarking).
"""

from __future__ import annotations

import json
from pathlib import Path

from ala.retrieval.embedding.models import EmbeddingManifest, EmbeddingRecord


class EmbeddingStore:
    def __init__(self, derived_root: str | Path) -> None:
        self.root = Path(derived_root)

    def dir(self, resource_id: str) -> Path:
        return self.root / resource_id / "embeddings"

    def exists(self, resource_id: str, model_id: str) -> bool:
        return (self.dir(resource_id) / f"{model_id}.manifest.json").is_file()

    def save(self, resource_id: str, model_id: str, version: str, dim: int,
             records: list[EmbeddingRecord]) -> Path:
        d = self.dir(resource_id)
        d.mkdir(parents=True, exist_ok=True)
        with (d / f"{model_id}.jsonl").open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps({"chunk_id": r.chunk_id, "vector": r.vector}) + "\n")
        manifest = EmbeddingManifest(
            resource_id=resource_id, model_id=model_id, version=version,
            dim=dim, count=len(records),
        )
        (d / f"{model_id}.manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        return d

    def load_manifest(self, resource_id: str, model_id: str) -> EmbeddingManifest | None:
        p = self.dir(resource_id) / f"{model_id}.manifest.json"
        if not p.is_file():
            return None
        return EmbeddingManifest.model_validate_json(p.read_text(encoding="utf-8"))

    def load_vectors(self, resource_id: str, model_id: str) -> list[tuple[str, list[float]]]:
        p = self.dir(resource_id) / f"{model_id}.jsonl"
        if not p.is_file():
            return []
        out = []
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    row = json.loads(line)
                    out.append((row["chunk_id"], row["vector"]))
        return out

    def load_matrix(self, resource_id: str, model_id: str):
        """Return (chunk_ids, numpy float32 matrix). Requires numpy."""
        import numpy as np

        pairs = self.load_vectors(resource_id, model_id)
        ids = [cid for cid, _ in pairs]
        mat = np.asarray([v for _, v in pairs], dtype="float32") if pairs else np.zeros((0, 0), "float32")
        return ids, mat
