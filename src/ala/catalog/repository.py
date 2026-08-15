"""KnowledgeCatalog — the repository API over the SQLite catalog.

Callers work with ``ResourceMetadata`` objects and plain dicts; SQL stays here.
Provides the capabilities Task 3 asks for: fast lookup, search, filtering,
version tracking, incremental-indexing support, provenance (event log), and
statistics (dashboard-ready).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ala.catalog.database import Database
from ala.core.clock import Clock, SystemClock
from ala.core.enums import RecordStatus as _RecordStatus
from ala.metadata.schema import ResourceMetadata

_CATALOG_SCHEMA_VERSION = "1.1.0"  # +M1.5 promoted academic columns

# Promoted columns, in schema order, written on every upsert.
_COLUMNS = [
    "resource_id", "parent_resource_id", "title", "track", "course", "subject",
    "module", "week", "lecture", "doc_type", "role", "language", "parallel_group",
    "record_status", "version", "persistence", "file_path", "file_name",
    "file_size", "sha256", "content_hash", "created_date", "last_modified",
    "processing_status", "ocr_status", "embedding_status", "graph_status",
    "vector_status", "validation_status", "chunk_count", "difficulty",
    "difficulty_score", "course_code", "instructor", "lab_required",
    "has_video", "has_web",
    "schema_version", "created_at", "updated_at", "last_indexed_at",
]

_FILTERABLE = {
    "track", "course", "subject", "module", "language", "doc_type", "role",
    "processing_status", "record_status", "parallel_group", "parent_resource_id",
    "difficulty", "course_code", "instructor", "lab_required", "has_video", "has_web",
}


class KnowledgeCatalog:
    """Central index of every resource the platform knows about."""

    def __init__(self, db: Database, clock: Clock | None = None) -> None:
        self.db = db
        self.clock = clock or SystemClock()

    @classmethod
    def from_settings(cls, settings, clock: Clock | None = None) -> "KnowledgeCatalog":
        db = Database(settings.catalog_db_path, journal_mode=settings.catalog.journal_mode)
        return cls(db, clock=clock)

    # -- setup ------------------------------------------------------------ #
    def initialize(self) -> None:
        self.db.initialize()
        self.set_meta("catalog_schema_version", _CATALOG_SCHEMA_VERSION)
        if self.get_meta("created_at") is None:
            self.set_meta("created_at", self.clock.now_iso())
        self.set_meta("last_updated", self.clock.now_iso())

    # -- catalog_meta ----------------------------------------------------- #
    def set_meta(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO catalog_meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def get_meta(self, key: str) -> str | None:
        row = self.db.query_one("SELECT value FROM catalog_meta WHERE key = ?", (key,))
        return row["value"] if row else None

    # -- write ------------------------------------------------------------ #
    def upsert_resource(self, meta: ResourceMetadata) -> None:
        """Insert or replace a resource (promoted columns + full JSON)."""
        row = meta.to_catalog_row()
        values = [row.get(col) for col in _COLUMNS]
        values.append(meta.to_json())  # metadata_json (full fidelity)
        placeholders = ", ".join(["?"] * (len(_COLUMNS) + 1))
        col_list = ", ".join(_COLUMNS + ["metadata_json"])
        self.db.execute(
            f"INSERT OR REPLACE INTO resources ({col_list}) VALUES ({placeholders})",
            values,
        )
        self.set_meta("last_updated", self.clock.now_iso())

    def record_event(
        self,
        resource_id: str,
        event_type: str,
        *,
        from_hash: str | None = None,
        to_hash: str | None = None,
        version: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.db.execute(
            "INSERT INTO resource_events "
            "(resource_id, event_type, from_hash, to_hash, version, details_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                resource_id,
                event_type,
                from_hash,
                to_hash,
                version,
                json.dumps(details) if details else None,
                self.clock.now_iso(),
            ),
        )

    def mark_superseded(self, old_id: str, by_id: str) -> None:
        """Flip a resource to 'superseded' and link it to its replacement.

        Loads the record, mutates the metadata, and re-upserts so the promoted
        columns and the full JSON stay in lock-step (single write path).
        """
        meta = self.get(old_id)
        if meta is None:
            return
        meta.lifecycle.record_status = _RecordStatus.SUPERSEDED
        meta.lifecycle.superseded_by = by_id
        meta.touch()
        self.upsert_resource(meta)

    # -- read ------------------------------------------------------------- #
    def exists(self, resource_id: str) -> bool:
        return (
            self.db.query_one("SELECT 1 FROM resources WHERE resource_id = ?", (resource_id,))
            is not None
        )

    def get(self, resource_id: str) -> ResourceMetadata | None:
        row = self.db.query_one(
            "SELECT metadata_json FROM resources WHERE resource_id = ?", (resource_id,)
        )
        return _parse(row["metadata_json"]) if row else None

    def get_row(self, resource_id: str) -> dict | None:
        row = self.db.query_one("SELECT * FROM resources WHERE resource_id = ?", (resource_id,))
        return dict(row) if row else None

    def find_by_sha256(self, sha256: str) -> list[dict]:
        rows = self.db.query("SELECT * FROM resources WHERE sha256 = ?", (sha256,))
        return [dict(r) for r in rows]

    def find_by_content_hash(self, content_hash: str) -> list[dict]:
        rows = self.db.query(
            "SELECT * FROM resources WHERE content_hash = ?", (content_hash,)
        )
        return [dict(r) for r in rows]

    def list_all(self, record_status: str | None = "active") -> list[dict]:
        if record_status:
            rows = self.db.query(
                "SELECT * FROM resources WHERE record_status = ? ORDER BY resource_id",
                (record_status,),
            )
        else:
            rows = self.db.query("SELECT * FROM resources ORDER BY resource_id")
        return [dict(r) for r in rows]

    def filter(self, **criteria: Any) -> list[dict]:
        """Filter by any promoted, filterable column (AND semantics)."""
        clauses, params = [], []
        for key, val in criteria.items():
            if key not in _FILTERABLE:
                raise ValueError(f"'{key}' is not a filterable column: {sorted(_FILTERABLE)}")
            clauses.append(f"{key} = ?")
            params.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.query(f"SELECT * FROM resources {where} ORDER BY resource_id", params)
        return [dict(r) for r in rows]

    def search(self, text: str, limit: int = 50) -> list[dict]:
        """Substring search over title, module, lecture, and the full JSON blob.

        The JSON scan catches topics/keywords/tags/objectives without a separate
        column. Adequate for a lightweight catalog; FTS5 is the named upgrade.
        """
        like = f"%{text}%"
        rows = self.db.query(
            "SELECT * FROM resources WHERE "
            "title LIKE ? OR module LIKE ? OR lecture LIKE ? OR metadata_json LIKE ? "
            "ORDER BY resource_id LIMIT ?",
            (like, like, like, like, limit),
        )
        return [dict(r) for r in rows]

    def count(self, **criteria: Any) -> int:
        rows = self.filter(**criteria) if criteria else self.list_all(record_status=None)
        return len(rows)

    def get_events(self, resource_id: str) -> list[dict]:
        rows = self.db.query(
            "SELECT * FROM resource_events WHERE resource_id = ? ORDER BY id", (resource_id,)
        )
        return [dict(r) for r in rows]

    # -- statistics (dashboard-ready) ------------------------------------- #
    def statistics(self) -> dict[str, Any]:
        def group(col: str) -> dict[str, int]:
            rows = self.db.query(
                f"SELECT {col} AS k, COUNT(*) AS n FROM resources GROUP BY {col}"
            )
            return {(r["k"] or "unknown"): r["n"] for r in rows}

        totals = self.db.query_one(
            "SELECT COUNT(*) AS n, COALESCE(SUM(file_size),0) AS bytes, "
            "COALESCE(SUM(chunk_count),0) AS chunks FROM resources"
        )
        return {
            "total_resources": totals["n"] if totals else 0,
            "total_bytes": totals["bytes"] if totals else 0,
            "total_chunks": totals["chunks"] if totals else 0,
            "by_track": group("track"),
            "by_course": group("course"),
            "by_doc_type": group("doc_type"),
            "by_language": group("language"),
            "by_processing_status": group("processing_status"),
            "by_record_status": group("record_status"),
            "by_validation_status": group("validation_status"),
            "catalog_schema_version": self.get_meta("catalog_schema_version"),
            "last_updated": self.get_meta("last_updated"),
        }

    def close(self) -> None:
        self.db.close()


# --------------------------------------------------------------------------- #
def _parse(metadata_json: str) -> ResourceMetadata:
    return ResourceMetadata.from_dict(json.loads(metadata_json))
