-- Additive indexed access to fully verified immutable source views.
-- No source, object, review, publication or historical payload is rewritten.
ALTER TABLE workflow.documents ADD COLUMN IF NOT EXISTS review_source_ref JSONB;
ALTER TABLE workflow.documents ADD COLUMN IF NOT EXISTS review_read_envelope JSONB;

-- Compute once on existing envelope writes, not by detoasting immutable raw
-- extraction/processing archives on each passage read. No historical backfill.
CREATE OR REPLACE FUNCTION workflow.review_read_envelope_for(payload JSONB)
RETURNS JSONB LANGUAGE SQL IMMUTABLE STRICT AS $body$
    SELECT (payload - ARRAY['semantic_replay','processing_attempts','quality_processing_runs','prepared_source_extraction'])
      || CASE WHEN payload ? 'prepared_source_extraction' THEN
           jsonb_build_object('prepared_source_extraction',
             CASE WHEN jsonb_typeof(payload->'prepared_source_extraction')='object'
                  THEN (payload->'prepared_source_extraction') - ARRAY['fragments','docling_record']
                  ELSE payload->'prepared_source_extraction' END)
         ELSE '{}'::jsonb END
      || jsonb_build_object('_review_formation_notice',jsonb_build_object('provider_evidence',
           jsonb_build_object('formation_incomplete',payload#>'{semantic_replay,provider_evidence,formation_incomplete}')),
           '_review_has_replay',COALESCE(payload->'semantic_replay' NOT IN ('null'::jsonb,'{}'::jsonb),false))
$body$;
CREATE OR REPLACE FUNCTION workflow.refresh_review_read_envelope()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    NEW.review_read_envelope := workflow.review_read_envelope_for(NEW.envelope_payload);
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS refresh_review_read_envelope ON workflow.documents;
-- Run after trg_workflow_documents_lifecycle_identity, including updates whose
-- SET list omits envelope_payload but whose identity trigger normalizes it.
DROP TRIGGER IF EXISTS zzz_refresh_review_read_envelope ON workflow.documents;
CREATE TRIGGER zzz_refresh_review_read_envelope
    BEFORE INSERT OR UPDATE ON workflow.documents
    FOR EACH ROW EXECUTE FUNCTION workflow.refresh_review_read_envelope();
CREATE TABLE IF NOT EXISTS workflow.source_read_roots (
    views_id TEXT PRIMARY KEY,
    extraction_hash TEXT NOT NULL REFERENCES workflow.prepared_extraction_versions(record_hash) ON DELETE CASCADE,
    header JSONB NOT NULL,
    header_hash TEXT NOT NULL,
    sealed BOOLEAN NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS workflow.source_read_fragments (
    views_id TEXT NOT NULL REFERENCES workflow.source_read_roots(views_id) ON DELETE CASCADE,
    fragment_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    views TEXT[] NOT NULL,
    blocks JSONB NOT NULL,
    payload_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    PRIMARY KEY(views_id, fragment_id),
    UNIQUE(views_id, ordinal),
    UNIQUE(views_id, fragment_id, payload_hash),
    CHECK(payload->>'fragment_id'=fragment_id)
);
CREATE TABLE IF NOT EXISTS workflow.source_read_blocks (
    views_id TEXT NOT NULL REFERENCES workflow.source_read_roots(views_id) ON DELETE CASCADE,
    view_name TEXT NOT NULL CHECK(view_name IN ('full','content','candidate','evidence','evidence_content','headings')),
    block_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    fragment_count INTEGER NOT NULL CHECK (fragment_count > 0),
    payload_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    PRIMARY KEY(views_id, view_name, block_id),
    UNIQUE(views_id, view_name, ordinal),
    CHECK(payload->0->>'block_id'=block_id)
);
CREATE TABLE IF NOT EXISTS workflow.source_read_block_fragments (
    views_id TEXT NOT NULL,
    view_name TEXT NOT NULL,
    block_id TEXT NOT NULL,
    fragment_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    PRIMARY KEY(views_id, view_name, block_id, fragment_id),
    FOREIGN KEY(views_id, view_name, block_id)
        REFERENCES workflow.source_read_blocks(views_id, view_name, block_id) ON DELETE CASCADE,
    FOREIGN KEY(views_id, fragment_id, payload_hash)
        REFERENCES workflow.source_read_fragments(views_id, fragment_id, payload_hash) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS source_read_block_lookup
    ON workflow.source_read_blocks(views_id, block_id, view_name);
CREATE INDEX IF NOT EXISTS source_read_block_members
    ON workflow.source_read_block_fragments(views_id, block_id, view_name, fragment_id);

CREATE OR REPLACE FUNCTION workflow.guard_source_read_root()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.sealed THEN
            RAISE EXCEPTION 'source_read_records_immutable';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP='DELETE' THEN
        -- Only the existing extraction/document cascade may remove its derivation.
        IF EXISTS(SELECT 1 FROM workflow.prepared_extraction_versions WHERE record_hash=OLD.extraction_hash) THEN
            RAISE EXCEPTION 'source_read_records_immutable';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.sealed OR NOT NEW.sealed OR NEW.views_id<>OLD.views_id
       OR NEW.extraction_hash<>OLD.extraction_hash OR NEW.header<>OLD.header OR NEW.header_hash<>OLD.header_hash THEN
        RAISE EXCEPTION 'source_read_records_immutable';
    END IF;
    IF (SELECT count(*) FROM workflow.source_read_fragments WHERE views_id=NEW.views_id)
           <> (NEW.header->>'fragment_count')::integer
       OR (SELECT count(*) FROM workflow.source_read_blocks WHERE views_id=NEW.views_id)
           <> (NEW.header->>'block_count')::integer
       OR EXISTS(SELECT 1 FROM workflow.source_read_blocks b WHERE b.views_id=NEW.views_id
           AND b.fragment_count<>(SELECT count(*) FROM workflow.source_read_block_fragments m
               WHERE (m.views_id,m.view_name,m.block_id)=(b.views_id,b.view_name,b.block_id))) THEN
        RAISE EXCEPTION 'source_read_records_incomplete';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_source_read_root ON workflow.source_read_roots;
CREATE TRIGGER guard_source_read_root BEFORE INSERT OR UPDATE OR DELETE ON workflow.source_read_roots
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_source_read_root();

CREATE OR REPLACE FUNCTION workflow.guard_source_read_member()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE root_id TEXT; protected BOOLEAN;
BEGIN
    root_id := CASE WHEN TG_OP='INSERT' THEN NEW.views_id ELSE OLD.views_id END;
    SELECT sealed INTO protected FROM workflow.source_read_roots WHERE views_id=root_id FOR UPDATE;
    IF NOT FOUND AND TG_OP<>'DELETE' THEN
        RAISE EXCEPTION 'source_read_root_missing';
    END IF;
    IF protected OR TG_OP='UPDATE' THEN
        RAISE EXCEPTION 'source_read_records_immutable';
    END IF;
    RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END
$body$;
DROP TRIGGER IF EXISTS guard_source_read_member ON workflow.source_read_fragments;
CREATE TRIGGER guard_source_read_member BEFORE INSERT OR UPDATE OR DELETE ON workflow.source_read_fragments
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_source_read_member();
DROP TRIGGER IF EXISTS guard_source_read_member ON workflow.source_read_blocks;
CREATE TRIGGER guard_source_read_member BEFORE INSERT OR UPDATE OR DELETE ON workflow.source_read_blocks
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_source_read_member();
DROP TRIGGER IF EXISTS guard_source_read_member ON workflow.source_read_block_fragments;
CREATE TRIGGER guard_source_read_member BEFORE INSERT OR UPDATE OR DELETE ON workflow.source_read_block_fragments
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_source_read_member();

CREATE OR REPLACE FUNCTION workflow.require_sealed_source_read_root()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF EXISTS(SELECT 1 FROM workflow.source_read_roots WHERE views_id=NEW.views_id AND NOT sealed) THEN
        RAISE EXCEPTION 'source_read_records_incomplete';
    END IF;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS require_sealed_source_read_root ON workflow.source_read_roots;
CREATE CONSTRAINT TRIGGER require_sealed_source_read_root
    AFTER INSERT ON workflow.source_read_roots DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION workflow.require_sealed_source_read_root();
