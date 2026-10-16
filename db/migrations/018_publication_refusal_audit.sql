-- #629 F1 (Metis): separate append-only refusal audit store, outside the review ledger hash chain.
-- EXPAND only, idempotent: safe twice and on top of the pre-UNIQUE 018 (Sherlock 02:10 F1).
-- Rows are NOOIT updated or deleted by this migration; retention is the explicit maintenance command.
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
-- Metis F1-4: one row per (document, reason codes, actor, fixed 10-minute window). Named
-- constraint, guarded by pg_constraint (conname + conrelid).
-- Metis F1-5: this migration NOOIT changes audit rows. If the pre-UNIQUE 018 left duplicate
-- dedup_keys, 018 MOET fail with the count and the keys; a human decides (runbook).
DO $$
DECLARE
    dup_count BIGINT;
    dup_keys TEXT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'publication_refusals_dedup_key_uniq'
          AND conrelid = 'workflow.publication_refusals'::regclass
    ) THEN
        SELECT count(*), string_agg(dedup_key, ', ' ORDER BY dedup_key)
          INTO dup_count, dup_keys
          FROM (SELECT dedup_key FROM workflow.publication_refusals
                GROUP BY dedup_key HAVING count(*) > 1) AS d;
        IF dup_count > 0 THEN
            RAISE EXCEPTION 'publication_refusals_duplicate_dedup_keys count=% keys=%', dup_count, dup_keys
                USING HINT = 'See docs/TEST_AND_RELEASE_RUNBOOK.md, Migratie 018: a human decides; 018 changes no rows.';
        END IF;
        ALTER TABLE workflow.publication_refusals
            ADD CONSTRAINT publication_refusals_dedup_key_uniq UNIQUE (dedup_key);
    END IF;
END
$$;
DROP INDEX IF EXISTS workflow.publication_refusals_dedup_idx;
CREATE INDEX IF NOT EXISTS publication_refusals_snapshot_idx ON workflow.publication_refusals (snapshot_id, refusal_id DESC);
CREATE INDEX IF NOT EXISTS publication_refusals_recorded_idx ON workflow.publication_refusals (recorded_at);
