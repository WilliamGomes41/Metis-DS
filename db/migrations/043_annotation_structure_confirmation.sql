CREATE TABLE IF NOT EXISTS workflow.annotation_structure_confirmations (
    snapshot_id TEXT PRIMARY KEY REFERENCES workflow.annotation_sets(snapshot_id) ON DELETE CASCADE,
    extraction_hash TEXT NOT NULL REFERENCES workflow.prepared_extraction_versions(record_hash),
    working_revision_id TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    definition JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jsonb_typeof(definition)='object' AND definition ?& ARRAY['version','entries','extraction_hash','working_revision_id']
           AND definition->'version'='1'::jsonb AND jsonb_typeof(definition->'entries') IS NOT DISTINCT FROM 'array'
           AND jsonb_array_length(definition->'entries')>0
           AND (definition->>'extraction_hash') IS NOT DISTINCT FROM extraction_hash
           AND (definition->>'working_revision_id') IS NOT DISTINCT FROM working_revision_id)
);

CREATE OR REPLACE FUNCTION workflow.guard_annotation_structure_confirmation() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
    PERFORM 1 FROM workflow.annotation_sets
      WHERE snapshot_id=NEW.snapshot_id AND extraction_hash=NEW.extraction_hash
      AND working_revision_id=NEW.working_revision_id FOR UPDATE;
    IF NOT FOUND OR EXISTS (SELECT 1 FROM workflow.annotation_seals WHERE snapshot_id=NEW.snapshot_id) THEN
        RAISE EXCEPTION 'annotation_structure_basis_invalid';
    END IF;
    RETURN NEW;
END
$body$;

DROP TRIGGER IF EXISTS guard_annotation_structure_insert ON workflow.annotation_structure_confirmations;
CREATE TRIGGER guard_annotation_structure_insert BEFORE INSERT ON workflow.annotation_structure_confirmations
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_structure_confirmation();
DROP TRIGGER IF EXISTS guard_annotation_structure_history ON workflow.annotation_structure_confirmations;
CREATE TRIGGER guard_annotation_structure_history BEFORE UPDATE OR DELETE ON workflow.annotation_structure_confirmations
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_history();

CREATE OR REPLACE FUNCTION workflow.guard_annotation_structure_seal() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
    IF NEW.payload->'confirmed_document_structure' IS DISTINCT FROM (
        SELECT definition FROM workflow.annotation_structure_confirmations WHERE snapshot_id=NEW.snapshot_id
    ) THEN
        RAISE EXCEPTION 'annotation_structure_seal_mismatch';
    END IF;
    RETURN NEW;
END
$body$;

DROP TRIGGER IF EXISTS guard_annotation_structure_seal ON workflow.annotation_seals;
CREATE TRIGGER guard_annotation_structure_seal BEFORE INSERT ON workflow.annotation_seals
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_structure_seal();
