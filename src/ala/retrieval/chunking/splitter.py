"""Recursive, multilingual-safe text splitter with overlap.

Boundaries respect sentence structure (never mid-word), using terminators for
both Latin and Arabic scripts, so Arabic text is chunked as cleanly as English.
Sentences are greedily packed into windows of <= ``max_tokens`` with a trailing
``overlap_tokens`` carried into the next window (context continuity). A single
oversized sentence is hard-split on word boundaries as a last resort.
"""

from __future__ import annotations

import re

from ala.retrieval.chunking.tokenizer import TokenCounter, WordTokenCounter

# Sentence terminators: Latin (. ! ? ; :) and Arabic (؟ ؛ ،) + ellipsis + newlines.
_SENT_SPLIT = re.compile(r"(?<=[\.\!\?;:؟؛،…])\s+|\n+")
_WORD = re.compile(r"\S+")


class RecursiveTextSplitter:
    def __init__(
        self,
        max_tokens: int,
        overlap_tokens: int = 0,
        counter: TokenCounter | None = None,
    ) -> None:
        if overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.counter = counter or WordTokenCounter()

    def split(self, text: str) -> list[str]:
        text = (text or "").strip()
        if not text:
            return []
        if self.counter.count(text) <= self.max_tokens:
            return [text]

        units = self._sentences(text)
        return self._pack(units)

    # -- internals -------------------------------------------------------- #
    def _sentences(self, text: str) -> list[str]:
        raw = [s.strip() for s in _SENT_SPLIT.split(text) if s and s.strip()]
        units: list[str] = []
        for s in raw:
            if self.counter.count(s) > self.max_tokens:
                units.extend(self._hard_split(s))   # oversized sentence
            else:
                units.append(s)
        return units

    def _hard_split(self, sentence: str) -> list[str]:
        words = _WORD.findall(sentence)
        out, cur = [], []
        for w in words:
            cur.append(w)
            if self.counter.count(" ".join(cur)) >= self.max_tokens:
                out.append(" ".join(cur))
                cur = []
        if cur:
            out.append(" ".join(cur))
        return out

    def _pack(self, units: list[str]) -> list[str]:
        windows: list[str] = []
        cur: list[str] = []

        def cur_tokens() -> int:
            return self.counter.count(" ".join(cur))

        for unit in units:
            if cur and self.counter.count(" ".join(cur + [unit])) > self.max_tokens:
                windows.append(" ".join(cur))
                cur = self._overlap_tail(cur)
            cur.append(unit)
        if cur:
            windows.append(" ".join(cur))
        return windows

    def _overlap_tail(self, units: list[str]) -> list[str]:
        """Return the trailing units whose tokens sum to ~overlap_tokens."""
        if self.overlap_tokens <= 0:
            return []
        tail: list[str] = []
        total = 0
        for unit in reversed(units):
            t = self.counter.count(unit)
            if total + t > self.overlap_tokens and tail:
                break
            tail.insert(0, unit)
            total += t
        return tail
