-- Expand only: no envelope backfill, activation pin, read hook or status change.
-- Diagnostic provenance is not a validated formation-proof or review decision.
CREATE TABLE IF NOT EXISTS workflow.processing_archives (
    archive_id TEXT PRIMARY KEY CHECK (archive_id ~ '^[0-9a-f]{64}$'),
    layout INTEGER NOT NULL CHECK (layout = 1),
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('semantic_replay','quality_processing_run')),
    record_key TEXT NOT NULL CHECK (length(record_key) BETWEEN 1 AND 256),
    binding JSONB NOT NULL,
    -- Objectset revision tokens can be large. Metadata selects only this hash,
    -- never truncates the original opaque precondition/provenance token.
    revision_hash TEXT NOT NULL CHECK (revision_hash ~ '^[0-9a-f]{64}$'),
    observed_revision TEXT NOT NULL CHECK (length(observed_revision) > 0),
    payload_hash TEXT NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    -- Preserve exact canonical JSON, including numeric types and old hashes;
    -- JSONB would normalize exponents and other valid numeric representations.
    payload_text TEXT NOT NULL,
    UNIQUE(snapshot_id,kind,record_key)
);

CREATE OR REPLACE FUNCTION workflow.guard_processing_archive()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE actual_binding JSONB;
BEGIN
    IF TG_OP='TRUNCATE' OR TG_OP='UPDATE' THEN
        RAISE EXCEPTION 'processing_archive_immutable';
    END IF;
    IF TG_OP='DELETE' THEN
        IF EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=OLD.snapshot_id) THEN
            RAISE EXCEPTION 'processing_archive_immutable';
        END IF;
        RETURN OLD; -- Only existing whole-document cascade; no new GC authority.
    END IF;
    SELECT jsonb_build_object('snapshot_id',snapshot_id,'source_id',source_id,
        'document_id',document_id,'sha256',source_sha256,'version',source_version,
        'content_kind',content_kind,'logical_document_id',logical_document_id,
        'working_revision_id',working_revision_id)
        INTO actual_binding FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id FOR SHARE;
    IF actual_binding IS NULL OR NEW.binding IS DISTINCT FROM actual_binding THEN
        RAISE EXCEPTION 'processing_archive_source_mismatch';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_processing_archive ON workflow.processing_archives;
CREATE TRIGGER guard_processing_archive BEFORE INSERT OR UPDATE OR DELETE ON workflow.processing_archives
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_processing_archive();
DROP TRIGGER IF EXISTS guard_processing_archive_truncate ON workflow.processing_archives;
CREATE TRIGGER guard_processing_archive_truncate BEFORE TRUNCATE ON workflow.processing_archives
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_processing_archive();
