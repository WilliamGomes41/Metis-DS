-- A confirmed source can have no headings. Its coverage then has one section.
ALTER TABLE workflow.annotation_structure_confirmations
    DROP CONSTRAINT IF EXISTS annotation_structure_confirmations_check,
    ADD CONSTRAINT annotation_structure_confirmations_check CHECK (
        jsonb_typeof(definition)='object'
        AND definition ?& ARRAY['version','entries','extraction_hash','working_revision_id']
        AND definition->'version'='1'::jsonb
        AND jsonb_typeof(definition->'entries') IS NOT DISTINCT FROM 'array'
        AND (definition->>'extraction_hash') IS NOT DISTINCT FROM extraction_hash
        AND (definition->>'working_revision_id') IS NOT DISTINCT FROM working_revision_id
    );

CREATE TABLE IF NOT EXISTS workflow.annotation_round_events (
    snapshot_id TEXT NOT NULL REFERENCES workflow.annotation_sets(snapshot_id) ON DELETE CASCADE,
    revision BIGINT NOT NULL CHECK (revision > 0),
    phase TEXT NOT NULL CHECK (phase IN ('annotating','checking')),
    generation BIGINT NOT NULL CHECK (generation >= 0),
    actor_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_id, revision)
);

DROP TRIGGER IF EXISTS guard_annotation_round_history ON workflow.annotation_round_events;
CREATE TRIGGER guard_annotation_round_history BEFORE UPDATE OR DELETE ON workflow.annotation_round_events
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_history();

CREATE OR REPLACE FUNCTION workflow.guard_annotation_document_check_seal() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE check_input JSONB := NEW.payload->'document_check';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM workflow.annotation_round_events WHERE snapshot_id=NEW.snapshot_id) THEN
        IF check_input IS NOT NULL THEN
            RAISE EXCEPTION 'annotation_document_check_seal_mismatch';
        END IF;
        RETURN NEW;
    END IF;
    IF check_input IS NULL OR check_input->'version' IS DISTINCT FROM '1'::jsonb
        OR NOT EXISTS (
            SELECT 1 FROM workflow.annotation_round_events e WHERE e.snapshot_id=NEW.snapshot_id
              AND e.phase='checking' AND e.generation<=NEW.generation
              AND jsonb_build_object('revision',e.revision,'phase',e.phase,
                                     'generation',e.generation,'actor_id',e.actor_id)=check_input->'round'
        ) THEN
        RAISE EXCEPTION 'annotation_document_check_seal_mismatch';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_document_check_seal ON workflow.annotation_seals;
CREATE TRIGGER guard_annotation_document_check_seal BEFORE INSERT ON workflow.annotation_seals
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_document_check_seal();

CREATE OR REPLACE FUNCTION workflow.guard_annotation_document_check_attempt() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE
    input JSONB;
    latest JSONB;
    scope_input TEXT;
    receipts JSONB;
BEGIN
    IF NEW.payload->>'kind' IS DISTINCT FROM 'human_annotation_build'
        OR NEW.payload->>'state' IS DISTINCT FROM 'running' THEN
        RETURN NEW;
    END IF;
    SELECT s.payload->'document_check' INTO input FROM workflow.annotation_seals s
        WHERE s.seal_id=NEW.payload->>'annotation_seal_id' AND s.snapshot_id=NEW.snapshot_id;
    SELECT jsonb_build_object('revision',revision,'phase',phase,'generation',generation,'actor_id',actor_id)
        INTO latest FROM workflow.annotation_round_events WHERE snapshot_id=NEW.snapshot_id
        ORDER BY revision DESC LIMIT 1;
    IF latest IS NULL AND input IS NULL THEN RETURN NEW; END IF;
    SELECT scope, confirmations INTO scope_input, receipts FROM workflow.annotation_section_coverage
        WHERE snapshot_id=NEW.snapshot_id;
    IF latest->>'phase' IS DISTINCT FROM 'checking' OR input->'round' IS DISTINCT FROM latest
        OR input->>'scope' IS DISTINCT FROM COALESCE(scope_input,'selection')
        OR input->'confirmations' IS DISTINCT FROM (CASE WHEN scope_input='full' THEN receipts ELSE '{}'::jsonb END) THEN
        RAISE EXCEPTION 'annotation_document_check_attempt_stale';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_document_check_attempt ON workflow.processing_attempts;
CREATE TRIGGER guard_annotation_document_check_attempt BEFORE INSERT ON workflow.processing_attempts
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_document_check_attempt();
