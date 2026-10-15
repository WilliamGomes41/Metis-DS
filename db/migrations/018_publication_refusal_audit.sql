-- #629 F1 (Metis): separate append-only refusal audit store, outside the review ledger hash chain.
-- dedup_key is UNIQUE (Metis F1-4): one row per (document, reason codes, actor, 10-minute window).
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
    dedup_key TEXT NOT NULL UNIQUE,
    schema_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS publication_refusals_snapshot_idx ON workflow.publication_refusals (snapshot_id, refusal_id DESC);
CREATE INDEX IF NOT EXISTS publication_refusals_recorded_idx ON workflow.publication_refusals (recorded_at);
