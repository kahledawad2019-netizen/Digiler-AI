"""ChunkStore — persists chunks with metadata SEPARATE from text (Stage 3).

Layout under ``knowledge_base/derived/<resource_id>/chunks/``:
    parents.meta.jsonl    children.meta.jsonl     (ChunkMetadata, no text)
    parents.text.jsonl    children.text.jsonl     ({chunk_id, text})

Keeping metadata and text apart lets later stages scan/filter/evolve metadata
(and attach embeddings, scores, graph ids) without loading the text corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

from ala.retrieval.chunking.models import Chunk, ChunkMetadata, ChunkSet


class ChunkStore:
    def __init__(self, derived_root: str | Path) -> None:
        self.root = Path(derived_root)

    def chunks_dir(self, resource_id: str) -> Path:
        return self.root / resource_id / "chunks"

    def exists(self, resource_id: str) -> bool:
        return (self.chunks_dir(resource_id) / "children.meta.jsonl").is_file()

    def save(self, chunkset: ChunkSet) -> Path:
        d = self.chunks_dir(chunkset.resource_id)
        d.mkdir(parents=True, exist_ok=True)
        _write_jsonl(d / "parents.meta.jsonl", [c.metadata.model_dump(mode="json") for c in chunkset.parents])
        _write_jsonl(d / "children.meta.jsonl", [c.metadata.model_dump(mode="json") for c in chunkset.children])
        _write_jsonl(d / "parents.text.jsonl", [{"chunk_id": c.chunk_id, "text": c.text} for c in chunkset.parents])
        _write_jsonl(d / "children.text.jsonl", [{"chunk_id": c.chunk_id, "text": c.text} for c in chunkset.children])
        return d

    def load_meta(self, resource_id: str, kind: str = "child") -> list[ChunkMetadata]:
        name = "children" if kind == "child" else "parents"
        return [ChunkMetadata.model_validate(r) for r in _read_jsonl(self.chunks_dir(resource_id) / f"{name}.meta.jsonl")]

    def load_text(self, resource_id: str, kind: str = "child") -> dict[str, str]:
        name = "children" if kind == "child" else "parents"
        return {r["chunk_id"]: r["text"] for r in _read_jsonl(self.chunks_dir(resource_id) / f"{name}.text.jsonl")}

    def load_chunkset(self, resource_id: str) -> ChunkSet:
        def bundle(kind: str) -> list[Chunk]:
            metas = self.load_meta(resource_id, kind)
            texts = self.load_text(resource_id, kind)
            return [Chunk(metadata=m, text=texts.get(m.chunk_id, "")) for m in metas]

        return ChunkSet(resource_id=resource_id, parents=bundle("parent"), children=bundle("child"))


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
