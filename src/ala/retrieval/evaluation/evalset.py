"""Known-item evaluation set built directly from the corpus (label-free).

For each sampled child chunk we extract a contiguous word span from the middle
of the chunk as the query, and treat the chunk's **source resource** as the
relevant set (every child of that resource). This is a reproducible, human-free
"can retrieval find the right document?" evaluation. It also returns the
resource → chunk-ids map used by the metrics.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from ala.config.settings import Settings


@dataclass
class EvalQuery:
    query: str
    gold_chunk_id: str
    gold_resource_id: str


def build_known_item_evalset(
    settings: Settings, *, n: int = 150, seed: int = 0, span_words: int = 12,
    min_words: int = 25,
) -> tuple[list[EvalQuery], dict[str, set[str]]]:
    derived = settings.derived_path
    rng = random.Random(seed)
    resource_chunks: dict[str, set[str]] = {}
    pool: list[tuple[str, str, list[str]]] = []      # (rid, chunk_id, words)

    files = sorted(derived.glob("*/chunks/children.text.jsonl"))
    rng.shuffle(files)
    for f in files:
        rid = f.parent.parent.name
        ids: set[str] = set()
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        for row in rows:
            ids.add(row["chunk_id"])
            words = row["text"].split()
            if len(words) >= min_words:
                pool.append((rid, row["chunk_id"], words))
        resource_chunks[rid] = ids

    rng.shuffle(pool)
    evalset: list[EvalQuery] = []
    for rid, cid, words in pool[:n]:
        start = len(words) // 3
        query = " ".join(words[start:start + span_words])
        if query.strip():
            evalset.append(EvalQuery(query=query, gold_chunk_id=cid, gold_resource_id=rid))
    return evalset, resource_chunks
