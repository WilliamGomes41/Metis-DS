-- Immutable derived source views; no input/context/task identity changes or backfill.
CREATE TABLE IF NOT EXISTS workflow.formation_source_views (
    views_id TEXT PRIMARY KEY,
    extraction_hash TEXT NOT NULL REFERENCES workflow.prepared_extraction_versions(record_hash) ON DELETE CASCADE,
    payload_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
