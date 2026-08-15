"""Query → concept linking (ontology-aware, graph-backed).

Two complementary signals (both use only the persisted graph — no external
lexicon needed at query time):

1. **Direct alias match** — the query text is scanned for any concept alias /
   canonical name stored on the concept nodes (longest-alias-first, so
   "convolutional neural network" beats "neural network"). Score 1.0.
2. **Seed-resource concepts** — concepts attached to the resources the hybrid
   retriever already surfaced. Score scaled by the seed's rank weight.

The union (capped to ``top_k``) is the seed set handed to the expander.
"""

from __future__ import annotations

import re

from ala.graph.graph import ConceptGraph
from ala.graph.models import NodeType


class QueryConceptLinker:
    def __init__(self, graph: ConceptGraph, *, min_alias_len: int = 3) -> None:
        self.graph = graph
        self._alias_to_concept: dict[str, str] = {}
        aliases: list[str] = []
        for cid in graph.nodes(NodeType.CONCEPT.value):
            node = graph.node(cid)
            if node is None:
                continue
            names = {str(a) for a in node.attrs.get("aliases", [])} | {node.label}
            for a in names:
                al = a.lower().strip()
                if len(al) >= min_alias_len and al not in self._alias_to_concept:
                    self._alias_to_concept[al] = cid
                    aliases.append(al)
        aliases.sort(key=len, reverse=True)
        self._regex = re.compile(
            r"\b(" + "|".join(re.escape(a) for a in aliases) + r")\b", re.IGNORECASE
        ) if aliases else None

    def link(self, query: str, *, seed_resources: list[tuple[str, float]] | None = None,
             top_k: int = 8) -> dict[str, float]:
        scores: dict[str, float] = {}
        if self._regex is not None:
            for m in self._regex.finditer(query.lower()):
                cid = self._alias_to_concept.get(m.group(0).lower())
                if cid:
                    scores[cid] = max(scores.get(cid, 0.0), 1.0)
        for rid, weight in (seed_resources or []):
            rnode = f"resource:{rid}"
            if not self.graph.has_node(rnode):
                continue
            for nb, _etype, _data in self.graph.neighbors(rnode):
                if nb.startswith("concept:"):
                    scores[nb] = max(scores.get(nb, 0.0), 0.6 * weight)
        return dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k])
