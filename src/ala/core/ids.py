"""Stable identifiers.

Design principle #2 of the redesign: citations, the Concept Graph, and the
Student Model reference a ``resource_id``, never a file path — so renames and
reorganizations are free. A resource_id is a dotted slug:

    <track>.<course>.<module>.<slug>
    e.g.  technical.dmv.w03.constraints-relationships

The slug segment is derived from the human title but sanitised to ASCII, so
Arabic titles (which live in metadata) never leak into identifiers or paths.
"""

from __future__ import annotations

import re
import unicodedata
import uuid

# resource_id: dot-separated segments of [a-z0-9-]; 3+ segments.
_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*){2,}$")
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 60) -> str:
    """Turn arbitrary text into an ASCII ``a-z0-9-`` slug.

    Non-ASCII (e.g. Arabic) is transliterated where possible and otherwise
    dropped; if nothing survives, a short uid is returned so a slug always
    exists.
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_STRIP.sub("-", ascii_text).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or f"res-{short_uid()}"


def make_resource_id(track: str, course: str, module: str, slug: str) -> str:
    """Compose a canonical resource_id from taxonomy parts + a slug."""
    parts = [slugify(track, 20), slugify(course, 20), slugify(module, 20), slugify(slug)]
    resource_id = ".".join(p for p in parts if p)
    if not is_valid_resource_id(resource_id):
        raise ValueError(f"Could not build a valid resource_id from parts: {parts!r}")
    return resource_id


def is_valid_resource_id(resource_id: str) -> bool:
    """True if the id matches the canonical dotted-slug format."""
    return bool(_ID_RE.match(resource_id))


def short_uid() -> str:
    """A short, collision-resistant token for disambiguation/fallbacks."""
    return uuid.uuid4().hex[:8]
