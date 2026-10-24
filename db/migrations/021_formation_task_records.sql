-- Expand only. No historical backfill, deletion or automatic context cutover.
ALTER TABLE workflow.documents ADD COLUMN IF NOT EXISTS processing_storage_version INTEGER;
ALTER TABLE workflow.documents ADD COLUMN IF NOT EXISTS object_generation BIGINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS workflow.processing_attempts (
    attempt_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id),
    command_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    object_generation BIGINT NOT NULL,
    payload JSONB NOT NULL,
    UNIQUE(snapshot_id,command_id)
);
CREATE INDEX IF NOT EXISTS processing_attempts_document_order
    ON workflow.processing_attempts(snapshot_id,started_at,attempt_id);
CREATE INDEX IF NOT EXISTS processing_attempts_dispatch
    ON workflow.processing_attempts((payload->>'state'),(payload->'dispatch'->>'state'));

CREATE TABLE IF NOT EXISTS workflow.processing_document_summaries (
    snapshot_id TEXT PRIMARY KEY REFERENCES workflow.documents(snapshot_id),
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow.processing_checkpoints (
    checkpoint_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES workflow.processing_attempts(attempt_id),
    phase TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS processing_checkpoints_attempt
    ON workflow.processing_checkpoints(attempt_id,checkpoint_id);

CREATE TABLE IF NOT EXISTS workflow.prepared_extraction_versions (
    record_hash TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id),
    payload JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow.formation_inputs (
    artifact_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id),
    extraction_hash TEXT NOT NULL REFERENCES workflow.prepared_extraction_versions(record_hash),
    payload JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow.formation_contexts (
    context_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id),
    artifact_id TEXT NOT NULL REFERENCES workflow.formation_inputs(artifact_id),
    semantic_identity JSONB NOT NULL,
    semantic_hash TEXT NOT NULL,
    expected_revision TEXT NOT NULL,
    planned_task_count INTEGER NOT NULL DEFAULT 0 CHECK (planned_task_count >= 0),
    completed_task_count INTEGER NOT NULL DEFAULT 0 CHECK (completed_task_count >= 0),
    final_result_hash TEXT,
    final_validation JSONB,
    UNIQUE(artifact_id,semantic_hash,expected_revision)
);
CREATE INDEX IF NOT EXISTS formation_contexts_document ON workflow.formation_contexts(snapshot_id);
CREATE TABLE IF NOT EXISTS workflow.formation_task_results (
    context_id TEXT NOT NULL REFERENCES workflow.formation_contexts(context_id),
    ranges_hash TEXT NOT NULL,
    source_ranges JSONB NOT NULL,
    result_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    attempt_id TEXT NOT NULL REFERENCES workflow.processing_attempts(attempt_id),
    claim_token TEXT,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(context_id,ranges_hash)
);
CREATE INDEX IF NOT EXISTS formation_task_results_attempt ON workflow.formation_task_results(attempt_id);
CREATE TABLE IF NOT EXISTS workflow.formation_task_findings (
    context_id TEXT NOT NULL REFERENCES workflow.formation_contexts(context_id),
    ranges_hash TEXT NOT NULL,
    result_hash TEXT NOT NULL,
    finding JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(context_id,ranges_hash,result_hash)
);
CREATE TABLE IF NOT EXISTS workflow.formation_task_result_history (
    context_id TEXT NOT NULL REFERENCES workflow.formation_contexts(context_id),
    ranges_hash TEXT NOT NULL,
    result_hash TEXT NOT NULL,
    source_ranges JSONB NOT NULL,
    payload JSONB NOT NULL,
    attempt_id TEXT NOT NULL REFERENCES workflow.processing_attempts(attempt_id),
    claim_token TEXT,
    committed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(context_id,ranges_hash,result_hash)
);

-- A small scalar detects concurrent object mutations without reading/hashing
-- every object's payload at each task checkpoint. Existing writers already own
-- the document row lock before touching objects.
CREATE OR REPLACE FUNCTION workflow.advance_object_generation() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
    UPDATE workflow.documents SET object_generation=object_generation+1
    WHERE snapshot_id=CASE WHEN TG_OP='DELETE' THEN OLD.snapshot_id ELSE NEW.snapshot_id END
      AND processing_storage_version=1;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS advance_object_generation ON workflow.document_objects;
CREATE TRIGGER advance_object_generation AFTER INSERT OR UPDATE OR DELETE ON workflow.document_objects
    FOR EACH ROW EXECUTE FUNCTION workflow.advance_object_generation();

-- Old binaries cannot silently recreate inline attempts in a cut-over context.
CREATE OR REPLACE FUNCTION workflow.guard_processing_storage() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
    IF OLD.processing_storage_version=1 THEN
        IF NEW.processing_storage_version IS DISTINCT FROM 1
           OR NEW.envelope_payload ? 'processing_attempts' THEN
            RAISE EXCEPTION 'processing_storage_compatible_writer_required';
        END IF;
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_processing_storage ON workflow.documents;
CREATE TRIGGER guard_processing_storage BEFORE UPDATE ON workflow.documents
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_processing_storage();
