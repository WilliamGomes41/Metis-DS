-- Expand only: an explicitly enabled publisher test-data operation owns removal.
-- Installing this migration deletes nothing and does not enable the feature.
CREATE TABLE IF NOT EXISTS workflow.test_document_deletions (
    command_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    logical_document_id TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 1000),
    result JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS workflow.deleted_test_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    command_id TEXT NOT NULL REFERENCES workflow.test_document_deletions(command_id),
    logical_document_id TEXT NOT NULL
);

CREATE OR REPLACE FUNCTION workflow.guard_test_deletion_history() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'test_document_deletion_history_immutable';
END;
$$;
DROP TRIGGER IF EXISTS guard_test_deletion_history ON workflow.test_document_deletions;
CREATE TRIGGER guard_test_deletion_history BEFORE UPDATE OR DELETE OR TRUNCATE
    ON workflow.test_document_deletions FOR EACH STATEMENT
    EXECUTE FUNCTION workflow.guard_test_deletion_history();
DROP TRIGGER IF EXISTS guard_deleted_test_snapshot_history ON workflow.deleted_test_snapshots;
CREATE TRIGGER guard_deleted_test_snapshot_history BEFORE UPDATE OR DELETE OR TRUNCATE
    ON workflow.deleted_test_snapshots FOR EACH STATEMENT
    EXECUTE FUNCTION workflow.guard_test_deletion_history();

-- A stale worker/rollback publisher must not reinsert a deleted snapshot, even
-- when it predates the new application code. A fresh upload has a fresh ID.
CREATE OR REPLACE FUNCTION workflow.refuse_deleted_test_snapshot() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM workflow.deleted_test_snapshots WHERE snapshot_id=NEW.snapshot_id) THEN
        RAISE EXCEPTION 'test_document_snapshot_deleted';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS refuse_deleted_test_document ON workflow.documents;
CREATE TRIGGER refuse_deleted_test_document BEFORE INSERT ON workflow.documents
    FOR EACH ROW EXECUTE FUNCTION workflow.refuse_deleted_test_snapshot();
DROP TRIGGER IF EXISTS refuse_deleted_test_source ON public.source_snapshots;
CREATE TRIGGER refuse_deleted_test_source BEFORE INSERT ON public.source_snapshots
    FOR EACH ROW EXECUTE FUNCTION workflow.refuse_deleted_test_snapshot();
