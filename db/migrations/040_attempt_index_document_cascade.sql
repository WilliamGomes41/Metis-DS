-- Keep the attempt index immutable while its owning aggregate exists.
-- Whole-document deletion may reach the index before its attempt cascade.
-- Replacing the guard changes no rows, grants, FKs or runtime feature flags.
CREATE OR REPLACE FUNCTION workflow.guard_processing_attempt_input() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE original workflow.processing_attempts%ROWTYPE;
BEGIN
    IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'document_inputs_attempt_index_immutable'; END IF;
    IF TG_OP='DELETE' THEN
        IF EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=OLD.snapshot_id)
           AND EXISTS(SELECT 1 FROM workflow.processing_attempts WHERE attempt_id=OLD.attempt_id) THEN
            RAISE EXCEPTION 'document_inputs_attempt_index_immutable';
        END IF;
        RETURN OLD;
    END IF;
    SELECT * INTO original FROM workflow.processing_attempts WHERE attempt_id=NEW.attempt_id;
    IF NOT FOUND OR (NEW.snapshot_id,NEW.command_id,NEW.started_at,NEW.record_version)
            IS DISTINCT FROM (original.snapshot_id,original.command_id,original.started_at,original.record_version)
       OR NEW.state IS DISTINCT FROM original.payload->>'state'
       OR NEW.kind IS DISTINCT FROM original.payload->>'kind'
       OR NEW.progress_made IS DISTINCT FROM (original.payload->'formation_progress_made'='true'::jsonb)
       OR NOT workflow.exact_archive_json(NEW.payload::text::json,
            workflow.processing_attempt_input_for(original.payload)::text::json,true) THEN
        RAISE EXCEPTION 'document_inputs_attempt_index_changed';
    END IF;
    RETURN NEW;
END
$body$;
