"""Sidecar I/O — the "metadata as JSON beside every resource" half of Task 2.

The catalog (SQLite) is the queryable index; the sidecar is the human-readable,
version-controllable, travels-with-the-file copy. They are kept in sync by the
Registry. If they ever disagree, the validation pipeline flags it.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ala.metadata.schema import ResourceMetadata

DEFAULT_SUFFIX = ".meta.json"


def sidecar_path(resource_file: str | Path, suffix: str = DEFAULT_SUFFIX) -> Path:
    """Return the sidecar path for a given raw resource file.

    ``.../source.pdf`` -> ``.../source.pdf.meta.json`` (one sidecar per file,
    unambiguous even when a folder holds several files).
    """
    p = Path(resource_file)
    return p.with_name(p.name + suffix)


def write_sidecar(
    meta: ResourceMetadata,
    resource_file: str | Path,
    *,
    suffix: str = DEFAULT_SUFFIX,
    fmt: str = "json",
) -> Path:
    """Write ``meta`` next to ``resource_file``. Returns the sidecar path."""
    dest = sidecar_path(resource_file, suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = meta.to_dict()
    if fmt == "yaml":
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    else:
        text = json.dumps(data, indent=2, ensure_ascii=False)
    dest.write_text(text, encoding="utf-8")
    return dest


def read_sidecar(path: str | Path) -> ResourceMetadata:
    """Load and validate a sidecar file into a ResourceMetadata."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    data = yaml.safe_load(text) if p.suffix in {".yaml", ".yml"} else json.loads(text)
    return ResourceMetadata.from_dict(data)


def load_sidecar_for(
    resource_file: str | Path, suffix: str = DEFAULT_SUFFIX
) -> ResourceMetadata | None:
    """Return the metadata for a resource file, or None if no sidecar exists."""
    path = sidecar_path(resource_file, suffix)
    return read_sidecar(path) if path.is_file() else None
