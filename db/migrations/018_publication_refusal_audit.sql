-- #629 F1 (Metis): separate append-only refusal audit store, outside the review ledger hash chain.
-- EXPAND only, idempotent: safe twice and on top of the pre-UNIQUE 018 (Sherlock 02:10 F1).
-- Rows are NOOIT deleted by this migration; retention is the explicit maintenance command.
-- Applied BEFORE the code that uses it, only with William's GO (docs/TEST_AND_RELEASE_RUNBOOK.md).
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
-- Metis F1-4: one row per (document, reason codes, actor, 10-minute window). Named constraint,
-- guarded by pg_constraint (conname + conrelid). Legacy rows from the pre-UNIQUE 018 that share
-- a dedup_key keep their audit content; only the helper column dedup_key of the later duplicates
-- gets a 'legacy:<refusal_id>:' prefix, so the constraint can be added without deleting rows.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'publication_refusals_dedup_key_uniq'
          AND conrelid = 'workflow.publication_refusals'::regclass
    ) THEN
        UPDATE workflow.publication_refusals AS r
           SET dedup_key = 'legacy:' || r.refusal_id || ':' || r.dedup_key
         WHERE EXISTS (SELECT 1 FROM workflow.publication_refusals AS o
                        WHERE o.dedup_key = r.dedup_key AND o.refusal_id < r.refusal_id);
        ALTER TABLE workflow.publication_refusals
            ADD CONSTRAINT publication_refusals_dedup_key_uniq UNIQUE (dedup_key);
    END IF;
END
$$;
DROP INDEX IF EXISTS workflow.publication_refusals_dedup_idx;
CREATE INDEX IF NOT EXISTS publication_refusals_snapshot_idx ON workflow.publication_refusals (snapshot_id, refusal_id DESC);
CREATE INDEX IF NOT EXISTS publication_refusals_recorded_idx ON workflow.publication_refusals (recorded_at);
