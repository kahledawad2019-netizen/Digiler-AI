"""Thin SQLite access layer.

Isolates all sqlite3 details (connection, pragmas, schema application, row
factory) so the repository speaks in dicts and never touches the driver.
``sqlite3`` is standard library -> zero-infra, in-process, matching the ChromaDB
rationale in Architecture V3.
"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

from ala.core.exceptions import CatalogError

_SCHEMA_RESOURCE = ("ala.catalog", "schema.sql")


class Database:
    """Owns one SQLite connection and knows how to initialise the schema."""

    def __init__(self, db_path: str | Path, journal_mode: str = "WAL") -> None:
        self.db_path = Path(db_path)
        self.journal_mode = journal_mode
        self._conn: sqlite3.Connection | None = None

    # -- lifecycle -------------------------------------------------------- #
    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            # check_same_thread=False: safe under sqlite3 SERIALIZED mode (threadsafety=3);
            # lets the API layer create/close the connection across threadpool workers.
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            # WAL only makes sense for on-disk DBs (not :memory:).
            if str(self.db_path) != ":memory:":
                try:
                    conn.execute(f"PRAGMA journal_mode = {self.journal_mode};")
                except sqlite3.Error:  # pragma: no cover - defensive
                    pass
            self._conn = conn
        return self._conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self.connect()

    def initialize(self) -> None:
        """Create tables/indices from schema.sql (idempotent)."""
        try:
            sql = (
                resources.files(_SCHEMA_RESOURCE[0])
                .joinpath(_SCHEMA_RESOURCE[1])
                .read_text(encoding="utf-8")
            )
        except (FileNotFoundError, ModuleNotFoundError) as exc:  # pragma: no cover
            raise CatalogError(f"Could not load catalog schema.sql: {exc}") from exc
        with self.conn as c:
            c.executescript(sql)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- helpers ---------------------------------------------------------- #
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        try:
            with self.conn as c:
                return c.execute(sql, tuple(params))
        except sqlite3.Error as exc:
            raise CatalogError(f"SQL error: {exc}\n  {sql}") from exc

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        try:
            cur = self.conn.execute(sql, tuple(params))
            return cur.fetchall()
        except sqlite3.Error as exc:
            raise CatalogError(f"SQL error: {exc}\n  {sql}") from exc

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # -- context manager -------------------------------------------------- #
    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
