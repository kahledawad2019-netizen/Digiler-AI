"""Content-hash embedding cache (avoid re-embedding identical text).

Keyed by (embedder version, sha256(text)). Many chunks repeat across a corpus
(shared boilerplate, duplicated datasets), so the cache measurably cuts embedding
time. One JSONL file per embedder version under ``derived/_embedding_cache/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


class EmbeddingCache:
    def __init__(self, derived_root: str | Path, version: str) -> None:
        self.path = Path(derived_root) / "_embedding_cache" / f"{_safe(version)}.jsonl"
        self._mem: dict[str, list[float]] = {}
        self._pending: list[tuple[str, list[float]]] = []
        self._load()

    def get(self, content_hash: str) -> list[float] | None:
        return self._mem.get(content_hash)

    def put(self, content_hash: str, vector: list[float]) -> None:
        if content_hash not in self._mem:
            self._mem[content_hash] = vector
            self._pending.append((content_hash, vector))

    def flush(self) -> None:
        if not self._pending:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            for h, v in self._pending:
                fh.write(json.dumps({"h": h, "v": v}) + "\n")
        self._pending.clear()

    def __len__(self) -> int:
        return len(self._mem)

    def _load(self) -> None:
        if not self.path.is_file():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    row = json.loads(line)
                    self._mem[row["h"]] = row["v"]
