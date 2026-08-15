"""Token counting behind an interface (Dependency Inversion).

Chunk sizes are expressed in "tokens". The default counter is a dependency-free
word-based approximation that works for both English and Arabic (both are
space-delimited scripts). For exact model tokenization, inject a counter backed
by tiktoken or a HuggingFace tokenizer — retrieval code never changes.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

_WORD = re.compile(r"\S+")


@runtime_checkable
class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class WordTokenCounter:
    """Whitespace/word count, scaled to approximate subword tokens.

    English averages ~1.3 subword tokens per word; the scale makes the word
    count a reasonable proxy for a real tokenizer's output.
    """

    def __init__(self, tokens_per_word: float = 1.3) -> None:
        self.tokens_per_word = tokens_per_word

    def count(self, text: str) -> int:
        words = len(_WORD.findall(text or ""))
        return int(round(words * self.tokens_per_word))
