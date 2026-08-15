"""Content hashing — the backbone of change detection and de-duplication.

SHA-256 of the raw bytes is authoritative: identical bytes -> identical hash,
so we can detect an unchanged file, a modified file, or a duplicate drop with
certainty. Files are read in chunks so multi-hundred-MB textbooks don't blow up
memory.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_DEFAULT_CHUNK = 1024 * 1024  # 1 MiB


def sha256_file(path: str | Path, chunk_bytes: int = _DEFAULT_CHUNK) -> str:
    """Return the hex SHA-256 of a file's bytes, streaming to bound memory."""
    digest = hashlib.sha256()
    p = Path(path)
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk_bytes), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 of an in-memory byte string."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Return the hex SHA-256 of a string (UTF-8 encoded)."""
    return sha256_bytes(text.encode("utf-8"))
