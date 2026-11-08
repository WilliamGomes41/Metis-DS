-- Expand: input within the existing WorkingRevision, never candidates/reviews.
CREATE TABLE IF NOT EXISTS workflow.annotation_sets (
    snapshot_id TEXT PRIMARY KEY REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    working_revision_id TEXT NOT NULL,
    extraction_hash TEXT NOT NULL REFERENCES workflow.prepared_extraction_versions(record_hash),
    source_identity JSONB NOT NULL,
    objects_revision TEXT NOT NULL,
    normalization TEXT NOT NULL CHECK (normalization='metis-visible-prose-codepoints-v1'),
    generation BIGINT NOT NULL DEFAULT 0 CHECK (generation>=0),
    created_by TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS workflow.annotation_versions (
    snapshot_id TEXT NOT NULL REFERENCES workflow.annotation_sets(snapshot_id) ON DELETE CASCADE,
    annotation_id TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision>0),
    status TEXT NOT NULL CHECK (status IN ('draft','ready','uncertain','withdrawn')),
    author_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    payload JSONB NOT NULL,
    payload_hash TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(snapshot_id,annotation_id,revision)
);
CREATE TABLE IF NOT EXISTS workflow.annotation_heads (
    snapshot_id TEXT NOT NULL,
    annotation_id TEXT NOT NULL,
    revision BIGINT NOT NULL,
    position BIGINT NOT NULL CHECK(position>=0),
    PRIMARY KEY(snapshot_id,annotation_id),
    FOREIGN KEY(snapshot_id) REFERENCES workflow.annotation_sets(snapshot_id) ON DELETE CASCADE,
    FOREIGN KEY(snapshot_id,annotation_id,revision)
        REFERENCES workflow.annotation_versions(snapshot_id,annotation_id,revision)
);
CREATE TABLE IF NOT EXISTS workflow.annotation_commands (
    snapshot_id TEXT NOT NULL REFERENCES workflow.annotation_sets(snapshot_id) ON DELETE CASCADE,
    command_id TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    request_hash TEXT NOT NULL,
    result JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(snapshot_id,command_id)
);

CREATE OR REPLACE FUNCTION workflow.guard_annotation_history() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF TG_OP='DELETE' AND NOT EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=OLD.snapshot_id) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'annotation_history_immutable';
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_versions ON workflow.annotation_versions;
CREATE TRIGGER guard_annotation_versions BEFORE UPDATE OR DELETE ON workflow.annotation_versions
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_history();
DROP TRIGGER IF EXISTS guard_annotation_commands ON workflow.annotation_commands;
CREATE TRIGGER guard_annotation_commands BEFORE UPDATE OR DELETE ON workflow.annotation_commands
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_history();

CREATE OR REPLACE FUNCTION workflow.guard_annotation_source() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF (NEW.snapshot_id,NEW.working_revision_id,NEW.extraction_hash,NEW.source_identity,NEW.objects_revision,NEW.normalization,NEW.created_by,NEW.created_at)
        IS DISTINCT FROM
       (OLD.snapshot_id,OLD.working_revision_id,OLD.extraction_hash,OLD.source_identity,OLD.objects_revision,OLD.normalization,OLD.created_by,OLD.created_at)
       OR NEW.generation<>OLD.generation+1 THEN
        RAISE EXCEPTION 'annotation_source_immutable';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_source ON workflow.annotation_sets;
CREATE TRIGGER guard_annotation_source BEFORE UPDATE ON workflow.annotation_sets
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_source();

-- Fail closed even for a rollback writer which predates annotation commands.
-- HA-2b must replace this fence with the versioned human-proof activation check;
-- a flag or a caller claiming to be human may not bypass it.
CREATE OR REPLACE FUNCTION workflow.guard_annotation_legacy_writes() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
    IF EXISTS(SELECT 1 FROM annotation_written w
        JOIN workflow.annotation_sets s USING(snapshot_id)
        JOIN workflow.documents d USING(snapshot_id)) THEN
        RAISE EXCEPTION 'annotation_activation_not_available';
    END IF;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_object_insert ON workflow.document_objects;
CREATE TRIGGER guard_annotation_object_insert AFTER INSERT ON workflow.document_objects
    REFERENCING NEW TABLE AS annotation_written FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_annotation_legacy_writes();
DROP TRIGGER IF EXISTS guard_annotation_object_update ON workflow.document_objects;
CREATE TRIGGER guard_annotation_object_update AFTER UPDATE ON workflow.document_objects
    REFERENCING NEW TABLE AS annotation_written FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_annotation_legacy_writes();
DROP TRIGGER IF EXISTS guard_annotation_object_delete ON workflow.document_objects;
CREATE TRIGGER guard_annotation_object_delete AFTER DELETE ON workflow.document_objects
    REFERENCING OLD TABLE AS annotation_written FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_annotation_legacy_writes();

CREATE OR REPLACE FUNCTION workflow.guard_annotation_legacy_attempt() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
    IF EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id) THEN
        RAISE EXCEPTION 'annotation_source_owned';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_legacy_attempt ON workflow.processing_attempts;
CREATE TRIGGER guard_annotation_legacy_attempt BEFORE INSERT OR UPDATE ON workflow.processing_attempts
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_legacy_attempt();
DROP TRIGGER IF EXISTS guard_annotation_legacy_attempt_input ON workflow.processing_attempt_inputs;
CREATE TRIGGER guard_annotation_legacy_attempt_input BEFORE INSERT OR UPDATE ON workflow.processing_attempt_inputs
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_legacy_attempt();

CREATE OR REPLACE FUNCTION workflow.guard_annotated_document() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
    IF EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id) AND (
        (NEW.source_id,NEW.document_id,NEW.source_sha256,NEW.source_version,NEW.content_kind,NEW.working_revision_id,NEW.logical_document_id)
            IS DISTINCT FROM (OLD.source_id,OLD.document_id,OLD.source_sha256,OLD.source_version,OLD.content_kind,OLD.working_revision_id,OLD.logical_document_id)
        OR NEW.envelope_payload->'processing_attempts' IS DISTINCT FROM OLD.envelope_payload->'processing_attempts'
        OR NEW.envelope_payload->'semantic_replay' IS DISTINCT FROM OLD.envelope_payload->'semantic_replay'
    ) THEN
        RAISE EXCEPTION 'annotation_source_immutable';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotated_document ON workflow.documents;
CREATE TRIGGER guard_annotated_document BEFORE UPDATE ON workflow.documents
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotated_document();
