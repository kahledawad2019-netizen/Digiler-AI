"""Tokenizer for the BM25 index.

Unicode word tokenization, lower-cased, with a minimum length filter. Works for
both English and Arabic (both space/word delimited under ``\\w``). Kept separate
and simple so it can be swapped (e.g. for a stemmer) without touching the index.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str, *, min_len: int = 2) -> list[str]:
    return [t for t in _WORD.findall((text or "").lower()) if len(t) >= min_len]
