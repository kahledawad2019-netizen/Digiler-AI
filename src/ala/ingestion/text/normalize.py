"""Normalization primitives (pure functions).

Applied by the Cleaning & Normalization stage. Crucially, reflow/whitespace
rules are *type-aware*: CODE and TABLE blocks are never reflowed, so document
structure is preserved (the milestone's explicit requirement).
"""

from __future__ import annotations

import re
import unicodedata

from ala.fabric.content import BlockType

# smart / exotic characters -> plain equivalents
_REPLACEMENTS = {
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "–": "-", "—": "-", "―": "-",
    "…": "...",
    " ": " ", " ": " ", " ": " ", " ": " ", "﻿": "",
}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")   # keep \t (\x09), \n (\x0a)
_MULTISPACE = re.compile(r"[ \t]{2,}")
_MULTINEWLINE = re.compile(r"\n{3,}")
# join a line that doesn't end a sentence with the next line that continues it
_BROKEN_LINE = re.compile(r"([^\n.!?:;)\]\}])\n(?=[a-z0-9])")

_NO_REFLOW = {BlockType.CODE.value, BlockType.TABLE.value}


def normalize_unicode(text: str, form: str = "NFC") -> str:
    return unicodedata.normalize(form, text)


def replace_smart_chars(text: str) -> str:
    for bad, good in _REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text


def remove_control_chars(text: str) -> str:
    return _CONTROL.sub("", text)


def collapse_whitespace(text: str) -> str:
    text = _MULTISPACE.sub(" ", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return _MULTINEWLINE.sub("\n\n", text).strip()


def join_broken_lines(text: str) -> str:
    """Reflow hard-wrapped prose: 'foo\\nbar' -> 'foo bar' when it's mid-sentence."""
    return _BROKEN_LINE.sub(r"\1 ", text)


def normalize_block_text(text: str, *, block_type: str, config) -> str:
    """Apply the configured normalization appropriate to a block type."""
    out = text
    if getattr(config, "unicode_form", None):
        out = normalize_unicode(out, config.unicode_form)
    if getattr(config, "strip_smart_quotes", False):
        out = replace_smart_chars(out)
    out = remove_control_chars(out)
    if str(block_type) not in _NO_REFLOW:
        if getattr(config, "join_broken_lines", False):
            out = join_broken_lines(out)
        if getattr(config, "collapse_whitespace", False):
            out = collapse_whitespace(out)
    return out.strip()


def find_repeated_lines(page_lines: list[list[str]], min_ratio: float) -> set[str]:
    """Return lines that appear on >= min_ratio of pages (page headers/footers).

    ``page_lines`` is a list (per page) of the candidate lines on that page
    (typically the first and last line). A line seen on enough pages is chrome.
    """
    if not page_lines:
        return set()
    from collections import Counter

    counts: Counter[str] = Counter()
    for lines in page_lines:
        for ln in set(l.strip() for l in lines if l.strip()):
            counts[ln] += 1
    threshold = max(2, int(len(page_lines) * min_ratio))
    return {ln for ln, c in counts.items() if c >= threshold and len(ln) < 120}
