-- ============================================================================
-- ALA Knowledge Catalog — SQLite schema (Task 3)
-- ----------------------------------------------------------------------------
-- Promoted columns are the queryable/filterable projection; the complete
-- ResourceMetadata is ALSO stored as JSON in resources.metadata_json so no
-- field is ever lost. resource_events is the append-only history that powers
-- version tracking, change detection audit, and provenance.
-- ============================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS catalog_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS resources (
    resource_id        TEXT PRIMARY KEY,
    parent_resource_id TEXT,
    title              TEXT NOT NULL,

    -- classification
    track              TEXT,
    course             TEXT,
    subject            TEXT,
    module             TEXT,
    week               INTEGER,
    lecture            TEXT,
    doc_type           TEXT,
    role               TEXT,
    language           TEXT,
    parallel_group     TEXT,

    -- lifecycle / versioning
    record_status      TEXT NOT NULL DEFAULT 'active',
    version            INTEGER NOT NULL DEFAULT 1,
    persistence        TEXT NOT NULL DEFAULT 'permanent',

    -- file & integrity
    file_path          TEXT,
    file_name          TEXT,
    file_size          INTEGER,
    sha256             TEXT,
    content_hash       TEXT,
    created_date       TEXT,
    last_modified      TEXT,

    -- pipeline status
    processing_status  TEXT NOT NULL DEFAULT 'pending',
    ocr_status         TEXT,
    embedding_status   TEXT,
    graph_status       TEXT,
    vector_status      TEXT,
    validation_status  TEXT,
    chunk_count        INTEGER NOT NULL DEFAULT 0,
    difficulty         TEXT,

    -- academic / M1.5 promoted columns (filterable; full data in metadata_json)
    difficulty_score   REAL,
    course_code        TEXT,
    instructor         TEXT,
    lab_required       INTEGER NOT NULL DEFAULT 0,
    has_video          INTEGER NOT NULL DEFAULT 0,
    has_web            INTEGER NOT NULL DEFAULT 0,

    -- record bookkeeping
    schema_version     TEXT,
    created_at         TEXT,
    updated_at         TEXT,
    last_indexed_at    TEXT,

    -- full fidelity
    metadata_json      TEXT NOT NULL
);

-- Indices for the fast lookups / filters Task 3 requires.
CREATE INDEX IF NOT EXISTS idx_resources_sha256        ON resources(sha256);
CREATE INDEX IF NOT EXISTS idx_resources_content_hash  ON resources(content_hash);
CREATE INDEX IF NOT EXISTS idx_resources_track_course  ON resources(track, course);
CREATE INDEX IF NOT EXISTS idx_resources_language      ON resources(language);
CREATE INDEX IF NOT EXISTS idx_resources_doc_type      ON resources(doc_type);
CREATE INDEX IF NOT EXISTS idx_resources_proc_status   ON resources(processing_status);
CREATE INDEX IF NOT EXISTS idx_resources_record_status ON resources(record_status);
CREATE INDEX IF NOT EXISTS idx_resources_parent        ON resources(parent_resource_id);
CREATE INDEX IF NOT EXISTS idx_resources_parallel      ON resources(parallel_group);
CREATE INDEX IF NOT EXISTS idx_resources_course_code   ON resources(course_code);

-- Append-only event log: registrations, updates, content changes, status
-- transitions, supersessions. Never deleted -> full provenance/audit trail.
CREATE TABLE IF NOT EXISTS resource_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id  TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    from_hash    TEXT,
    to_hash      TEXT,
    version      INTEGER,
    details_json TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_resource ON resource_events(resource_id);
CREATE INDEX IF NOT EXISTS idx_events_type     ON resource_events(event_type);
