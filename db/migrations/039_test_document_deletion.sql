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
-- Workflow-only installations may not have canonical lineage migration 001 yet.
-- Keep those existing workflows usable; deletion stays blocked until the source
-- table and its fence are installed and verified by rerunning this migration.
DO $$
BEGIN
    IF to_regclass('public.source_snapshots') IS NOT NULL THEN
        DROP TRIGGER IF EXISTS refuse_deleted_test_source ON public.source_snapshots;
        CREATE TRIGGER refuse_deleted_test_source BEFORE INSERT ON public.source_snapshots
            FOR EACH ROW EXECUTE FUNCTION workflow.refuse_deleted_test_snapshot();
    END IF;
END;
$$;

-- These operational tables deliberately have no document FK. Serialize their
-- writers with deletion and then read the durable fence under that same lock;
-- a request validated before deletion cannot register an orphan afterwards.
CREATE OR REPLACE FUNCTION workflow.refuse_deleted_test_operational_row() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(2110039,hashtext(NEW.snapshot_id));
    IF EXISTS(SELECT 1 FROM workflow.deleted_test_snapshots WHERE snapshot_id=NEW.snapshot_id) THEN
        RAISE EXCEPTION 'test_document_snapshot_deleted';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS refuse_deleted_test_view_check ON workflow.view_checks;
CREATE TRIGGER refuse_deleted_test_view_check BEFORE INSERT OR UPDATE ON workflow.view_checks
    FOR EACH ROW EXECUTE FUNCTION workflow.refuse_deleted_test_operational_row();
DROP TRIGGER IF EXISTS refuse_deleted_test_publication_refusal ON workflow.publication_refusals;
CREATE TRIGGER refuse_deleted_test_publication_refusal BEFORE INSERT OR UPDATE ON workflow.publication_refusals
    FOR EACH ROW EXECUTE FUNCTION workflow.refuse_deleted_test_operational_row();

-- Older backup exporters still retain the global review ledger. Its deletion
-- event must never be restored without the receipt and every snapshot fence.
-- Deferred checking also supports the existing one-transaction empty-target
-- restore; an older reader which omits these tables cannot commit its import.
CREATE OR REPLACE FUNCTION workflow.guard_test_deletion_ledger() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF NEW.event_type='test_document_deleted' OR NEW.event_payload->>'event_type'='test_document_deleted' THEN
        IF NOT EXISTS (
            SELECT 1 FROM workflow.test_document_deletions d
            WHERE d.command_id=NEW.event_payload#>>'{details,command_id}'
              AND d.logical_document_id=NEW.event_payload#>>'{details,logical_document_id}'
              AND jsonb_typeof(d.result->'snapshot_ids')='array'
              AND jsonb_array_length(d.result->'snapshot_ids')>0
              AND NOT EXISTS (
                  SELECT 1 FROM jsonb_array_elements_text(d.result->'snapshot_ids') AS ids(snapshot_id)
                  LEFT JOIN workflow.deleted_test_snapshots s ON s.snapshot_id=ids.snapshot_id
                  WHERE s.snapshot_id IS NULL OR s.command_id<>d.command_id
                     OR s.logical_document_id<>d.logical_document_id
              )
        ) THEN RAISE EXCEPTION 'test_document_deletion_recovery_required'; END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS guard_test_deletion_ledger ON workflow.review_events;
CREATE CONSTRAINT TRIGGER guard_test_deletion_ledger AFTER INSERT OR UPDATE ON workflow.review_events
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    WHEN (NEW.event_type='test_document_deleted' OR NEW.event_payload->>'event_type'='test_document_deleted')
    EXECUTE FUNCTION workflow.guard_test_deletion_ledger();
