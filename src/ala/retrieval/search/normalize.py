"""Query normalization — the first step of the retrieval pipeline.

Reuses the ingestion normalizer (Unicode NFC + smart-char + whitespace) so
queries are cleaned exactly the way document text was, keeping BM25 lexical
matching consistent.
"""

from __future__ import annotations

from ala.ingestion.text import normalize as _n


def normalize_query(query: str) -> str:
    q = _n.normalize_unicode(query or "", "NFC")
    q = _n.replace_smart_chars(q)
    q = _n.remove_control_chars(q)
    return " ".join(q.split()).strip()
