"""Concept extraction — high-precision, domain-specific (Stage 10.5 upgrade).

Two complementary sources (V3 §4.3): a curated **domain lexicon** matched against
the corpus text (deterministic, acronym-aware) plus **embedding-aware multi-word
n-gram mining** (KeyBERT-style) for phrases not in the lexicon. Generic single
words never become concepts (only lexicon terms or mined multi-word phrases that
are embedding-similar to the domain survive). Each concept carries canonical
name, aliases, confidence, frequency, source resources, and provenance.

The graph schema is unchanged — these fields live in the concept node's ``attrs``.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ala.core import ids

_WORD = re.compile(r"[a-zA-Z][a-zA-Z\-]+")

# Words that must never be a (standalone) concept and must not sit at a phrase edge.
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "by", "as",
    "is", "are", "be", "this", "that", "these", "those", "it", "its", "we", "you",
    "can", "will", "using", "used", "use", "uses", "such", "each", "which", "when",
    "how", "from", "into", "than", "then", "some", "any", "all", "more", "most",
    "our", "based", "given", "shown", "called", "defined", "following", "follows",
    "different", "various", "many", "also", "one", "two", "new", "via", "per",
    "between", "within", "about", "above", "below", "over", "under", "same",
}
GENERIC_TERMS = {
    "data", "example", "examples", "information", "result", "results", "chapter",
    "section", "model", "models", "value", "values", "number", "numbers", "name",
    "names", "set", "sets", "step", "steps", "table", "tables", "column", "columns",
    "figure", "figures", "introduction", "overview", "summary", "note", "notes",
    "answer", "answers", "question", "questions", "problem", "problems", "goal",
    "goals", "practice", "sample", "samples", "score", "range", "first", "find",
    "print", "create", "function", "functions", "code", "output", "input", "type",
    "types", "list", "row", "rows", "case", "point", "points", "part", "way",
    "thing", "things", "lecture", "lesson", "week", "session", "slide", "page",
}


@dataclass
class Concept:
    concept_id: str
    canonical: str
    domain: str
    aliases: list[str] = field(default_factory=list)
    confidence: float = 1.0
    frequency: int = 0
    source_resources: list[str] = field(default_factory=list)
    seed: bool = True

    def node_attrs(self) -> dict:
        return {
            "canonical": self.canonical, "domain": self.domain, "aliases": self.aliases,
            "confidence": round(self.confidence, 4), "frequency": self.frequency,
            "source_resources": self.source_resources[:50],
            "n_resources": len(self.source_resources), "seed": self.seed,
        }


class ConceptExtractor:
    def __init__(self, lexicon: list[dict], embedder=None, *, min_phrase_freq: int = 4,
                 min_phrase_resources: int = 3, domain_threshold: float = 0.55,
                 alias_threshold: float = 0.92, max_mined: int = 60) -> None:
        self.lexicon = lexicon
        self.embedder = embedder
        self.min_phrase_freq = min_phrase_freq
        self.min_phrase_resources = min_phrase_resources
        self.domain_threshold = domain_threshold
        self.alias_threshold = alias_threshold
        self.max_mined = max_mined

        self._alias_to_concept: dict[str, str] = {}
        self._concept_by_id: dict[str, dict] = {}
        all_aliases: list[str] = []
        for entry in lexicon:
            cid = entry["id"]
            self._concept_by_id[cid] = entry
            for alias in set(a.lower() for a in entry.get("aliases", [])) | {entry["canonical"].lower()}:
                self._alias_to_concept[alias] = cid
                all_aliases.append(alias)
        # longest aliases first so "convolutional neural network" beats "neural network"
        all_aliases.sort(key=len, reverse=True)
        self._alias_regex = re.compile(
            r"\b(" + "|".join(re.escape(a) for a in all_aliases) + r")\b", re.IGNORECASE
        ) if all_aliases else None

    # ------------------------------------------------------------------ #
    def extract(self, resource_docs: dict[str, str]) -> list[Concept]:
        lexicon = self._match_lexicon(resource_docs)          # dict cid -> Concept
        mined = self._mine_phrases(resource_docs, lexicon)     # merges sub-phrases into lexicon
        return list(lexicon.values()) + mined

    def _match_lexicon(self, resource_docs: dict[str, str]) -> dict[str, Concept]:
        freq: Counter = Counter()
        resources: dict[str, set[str]] = defaultdict(set)
        hits: dict[str, Counter] = defaultdict(Counter)
        if self._alias_regex is not None:
            for rid, text in resource_docs.items():
                for m in self._alias_regex.finditer(text.lower()):
                    cid = self._alias_to_concept.get(m.group(0).lower())
                    if cid:
                        freq[cid] += 1
                        resources[cid].add(rid)
                        hits[cid][m.group(0).lower()] += 1

        out: dict[str, Concept] = {}
        for cid, entry in self._concept_by_id.items():
            if freq[cid] == 0:
                continue                              # curated but absent → skip
            out[cid] = Concept(
                concept_id=f"concept:{cid}", canonical=entry["canonical"],
                domain=entry.get("domain", "general"),
                aliases=sorted({a for a, _ in hits[cid].most_common()}),
                confidence=1.0, frequency=freq[cid],
                source_resources=sorted(resources[cid]), seed=True,
            )
        return out

    def _mine_phrases(self, resource_docs: dict[str, str],
                      lexicon: dict[str, Concept]) -> list[Concept]:
        known_aliases = set(self._alias_to_concept)
        phrase_freq: Counter = Counter()
        phrase_resources: dict[str, set[str]] = defaultdict(set)
        for rid, text in resource_docs.items():
            for phrase in _candidate_phrases(text):
                if phrase in known_aliases:
                    continue
                phrase_freq[phrase] += 1
                phrase_resources[phrase].add(rid)

        candidates = [p for p, f in phrase_freq.items()
                      if f >= self.min_phrase_freq
                      and len(phrase_resources[p]) >= self.min_phrase_resources]
        candidates.sort(key=lambda p: phrase_freq[p], reverse=True)
        candidates = candidates[: max(self.max_mined * 6, 300)]
        if not candidates:
            return []

        # canonicalization: fold a candidate into a lexicon concept when its words
        # are a sub/superset of that concept's words (ontology-aware merge).
        lex_tokens = {c.concept_id: {w for a in [c.canonical, *c.aliases] for w in a.lower().split()}
                      for c in lexicon.values()}
        remaining: list[str] = []
        for phrase in candidates:
            ptoks = set(phrase.split())
            merged = False
            for c in lexicon.values():
                lt = lex_tokens[c.concept_id]
                if ptoks <= lt or lt <= ptoks:
                    if phrase not in c.aliases:
                        c.aliases.append(phrase)
                    c.frequency += phrase_freq[phrase]
                    c.source_resources = sorted(set(c.source_resources) | phrase_resources[phrase])
                    merged = True
                    break
            if not merged:
                remaining.append(phrase)

        # embedding-aware: keep remaining candidates similar to the domain lexicon
        scored = self._score_by_domain(remaining)
        scored.sort(key=lambda kv: kv[1], reverse=True)

        mined: list[Concept] = []
        kept_tokens: list[set[str]] = []
        for phrase, sim in scored:
            if sim < self.domain_threshold or len(mined) >= self.max_mined:
                continue
            ptoks = set(phrase.split())
            dup = next((m for m, kt in zip(mined, kept_tokens) if ptoks <= kt or kt <= ptoks), None)
            if dup is not None:                       # dedupe among mined concepts
                if phrase not in dup.aliases:
                    dup.aliases.append(phrase)
                dup.frequency += phrase_freq[phrase]
                dup.source_resources = sorted(set(dup.source_resources) | phrase_resources[phrase])
                continue
            c = Concept(
                concept_id=f"concept:{ids.slugify(phrase)}", canonical=phrase.title(),
                domain="mined", aliases=[phrase],
                confidence=round(float(_calibrate(sim, phrase_freq[phrase])), 4),
                frequency=phrase_freq[phrase],
                source_resources=sorted(phrase_resources[phrase]), seed=False,
            )
            mined.append(c)
            kept_tokens.append(ptoks)
        return mined

    def _score_by_domain(self, candidates: list[str]) -> list[tuple[str, float]]:
        """Max cosine of each candidate to any lexicon canonical (KeyBERT-style)."""
        anchors = [e["canonical"] for e in self.lexicon]
        if self.embedder is None or not anchors:
            # no embedder: accept multi-word candidates by a neutral score
            return [(c, 1.0) for c in candidates]
        import numpy as np

        cand_vecs = np.asarray(self.embedder.embed_documents(candidates), dtype="float32")
        anchor_vecs = np.asarray(self.embedder.embed_documents(anchors), dtype="float32")
        sims = cand_vecs @ anchor_vecs.T           # vectors are L2-normalized
        best = sims.max(axis=1)
        return list(zip(candidates, best.tolist()))


# --------------------------------------------------------------------------- #
def _calibrate(similarity: float, frequency: int) -> float:
    """Blend domain similarity with (log-scaled) corpus frequency into [0,1]."""
    import math
    freq_factor = min(1.0, math.log1p(frequency) / math.log(50))
    return min(1.0, max(0.0, 0.7 * similarity + 0.3 * freq_factor))


def _candidate_phrases(text: str) -> list[str]:
    """2-4 gram noun-phrase-like candidates: no stopword/generic at the edges."""
    tokens = [t for t in (w.lower() for w in _WORD.findall(text)) if len(t) >= 3]
    out: list[str] = []
    n = len(tokens)
    for i in range(n):
        for size in (2, 3, 4):
            if i + size > n:
                break
            gram = tokens[i:i + size]
            if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
                continue
            if gram[0] in GENERIC_TERMS or gram[-1] in GENERIC_TERMS:
                continue
            if any(g in STOPWORDS for g in gram):
                continue
            out.append(" ".join(gram))
    return out
