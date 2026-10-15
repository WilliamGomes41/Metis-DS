-- #629 F1 (Metis): separate append-only refusal audit store, outside the review ledger hash chain.
-- EXPAND only, idempotent. Rows are NOOIT updated; retention deletes by age / row bound (application).
CREATE TABLE IF NOT EXISTS workflow.publication_refusals (
    refusal_id BIGSERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL,
    snapshot_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    actor TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict = 'refused'),
    reason_codes JSONB NOT NULL,
    revision_sha256 TEXT NULL,
    dedup_key TEXT NOT NULL,
    schema_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS publication_refusals_dedup_idx ON workflow.publication_refusals (dedup_key, recorded_at DESC);
CREATE INDEX IF NOT EXISTS publication_refusals_snapshot_idx ON workflow.publication_refusals (snapshot_id, refusal_id DESC);
CREATE INDEX IF NOT EXISTS publication_refusals_recorded_idx ON workflow.publication_refusals (recorded_at);
