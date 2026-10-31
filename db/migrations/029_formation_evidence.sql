-- Add complete immutable producer evidence; no historical or publication cutover.
CREATE TABLE IF NOT EXISTS workflow.formation_evidence_roots (
    proof_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    context_id TEXT NOT NULL REFERENCES workflow.formation_contexts(context_id) DEFERRABLE INITIALLY DEFERRED,
    extraction_hash TEXT NOT NULL REFERENCES workflow.prepared_extraction_versions(record_hash) DEFERRABLE INITIALLY DEFERRED,
    header JSONB NOT NULL,
    sealed BOOLEAN NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS workflow.formation_evidence_members (
    proof_id TEXT NOT NULL REFERENCES workflow.formation_evidence_roots(proof_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('replay','input','source','plan','result','checkpoint')),
    member_key TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    payload_text TEXT NOT NULL,
    PRIMARY KEY(proof_id,role,member_key),
    CHECK(payload_hash=encode(sha256(convert_to(payload_text,'UTF8')),'hex'))
);
CREATE INDEX IF NOT EXISTS formation_evidence_member_identity ON workflow.formation_evidence_members(role,member_key);
ALTER TABLE workflow.documents ADD COLUMN IF NOT EXISTS formation_evidence_id TEXT
    REFERENCES workflow.formation_evidence_roots(proof_id) DEFERRABLE INITIALLY DEFERRED;

CREATE OR REPLACE FUNCTION workflow.guard_formation_evidence_root() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'formation_evidence_immutable'; END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.sealed OR NEW.header->>'layout' IS DISTINCT FROM '1'
           OR NEW.header#>>'{source,snapshot_id}' IS DISTINCT FROM NEW.snapshot_id
           OR NEW.header#>>'{capture,context_id}' IS DISTINCT FROM NEW.context_id
           OR NEW.header->>'extraction_hash' IS DISTINCT FROM NEW.extraction_hash THEN
            RAISE EXCEPTION 'formation_evidence_root_invalid';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP='DELETE' THEN
        IF EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=OLD.snapshot_id) THEN
            RAISE EXCEPTION 'formation_evidence_immutable';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.sealed OR NOT NEW.sealed OR NEW.proof_id<>OLD.proof_id OR NEW.snapshot_id<>OLD.snapshot_id
       OR NEW.context_id<>OLD.context_id OR NEW.extraction_hash<>OLD.extraction_hash OR NEW.header<>OLD.header THEN
        RAISE EXCEPTION 'formation_evidence_immutable';
    END IF;
    IF (SELECT COALESCE(jsonb_agg(jsonb_build_array(role,member_key,payload_hash) ORDER BY role,member_key),'[]'::jsonb)
        FROM workflow.formation_evidence_members WHERE proof_id=NEW.proof_id)
        IS DISTINCT FROM NEW.header->'manifest' THEN
        RAISE EXCEPTION 'formation_evidence_membership_incomplete';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_formation_evidence_root ON workflow.formation_evidence_roots;
CREATE TRIGGER guard_formation_evidence_root BEFORE INSERT OR UPDATE OR DELETE ON workflow.formation_evidence_roots
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_formation_evidence_root();
DROP TRIGGER IF EXISTS guard_formation_evidence_root_truncate ON workflow.formation_evidence_roots;
CREATE TRIGGER guard_formation_evidence_root_truncate BEFORE TRUNCATE ON workflow.formation_evidence_roots
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_formation_evidence_root();

CREATE OR REPLACE FUNCTION workflow.guard_formation_evidence_member() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE protected BOOLEAN;
BEGIN
    IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'formation_evidence_immutable'; END IF;
    SELECT sealed INTO protected FROM workflow.formation_evidence_roots
        WHERE proof_id=CASE WHEN TG_OP='INSERT' THEN NEW.proof_id ELSE OLD.proof_id END FOR UPDATE;
    IF protected OR TG_OP='UPDATE' OR (NOT FOUND AND TG_OP<>'DELETE') THEN
        RAISE EXCEPTION 'formation_evidence_immutable';
    END IF;
    RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END
$body$;
DROP TRIGGER IF EXISTS guard_formation_evidence_member ON workflow.formation_evidence_members;
CREATE TRIGGER guard_formation_evidence_member BEFORE INSERT OR UPDATE OR DELETE ON workflow.formation_evidence_members
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_formation_evidence_member();
DROP TRIGGER IF EXISTS guard_formation_evidence_member_truncate ON workflow.formation_evidence_members;
CREATE TRIGGER guard_formation_evidence_member_truncate BEFORE TRUNCATE ON workflow.formation_evidence_members
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_formation_evidence_member();

CREATE OR REPLACE FUNCTION workflow.require_sealed_formation_evidence() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF EXISTS(SELECT 1 FROM workflow.formation_evidence_roots WHERE proof_id=NEW.proof_id AND NOT sealed) THEN
        RAISE EXCEPTION 'formation_evidence_membership_incomplete';
    END IF;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS require_sealed_formation_evidence ON workflow.formation_evidence_roots;
CREATE CONSTRAINT TRIGGER require_sealed_formation_evidence AFTER INSERT ON workflow.formation_evidence_roots
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.require_sealed_formation_evidence();

CREATE OR REPLACE FUNCTION workflow.guard_evidence_validator_compatibility() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF NEW.final_validation IS NOT NULL AND COALESCE((NEW.final_validation->>'version')::integer,0)<3
       AND EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id AND formation_evidence_id IS NOT NULL) THEN
        RAISE EXCEPTION 'formation_evidence_compatible_writer_required';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_evidence_validator_compatibility ON workflow.formation_contexts;
CREATE TRIGGER guard_evidence_validator_compatibility BEFORE INSERT OR UPDATE ON workflow.formation_contexts
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_evidence_validator_compatibility();

CREATE OR REPLACE FUNCTION workflow.guard_active_formation_evidence() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE document workflow.documents%ROWTYPE; proof workflow.formation_evidence_roots%ROWTYPE;
BEGIN
    -- Generation-only object updates do not fetch any proof/archive. Unchanged
    -- metadata writes likewise never hydrate a retained producer record.
    IF TG_OP='UPDATE' AND OLD.formation_evidence_id IS NOT NULL AND NEW.formation_evidence_id IS NULL THEN
        RAISE EXCEPTION 'formation_evidence_pin_required';
    END IF;
    IF TG_OP='UPDATE' AND NEW.formation_evidence_id IS NOT DISTINCT FROM OLD.formation_evidence_id
       AND NEW.review_source_ref IS NOT DISTINCT FROM OLD.review_source_ref
       AND NEW.envelope_payload#>>'{prepared_source_extraction,record_hash}'
           IS NOT DISTINCT FROM OLD.envelope_payload#>>'{prepared_source_extraction,record_hash}'
       AND NEW.envelope_payload->'semantic_replay' IS NOT DISTINCT FROM OLD.envelope_payload->'semantic_replay'
       AND (NEW.snapshot_id,NEW.source_id,NEW.document_id,NEW.source_sha256,NEW.source_version,
            NEW.content_kind,NEW.logical_document_id,NEW.working_revision_id)
           IS NOT DISTINCT FROM
           (OLD.snapshot_id,OLD.source_id,OLD.document_id,OLD.source_sha256,OLD.source_version,
            OLD.content_kind,OLD.logical_document_id,OLD.working_revision_id) THEN
        RETURN NULL;
    END IF;
    -- Deferred: read the final row, not the intermediate row while its pin and
    -- envelope are being staged inside the existing object transaction.
    SELECT * INTO document FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id;
    IF NOT FOUND OR document.formation_evidence_id IS NULL THEN RETURN NULL; END IF;
    SELECT * INTO proof FROM workflow.formation_evidence_roots WHERE proof_id=document.formation_evidence_id;
    IF NOT FOUND OR NOT proof.sealed OR proof.snapshot_id<>document.snapshot_id
       OR proof.header#>'{capture,source_ref}' IS DISTINCT FROM document.review_source_ref
       OR proof.extraction_hash IS DISTINCT FROM document.envelope_payload#>>'{prepared_source_extraction,record_hash}'
       OR proof.header->'source' IS DISTINCT FROM jsonb_build_object('snapshot_id',document.snapshot_id,
           'source_id',document.source_id,'document_id',document.document_id,'sha256',document.source_sha256,
           'version',document.source_version,'content_kind',document.content_kind,
           'logical_document_id',document.logical_document_id,'working_revision_id',document.working_revision_id)
       OR NOT EXISTS(SELECT 1 FROM workflow.formation_evidence_members WHERE proof_id=proof.proof_id
           AND role='replay' AND member_key='0'
           AND (payload_text::jsonb #- '{provider_evidence,formation_progress}')=document.envelope_payload->'semantic_replay') THEN
        RAISE EXCEPTION 'formation_evidence_active_binding_changed';
    END IF;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS guard_active_formation_evidence ON workflow.documents;
CREATE CONSTRAINT TRIGGER guard_active_formation_evidence
    AFTER INSERT OR UPDATE OF formation_evidence_id,review_source_ref,envelope_payload,source_id,document_id,source_sha256,
        source_version,content_kind,logical_document_id,working_revision_id ON workflow.documents
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.guard_active_formation_evidence();

CREATE OR REPLACE FUNCTION workflow.guard_active_evidence_attempt() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    -- A budget stop without activation must still be recordable and resumable.
    IF NEW.payload->>'state'='succeeded'
       AND COALESCE(NEW.payload#>>'{diagnostic,final_validation,version}','')<>'3'
       AND EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id AND formation_evidence_id IS NOT NULL) THEN
        RAISE EXCEPTION 'formation_evidence_compatible_writer_required';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_active_evidence_attempt ON workflow.processing_attempts;
CREATE TRIGGER guard_active_evidence_attempt BEFORE INSERT OR UPDATE ON workflow.processing_attempts
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_active_evidence_attempt();
