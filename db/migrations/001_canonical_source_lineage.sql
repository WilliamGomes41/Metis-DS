-- Durable source lineage for published canonical knowledge.
-- Apply after db/schema_v2.sql.

CREATE TABLE IF NOT EXISTS source_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_checksum TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_object_sources (
    object_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id),
    PRIMARY KEY (object_id, object_version),
    FOREIGN KEY (object_id, object_version)
      REFERENCES canonical_object_versions(object_id, object_version)
);

CREATE INDEX IF NOT EXISTS idx_cos_snapshot
ON canonical_object_sources(snapshot_id);
