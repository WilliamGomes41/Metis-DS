-- Additive storage capability; no existing document is converted by DDL/startup.
ALTER TABLE workflow.processing_archives DROP CONSTRAINT IF EXISTS processing_archives_kind_check;
ALTER TABLE workflow.processing_archives ADD CONSTRAINT processing_archives_kind_check
    CHECK(kind IN ('semantic_replay','quality_processing_run','tree_formation'));
ALTER TABLE workflow.documents ADD COLUMN IF NOT EXISTS document_storage_version INTEGER NOT NULL DEFAULT 0
    CHECK(document_storage_version IN (0,1));
CREATE TABLE IF NOT EXISTS workflow.document_inputs (
    snapshot_id TEXT PRIMARY KEY REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    metadata JSONB NOT NULL,
    refs JSONB NOT NULL,
    extraction_header JSONB,
    notice JSONB NOT NULL,
    CHECK(NOT metadata ?| ARRAY['semantic_replay','quality_processing_runs','processing_attempts','prepared_source_extraction'])
);
CREATE TABLE IF NOT EXISTS workflow.document_processing_records (
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    ordinal BIGINT NOT NULL CHECK(ordinal>=0),
    archive_id TEXT NOT NULL REFERENCES workflow.processing_archives(archive_id),
    reference JSONB NOT NULL,
    PRIMARY KEY(snapshot_id,kind,ordinal)
);
CREATE INDEX IF NOT EXISTS document_processing_records_archive ON workflow.document_processing_records(snapshot_id,kind,archive_id);
CREATE TABLE IF NOT EXISTS workflow.processing_archive_inputs (
    archive_id TEXT PRIMARY KEY REFERENCES workflow.processing_archives(archive_id) ON DELETE CASCADE,
    header JSONB NOT NULL,
    header_hash TEXT NOT NULL,
    sealed BOOLEAN NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS workflow.processing_archive_input_members (
    archive_id TEXT NOT NULL REFERENCES workflow.processing_archive_inputs(archive_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    member_key TEXT NOT NULL,
    object_id TEXT,
    payload_hash TEXT NOT NULL,
    payload_text TEXT NOT NULL,
    PRIMARY KEY(archive_id,role,member_key),
    CHECK(payload_hash=encode(sha256(convert_to(payload_text,'UTF8')),'hex'))
);
CREATE INDEX IF NOT EXISTS processing_archive_input_candidates
    ON workflow.processing_archive_input_members(archive_id,object_id,member_key) WHERE role='candidate';

CREATE OR REPLACE FUNCTION workflow.guard_archive_input_root() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE binding JSONB; content_hash TEXT;
BEGIN
    IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'processing_input_immutable'; END IF;
    IF TG_OP='DELETE' THEN
        IF EXISTS(SELECT 1 FROM workflow.processing_archives WHERE archive_id=OLD.archive_id) THEN
            RAISE EXCEPTION 'processing_input_immutable';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP='INSERT' THEN
        SELECT a.binding,a.payload_hash INTO binding,content_hash FROM workflow.processing_archives a WHERE archive_id=NEW.archive_id;
        IF NEW.sealed OR NOT FOUND OR NEW.header->>'layout' IS DISTINCT FROM '1'
           OR NEW.header->>'archive_id' IS DISTINCT FROM NEW.archive_id
           OR NEW.header->'source' IS DISTINCT FROM binding
           OR NEW.header->>'payload_hash' IS DISTINCT FROM content_hash THEN
            RAISE EXCEPTION 'processing_input_integrity_failed';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.sealed OR NOT NEW.sealed OR NEW.archive_id<>OLD.archive_id
       OR NEW.header<>OLD.header OR NEW.header_hash<>OLD.header_hash THEN
        RAISE EXCEPTION 'processing_input_immutable';
    END IF;
    IF (SELECT COALESCE(jsonb_agg(jsonb_build_array(role,member_key,object_id,payload_hash)
         ORDER BY role,member_key),'[]'::jsonb) FROM workflow.processing_archive_input_members WHERE archive_id=NEW.archive_id)
         IS DISTINCT FROM NEW.header->'manifest' THEN RAISE EXCEPTION 'processing_input_membership_incomplete'; END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_archive_input_root ON workflow.processing_archive_inputs;
CREATE TRIGGER guard_archive_input_root BEFORE INSERT OR UPDATE OR DELETE ON workflow.processing_archive_inputs
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_archive_input_root();
DROP TRIGGER IF EXISTS guard_archive_input_root_truncate ON workflow.processing_archive_inputs;
CREATE TRIGGER guard_archive_input_root_truncate BEFORE TRUNCATE ON workflow.processing_archive_inputs
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_archive_input_root();
CREATE OR REPLACE FUNCTION workflow.guard_archive_input_member() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE protected BOOLEAN;
BEGIN
    IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'processing_input_immutable'; END IF;
    SELECT sealed INTO protected FROM workflow.processing_archive_inputs WHERE archive_id=
        CASE WHEN TG_OP='INSERT' THEN NEW.archive_id ELSE OLD.archive_id END FOR UPDATE;
    IF protected OR TG_OP='UPDATE' OR (NOT FOUND AND TG_OP<>'DELETE') THEN RAISE EXCEPTION 'processing_input_immutable'; END IF;
    RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END
$body$;
DROP TRIGGER IF EXISTS guard_archive_input_member ON workflow.processing_archive_input_members;
CREATE TRIGGER guard_archive_input_member BEFORE INSERT OR UPDATE OR DELETE ON workflow.processing_archive_input_members
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_archive_input_member();
DROP TRIGGER IF EXISTS guard_archive_input_member_truncate ON workflow.processing_archive_input_members;
CREATE TRIGGER guard_archive_input_member_truncate BEFORE TRUNCATE ON workflow.processing_archive_input_members
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_archive_input_member();
CREATE OR REPLACE FUNCTION workflow.require_archive_input_sealed() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF EXISTS(SELECT 1 FROM workflow.processing_archive_inputs WHERE archive_id=NEW.archive_id AND NOT sealed) THEN
        RAISE EXCEPTION 'processing_input_membership_incomplete';
    END IF;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS require_archive_input_sealed ON workflow.processing_archive_inputs;
CREATE CONSTRAINT TRIGGER require_archive_input_sealed AFTER INSERT ON workflow.processing_archive_inputs
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.require_archive_input_sealed();

CREATE OR REPLACE FUNCTION workflow.guard_operational_envelope_write() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF OLD.document_storage_version=1 THEN RAISE EXCEPTION 'document_inputs_compatible_writer_required'; END IF;
    -- The explicit legacy-envelope mutation owns a revision even for direct SQL.
    IF NEW.envelope_payload IS DISTINCT FROM OLD.envelope_payload AND NEW.revision<=OLD.revision THEN
        NEW.revision:=OLD.revision+1;
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_operational_envelope_write ON workflow.documents;
CREATE TRIGGER guard_operational_envelope_write BEFORE UPDATE OF envelope_payload ON workflow.documents
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_operational_envelope_write();

CREATE OR REPLACE FUNCTION workflow.guard_operational_inputs() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE doc_id TEXT; source_binding JSONB; item JSONB; selected_archive RECORD; selected_notice JSONB; slot TEXT;
BEGIN
    IF TG_OP='DELETE' THEN
        IF EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=OLD.snapshot_id AND document_storage_version=1) THEN
            RAISE EXCEPTION 'document_inputs_required';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP='UPDATE' AND NEW.snapshot_id IS DISTINCT FROM OLD.snapshot_id THEN
        RAISE EXCEPTION 'document_inputs_identity_immutable';
    END IF;
    SELECT snapshot_id,jsonb_build_object('snapshot_id',snapshot_id,'source_id',source_id,
        'document_id',document_id,'sha256',source_sha256,'version',source_version,
        'content_kind',content_kind,'logical_document_id',logical_document_id,'working_revision_id',working_revision_id)
        INTO doc_id,source_binding FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id FOR UPDATE;
    IF NOT FOUND OR NEW.refs->>'layout' IS DISTINCT FROM '1' THEN RAISE EXCEPTION 'document_inputs_layout_invalid'; END IF;
    FOR slot,item IN SELECT key,value FROM jsonb_each(NEW.refs) WHERE key IN ('replay','quality','tree') AND value<>'null'::jsonb LOOP
        IF item->>'kind' IS DISTINCT FROM (CASE slot WHEN 'replay' THEN 'semantic_replay' WHEN 'quality' THEN 'quality_processing_run' ELSE 'tree_formation' END) THEN
            RAISE EXCEPTION 'document_inputs_reference_kind_invalid';
        END IF;
        IF slot='quality' AND NOT EXISTS(SELECT 1 FROM workflow.document_processing_records WHERE snapshot_id=NEW.snapshot_id AND kind='quality_processing_run' AND reference=item) THEN
            RAISE EXCEPTION 'document_inputs_quality_membership_missing';
        END IF;
        SELECT a.archive_id,a.snapshot_id,a.payload_hash,a.layout,a.kind,a.record_key,a.binding INTO selected_archive FROM workflow.processing_archives a WHERE a.archive_id=item->>'archive_id';
        IF NOT FOUND OR selected_archive.snapshot_id<>NEW.snapshot_id OR selected_archive.payload_hash IS DISTINCT FROM item->>'payload_hash'
           OR selected_archive.binding IS DISTINCT FROM source_binding
           OR item IS DISTINCT FROM jsonb_build_object('layout',selected_archive.layout,'archive_id',selected_archive.archive_id,
                'kind',selected_archive.kind,'record_key',selected_archive.record_key,'payload_hash',selected_archive.payload_hash)
           OR NOT EXISTS(SELECT 1 FROM workflow.processing_archive_inputs WHERE archive_id=selected_archive.archive_id AND sealed) THEN
            RAISE EXCEPTION 'document_inputs_reference_invalid';
        END IF;
    END LOOP;
    IF NEW.refs->'replay' IS NOT NULL AND NEW.refs->'replay'<>'null'::jsonb THEN
        SELECT header->'notice' INTO selected_notice FROM workflow.processing_archive_inputs
            WHERE archive_id=NEW.refs#>>'{replay,archive_id}';
        IF selected_notice IS DISTINCT FROM NEW.notice THEN RAISE EXCEPTION 'document_inputs_notice_changed'; END IF;
    ELSIF NEW.notice IS DISTINCT FROM '{}'::jsonb THEN RAISE EXCEPTION 'document_inputs_notice_without_replay';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_operational_inputs ON workflow.document_inputs;
CREATE TRIGGER guard_operational_inputs BEFORE INSERT OR UPDATE OR DELETE ON workflow.document_inputs
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_operational_inputs();
CREATE OR REPLACE FUNCTION workflow.require_operational_inputs() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF EXISTS(SELECT 1 FROM workflow.documents d WHERE d.snapshot_id=NEW.snapshot_id AND d.document_storage_version=1)
       AND NOT EXISTS(SELECT 1 FROM workflow.document_inputs WHERE snapshot_id=NEW.snapshot_id) THEN
        RAISE EXCEPTION 'document_inputs_required';
    END IF;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS require_operational_inputs ON workflow.documents;
CREATE CONSTRAINT TRIGGER require_operational_inputs AFTER INSERT OR UPDATE ON workflow.documents
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.require_operational_inputs();

-- Preserve the original identity allocator/guards; skip only legacy JSON enrichment.
CREATE OR REPLACE FUNCTION workflow.assign_lifecycle_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    predecessor_logical_document_id TEXT;
    next_revision_number INTEGER;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.logical_document_id IS DISTINCT FROM OLD.logical_document_id
           OR NEW.working_revision_id IS DISTINCT FROM OLD.working_revision_id
           OR NEW.working_revision_number IS DISTINCT FROM OLD.working_revision_number
           OR NEW.replaces_snapshot_id IS DISTINCT FROM OLD.replaces_snapshot_id THEN
            RAISE EXCEPTION 'lifecycle_identity_immutable';
        END IF;
    ELSE
        IF NEW.ingest_kind = 'new_version' THEN
            IF NEW.replaces_snapshot_id IS NULL THEN
                RAISE EXCEPTION 'lifecycle_identity_predecessor_required';
            END IF;

            SELECT logical_document_id
              INTO predecessor_logical_document_id
              FROM workflow.documents
             WHERE snapshot_id = NEW.replaces_snapshot_id;

            IF predecessor_logical_document_id IS NULL THEN
                RAISE EXCEPTION 'lifecycle_identity_predecessor_missing';
            END IF;

            IF NEW.logical_document_id IS NOT NULL
               AND NEW.logical_document_id <> predecessor_logical_document_id THEN
                RAISE EXCEPTION 'lifecycle_identity_logical_document_mismatch';
            END IF;

            NEW.logical_document_id := predecessor_logical_document_id;
        ELSE
            IF NEW.logical_document_id IS NULL THEN
                NEW.logical_document_id := 'ldoc-' || NEW.snapshot_id;
            END IF;
        END IF;

        -- Serialize revision allocation per LogicalDocument. This keeps two
        -- concurrent successor captures from receiving the same work number.
        PERFORM pg_advisory_xact_lock(hashtextextended(NEW.logical_document_id, 0));

        SELECT COALESCE(MAX(working_revision_number), 0) + 1
          INTO next_revision_number
          FROM workflow.documents
         WHERE logical_document_id = NEW.logical_document_id;

        IF NEW.working_revision_number IS NOT NULL
           AND NEW.working_revision_number <> next_revision_number THEN
            RAISE EXCEPTION 'lifecycle_identity_working_revision_number_mismatch';
        END IF;

        NEW.working_revision_number := next_revision_number;

        IF NEW.working_revision_id IS NULL THEN
            NEW.working_revision_id := 'work-' || NEW.snapshot_id;
        END IF;
    END IF;

    -- envelope_payload is a read projection, not a second identity authority.
    -- Enrich it only when a complete envelope already exists; migration-stage
    -- rows with NULL payload remain migration-stage rows.
    IF NEW.document_storage_version=0 AND NEW.envelope_payload IS NOT NULL THEN
        NEW.envelope_payload := NEW.envelope_payload || jsonb_build_object(
            'logical_document_id', NEW.logical_document_id,
            'source_snapshot_id', NEW.snapshot_id,
            'source_version', NEW.source_version,
            'working_revision_id', NEW.working_revision_id,
            'working_revision_number', NEW.working_revision_number
        );
    END IF;

    RETURN NEW;
END
$$;


CREATE OR REPLACE FUNCTION workflow.refresh_source_selection_summary()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF NEW.document_storage_version=1 THEN
        SELECT workflow.source_selection_summary_for(i.metadata || jsonb_build_object(
            'semantic_replay',i.notice,'prepared_source_extraction',i.extraction_header,
            'processing_attempts',COALESCE(p.payload->'processing_attempts','[]'::jsonb)))
            || jsonb_build_object('pending_rejection_count',COALESCE(r.header->'pending_rejection_count','0'::jsonb),
                'source_fragment_count',q.header->'source_fragment_count') INTO NEW.source_selection_summary
        FROM workflow.document_inputs i LEFT JOIN workflow.processing_document_summaries p USING(snapshot_id)
        LEFT JOIN workflow.processing_archive_inputs r ON r.archive_id=i.refs#>>'{replay,archive_id}'
        LEFT JOIN workflow.processing_archive_inputs q ON q.archive_id=i.refs#>>'{quality,archive_id}'
        WHERE i.snapshot_id=NEW.snapshot_id;
    ELSE
        NEW.source_selection_summary := workflow.source_selection_summary_for(NEW.envelope_payload);
    END IF;
    RETURN NEW;
END
$body$;


CREATE OR REPLACE FUNCTION workflow.refresh_review_read_envelope()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF NEW.document_storage_version=1 THEN
        SELECT workflow.current_document_envelope(NEW)
            || jsonb_build_object('_review_formation_notice',i.notice,
                '_review_has_replay',i.refs->'replay'<>'null'::jsonb)
            INTO NEW.review_read_envelope FROM workflow.document_inputs i WHERE i.snapshot_id=NEW.snapshot_id;
    ELSE
        NEW.review_read_envelope := workflow.review_read_envelope_for(NEW.envelope_payload);
    END IF;
    RETURN NEW;
END
$body$;

DO $install$ BEGIN
IF to_regclass('workflow.review_fact_state') IS NOT NULL THEN
EXECUTE $ddl$CREATE OR REPLACE FUNCTION workflow.refresh_review_card_envelope()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE tree_ref JSONB; inventory JSONB;
BEGIN
    NEW.review_card_envelope := workflow.review_card_envelope_for(CASE WHEN NEW.document_storage_version=1 THEN NEW.review_read_envelope ELSE NEW.envelope_payload END)
      || jsonb_build_object('snapshot_id',NEW.snapshot_id,'document_id',NEW.document_id,
        'source_id',NEW.source_id,'title',NEW.title,'class',NEW.class,'state',NEW.state,
        'date',to_char(NEW.source_date,'YYYY-MM-DD'),'version',NEW.source_version,
        'sha256',NEW.source_sha256,'content_kind',NEW.content_kind,
        'publication_eligibility',NEW.publication_eligibility)
      || jsonb_build_object('_source_identity',jsonb_build_object(
        'snapshot_id',NEW.snapshot_id,'source_id',NEW.source_id,'document_id',NEW.document_id,'sha256',NEW.source_sha256,
        'version',NEW.source_version,'content_kind',NEW.content_kind,
        'extraction',NEW.review_read_envelope#>'{prepared_source_extraction,record_hash}',
        'extraction_header',NEW.review_read_envelope->'prepared_source_extraction',
        'source_ref',NEW.review_source_ref));
    tree_ref:=NEW.review_read_envelope#>'{_document_inputs,tree}';
    IF NEW.document_storage_version=1 AND tree_ref IS NOT NULL AND tree_ref<>'null'::jsonb THEN
        IF TG_OP='UPDATE' AND OLD.document_storage_version=1
           AND OLD.review_card_envelope#>'{_document_inputs,tree}'=tree_ref
           AND OLD.review_card_envelope ? 'decision_graph_evidence' THEN
            inventory:=OLD.review_card_envelope->'decision_graph_evidence';
        ELSE
            SELECT payload_text::jsonb INTO inventory FROM workflow.processing_archive_input_members
                WHERE archive_id=tree_ref->>'archive_id' AND role='tree_card' AND member_key='0';
        END IF;
        IF inventory IS NOT NULL THEN
            NEW.review_card_envelope:=NEW.review_card_envelope || jsonb_build_object('decision_graph_evidence',inventory);
        ELSIF NEW.review_read_envelope ? 'decision_graph' THEN
            RAISE EXCEPTION 'document_inputs_tree_source_missing';
        END IF;
    END IF;
    RETURN NEW;
END
$body$;
$ddl$;
END IF;
END $install$;

DO $install$ BEGIN
IF to_regclass('workflow.review_fact_state') IS NOT NULL THEN
EXECUTE $ddl$CREATE OR REPLACE FUNCTION workflow.review_card_envelope_for(payload JSONB)
RETURNS JSONB LANGUAGE SQL IMMUTABLE STRICT AS $body$
    SELECT COALESCE((SELECT jsonb_object_agg(k,compact->k)
      FROM unnest(ARRAY['snapshot_id','class','review_policy','named_reviewers','title','version',
        'publication_eligibility','state','date','source_id','document_id','sha256','content_kind',
        'is_live_capture','acquired_at','processing_blocker','source_declaration',
        'review_configuration','configuration_source',
        'prepared_source_extraction','decision_graph','decision_graph_reviews',
        '_review_formation_notice','_review_has_replay','_document_inputs']) k WHERE compact ? k),'{}'::jsonb)
      || CASE WHEN payload ? 'decision_graph_evidence' THEN jsonb_build_object('decision_graph_evidence',
        jsonb_build_object('source_sha256',payload#>'{decision_graph_evidence,source_sha256}',
          'items',CASE WHEN jsonb_typeof(payload#>'{decision_graph_evidence,items}')='object' THEN (
            SELECT COALESCE(jsonb_object_agg(e.key,
              (SELECT COALESCE(jsonb_object_agg(k,e.value->k),'{}'::jsonb)
               FROM unnest(ARRAY['kind','bundle_id','bundle_role']) k WHERE e.value ? k)
              || jsonb_build_object('literal_text_hash',CASE WHEN jsonb_typeof(e.value->'text')='string'
                 THEN encode(sha256(convert_to(e.value->>'text','UTF8')),'hex') ELSE NULL END)), '{}')
            FROM jsonb_each(payload#>'{decision_graph_evidence,items}') e)
            ELSE payload#>'{decision_graph_evidence,items}' END)) ELSE '{}'::jsonb END
    FROM (SELECT CASE WHEN payload ? '_document_inputs' THEN payload ELSE workflow.review_read_envelope_for(payload) END AS compact) s
$body$;

$ddl$;
END IF;
END $install$;

CREATE OR REPLACE FUNCTION workflow.guard_active_formation_evidence() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE document workflow.documents%ROWTYPE; proof workflow.formation_evidence_roots%ROWTYPE;
BEGIN
    IF NEW.document_storage_version=1 THEN
        IF TG_OP='UPDATE' AND OLD.formation_evidence_id IS NOT NULL AND NEW.formation_evidence_id IS NULL THEN
            RAISE EXCEPTION 'formation_evidence_pin_required';
        END IF;
        SELECT snapshot_id,formation_evidence_id,review_source_ref,source_id,document_id,source_sha256,source_version,
            content_kind,logical_document_id,working_revision_id INTO document.snapshot_id,document.formation_evidence_id,
            document.review_source_ref,document.source_id,document.document_id,document.source_sha256,document.source_version,
            document.content_kind,document.logical_document_id,document.working_revision_id
            FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id;
        IF NOT FOUND OR document.formation_evidence_id IS NULL THEN RETURN NULL; END IF;
        SELECT * INTO proof FROM workflow.formation_evidence_roots WHERE proof_id=document.formation_evidence_id;
        IF NOT FOUND OR NOT proof.sealed OR proof.snapshot_id<>document.snapshot_id
           OR proof.header#>'{capture,source_ref}' IS DISTINCT FROM document.review_source_ref
           OR proof.header->'source' IS DISTINCT FROM jsonb_build_object('snapshot_id',document.snapshot_id,
             'source_id',document.source_id,'document_id',document.document_id,'sha256',document.source_sha256,
             'version',document.source_version,'content_kind',document.content_kind,
             'logical_document_id',document.logical_document_id,'working_revision_id',document.working_revision_id)
           OR NOT EXISTS(SELECT 1 FROM workflow.document_inputs i WHERE i.snapshot_id=document.snapshot_id
                AND (i.refs->'replay'=proof.header#>'{capture,replay_ref}'
                    OR i.refs#>>'{replay,payload_hash}'=proof.header->>'activation_replay_hash')
                AND i.refs->>'extraction_hash'=proof.extraction_hash) THEN
            RAISE EXCEPTION 'formation_evidence_active_binding_changed';
        END IF;
        RETURN NULL;
    END IF;
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

-- A second binary cannot silently put an admitted document back on legacy I/O.
CREATE OR REPLACE FUNCTION workflow.guard_document_storage_version() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF OLD.document_storage_version=1 AND NEW.document_storage_version<>1 THEN
        RAISE EXCEPTION 'document_inputs_downgrade_forbidden';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_document_storage_version ON workflow.documents;
CREATE TRIGGER guard_document_storage_version BEFORE UPDATE OF document_storage_version ON workflow.documents
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_document_storage_version();
CREATE OR REPLACE FUNCTION workflow.guard_document_inputs_truncate() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    RAISE EXCEPTION 'document_inputs_aggregate_delete_required';
END
$body$;
DROP TRIGGER IF EXISTS guard_document_inputs_truncate ON workflow.document_inputs;
CREATE TRIGGER guard_document_inputs_truncate BEFORE TRUNCATE ON workflow.document_inputs
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_document_inputs_truncate();

-- The side row is part of the existing document aggregate, not a second CAS
-- owner. AFTER makes the new input visible to all ordinary document projections.
CREATE OR REPLACE FUNCTION workflow.advance_document_inputs_revision() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    UPDATE workflow.documents SET revision=revision+1,updated_at=CURRENT_TIMESTAMP,
        formation_evidence_id=formation_evidence_id,source_selection_summary=source_selection_summary
        WHERE snapshot_id=NEW.snapshot_id AND document_storage_version=1;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS advance_document_inputs_revision ON workflow.document_inputs;
CREATE TRIGGER advance_document_inputs_revision AFTER INSERT OR UPDATE ON workflow.document_inputs
    FOR EACH ROW EXECUTE FUNCTION workflow.advance_document_inputs_revision();

-- A manifest supplied by a writer is not proof that it contains the original
-- findings. Validate its complete projection against the actual immutable owner
-- once, during independent preparation, never during normal document writes.
CREATE OR REPLACE FUNCTION workflow.expected_archive_input_parts(kind TEXT, payload JSON)
RETURNS TABLE(role TEXT, member_key TEXT, object_id TEXT, value JSON)
LANGUAGE plpgsql IMMUTABLE AS $body$
DECLARE provider JSON;
BEGIN
    IF kind='semantic_replay' THEN
        RETURN QUERY SELECT 'meta'::text,'0'::text,NULL::text,
            COALESCE(json_object_agg(e.key,e.value),'{}'::json) FROM json_each(payload) e
            WHERE e.key=ANY(ARRAY['version','validation','formation_method','origin_execution',
                'semantic_execution','proposal_hash','replay_from_proposal_hash','replay_rejection_reason']);
        RETURN QUERY SELECT 'identity'::text,'0'::text,NULL::text,payload->'identity';
        RETURN QUERY SELECT 'proposal'::text,'0'::text,NULL::text,payload->'proposal';
        provider:=CASE WHEN json_typeof(payload->'provider_evidence')='object' THEN payload->'provider_evidence' ELSE '{}'::json END;
        RETURN QUERY SELECT 'provider'::text,'0'::text,NULL::text,
            (SELECT json_object_agg(p.key,p.value) FROM (
              SELECT e.key,e.value FROM json_each(provider) e WHERE e.key=ANY(ARRAY['formation_incomplete',
                'pending_rejections','task_policy','tasks','task_plan_summary','formation_progress','formation_state'])
              UNION ALL SELECT 'supplementary_calls',(SELECT COALESCE(json_agg(
                (SELECT COALESCE(json_object_agg(e.key,e.value),'{}'::json) FROM json_each(c.value) e
                 WHERE e.key=ANY(ARRAY['error_code','target_spans','failure_reason'])) ORDER BY c.ordinal),'[]'::json)
              FROM (SELECT provider AS value,0::bigint AS ordinal UNION ALL
                SELECT supplementary.value,supplementary.ordinality FROM json_array_elements(CASE WHEN json_typeof(provider->'supplementary_calls')='array'
                    THEN provider->'supplementary_calls' ELSE '[]'::json END) WITH ORDINALITY supplementary) c
              WHERE c.value->>'error_code' IS NOT NULL AND c.value->>'error_code'<>'')
            ) p);
    ELSIF kind='quality_processing_run' THEN
        RETURN QUERY SELECT 'meta'::text,'0'::text,NULL::text,
            (SELECT COALESCE(json_object_agg(e.key,e.value),'{}'::json) FROM json_each(payload) e WHERE e.key IN ('run_id','outcome','extractor_versions'));
        RETURN QUERY SELECT e.key,'0'::text,NULL::text,e.value FROM json_each(payload) e
            WHERE e.key IN ('source_fragments','document_extraction');
        RETURN QUERY SELECT 'candidate'::text,lpad((c.ordinal-1)::text,10,'0'),c.value->>'object_id',c.value
            FROM json_array_elements(CASE WHEN json_typeof(payload->'candidates')='array' THEN payload->'candidates' ELSE '[]'::json END)
            WITH ORDINALITY c(value,ordinal);
    ELSIF kind='tree_formation' THEN
        RETURN QUERY SELECT e.key,'0'::text,NULL::text,e.value FROM json_each(payload) e
            WHERE e.key IN ('decision_graph_evidence','decision_tree_formation','decision_tree_construction');
        IF payload::jsonb ? 'decision_graph_evidence' THEN
            RETURN QUERY SELECT 'tree_card'::text,'0'::text,NULL::text,workflow.tree_card_inventory_for((payload->'decision_graph_evidence')::jsonb)::json;
        END IF;
    ELSE
        RAISE EXCEPTION 'processing_input_kind_unsupported';
    END IF;
END
$body$;
-- JSONB equates 1, 1.0 and 1e0. Existing proposal hashes distinguish them.
DROP FUNCTION IF EXISTS workflow.exact_archive_json(JSON,JSON);
CREATE OR REPLACE FUNCTION workflow.exact_archive_json(expected JSON, actual JSON, decoded_numbers BOOLEAN DEFAULT false)
RETURNS BOOLEAN LANGUAGE plpgsql IMMUTABLE AS $body$
DECLARE category TEXT;
BEGIN
    IF expected IS NULL OR actual IS NULL THEN RETURN expected IS NULL AND actual IS NULL; END IF;
    category:=json_typeof(expected);
    IF category IS DISTINCT FROM json_typeof(actual) THEN RETURN false; END IF;
    IF category='number' THEN
        IF decoded_numbers THEN
            RETURN expected::jsonb=actual::jsonb AND ((expected::text ~ '[.eE]')=(actual::text ~ '[.eE]'));
        END IF;
        RETURN btrim(expected::text)=btrim(actual::text);
    END IF;
    IF category='object' THEN
        RETURN (SELECT count(*) FROM json_each(expected))=(SELECT count(*) FROM json_each(actual)) AND NOT EXISTS(
            SELECT 1 FROM json_each(expected) e FULL JOIN json_each(actual) a USING(key)
            WHERE e.key IS NULL OR a.key IS NULL OR NOT workflow.exact_archive_json(e.value,a.value,decoded_numbers));
    END IF;
    IF category='array' THEN
        RETURN json_array_length(expected)=json_array_length(actual) AND NOT EXISTS(
            SELECT 1 FROM json_array_elements(expected) WITH ORDINALITY e(value,n)
              JOIN json_array_elements(actual) WITH ORDINALITY a(value,n) USING(n)
              WHERE NOT workflow.exact_archive_json(e.value,a.value,decoded_numbers));
    END IF;
    RETURN expected::jsonb=actual::jsonb;
END
$body$;

CREATE OR REPLACE FUNCTION workflow.verify_archive_input_projection() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE original JSON; kind TEXT; original_text TEXT; original_hash TEXT;
BEGIN
    IF OLD.sealed OR NOT NEW.sealed THEN RETURN NEW; END IF;
    SELECT a.payload_text,a.payload_hash,a.kind INTO original_text,original_hash,kind FROM workflow.processing_archives a WHERE a.archive_id=NEW.archive_id;
    IF encode(sha256(convert_to(original_text,'UTF8')),'hex') IS DISTINCT FROM original_hash THEN
        RAISE EXCEPTION 'processing_input_integrity_failed';
    END IF;
    original:=original_text::json;
    IF kind='tree_formation' AND NEW.header->'tree_route' IS DISTINCT FROM to_jsonb(COALESCE(original::jsonb->'decision_tree_formation' NOT IN ('null'::jsonb,'{}'::jsonb,'[]'::jsonb,'false'::jsonb),false)) THEN
        RAISE EXCEPTION 'processing_input_original_projection_changed';
    END IF;
    IF kind='semantic_replay' AND NEW.header->>'pending_rejection_count' IS DISTINCT FROM
        json_array_length(COALESCE(NULLIF(original::jsonb#>'{provider_evidence,pending_rejections}','null'::jsonb),'[]'::jsonb)::text::json)::text THEN
        RAISE EXCEPTION 'processing_input_original_projection_changed';
    END IF;
    IF kind='quality_processing_run' AND NEW.header->>'source_fragment_count' IS DISTINCT FROM
        json_array_length(COALESCE(NULLIF(original::jsonb->'source_fragments','null'::jsonb),'[]'::jsonb)::text::json)::text THEN
        RAISE EXCEPTION 'processing_input_original_projection_changed';
    END IF;
    IF kind='semantic_replay' AND NEW.header->'notice' IS DISTINCT FROM
        jsonb_build_object('provider_evidence',jsonb_build_object('formation_incomplete',
            (original->'provider_evidence'->'formation_incomplete')::jsonb)) THEN
        RAISE EXCEPTION 'processing_input_original_projection_changed';
    END IF;
    IF EXISTS(
      WITH expected AS (SELECT * FROM workflow.expected_archive_input_parts(kind,original)),
      actual AS (SELECT role,member_key,object_id,payload_text::json AS value
          FROM workflow.processing_archive_input_members WHERE archive_id=NEW.archive_id)
      SELECT 1 FROM expected e FULL JOIN actual a USING(role,member_key)
        WHERE e.role IS NULL OR a.role IS NULL OR e.object_id IS DISTINCT FROM a.object_id OR NOT workflow.exact_archive_json(e.value,a.value)
    ) THEN RAISE EXCEPTION 'processing_input_original_projection_changed'; END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS verify_archive_input_projection ON workflow.processing_archive_inputs;
CREATE TRIGGER verify_archive_input_projection BEFORE UPDATE ON workflow.processing_archive_inputs
    FOR EACH ROW EXECUTE FUNCTION workflow.verify_archive_input_projection();

-- The existing summary trigger listens to envelope/summary updates. Admission
-- changes only the layout pin; explicitly refresh its compact projection then.
DROP TRIGGER IF EXISTS refresh_operational_source_summary ON workflow.documents;
CREATE TRIGGER refresh_operational_source_summary BEFORE UPDATE OF document_storage_version ON workflow.documents
    FOR EACH ROW WHEN (NEW.document_storage_version=1)
    EXECUTE FUNCTION workflow.refresh_source_selection_summary();

-- No whole-row JSON conversion: the legacy TOAST value is only accessed by
-- the explicit legacy branch. Identity/scalars remain on the existing row.
CREATE OR REPLACE FUNCTION workflow.document_scalar_envelope(d workflow.documents) RETURNS JSONB
LANGUAGE SQL IMMUTABLE AS $scalar$ SELECT jsonb_build_object('snapshot_id',d.snapshot_id,
        'source_id',d.source_id,
        'document_id',d.document_id,
        'title',d.title,
        'family',d.family,
        'topic_id',d.topic_id,
        'class',d.class,
        'state',d.state,
        'publication_eligibility',d.publication_eligibility,
        'content_kind',d.content_kind,
        'ingest_kind',d.ingest_kind,
        'version',d.source_version,
        'date',d.source_date,
        'sha256',d.source_sha256,
        'locator',d.source_locator,
        'immutable_storage_locator',d.immutable_storage_locator,
        'live_url',d.live_url,
        'uploader_account_id',d.uploader_account_id,
        'replaces_snapshot_id',d.replaces_snapshot_id,
        'object_diff',d.object_diff,
        'clinical_rereview_required',d.clinical_rereview_required,
        'acquired_at',d.acquired_at,
        'console_version',d.console_version,
        'logical_document_id',d.logical_document_id,
        'working_revision_id',d.working_revision_id,
        'working_revision_number',d.working_revision_number,
        'processing_storage',CASE WHEN d.processing_storage_version=1 THEN 'task-v1' ELSE NULL END) $scalar$;

CREATE OR REPLACE FUNCTION workflow.current_document_envelope(d workflow.documents)
RETURNS JSONB LANGUAGE plpgsql STABLE AS $body$
DECLARE inputs workflow.document_inputs%ROWTYPE; scalar_values JSONB;
BEGIN
    IF d.document_storage_version=0 THEN RETURN d.envelope_payload; END IF;
    SELECT * INTO inputs FROM workflow.document_inputs WHERE snapshot_id=d.snapshot_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'document_inputs_required'; END IF;
    scalar_values:=workflow.document_scalar_envelope(d);
    IF inputs.refs->>'acquired_at_z'='true' THEN
        scalar_values:=scalar_values || jsonb_build_object('acquired_at',
            regexp_replace(scalar_values->>'acquired_at','[+]00:00$','Z'));
    END IF;
    RETURN inputs.metadata || COALESCE((SELECT jsonb_object_agg(e.key,e.value)
        FROM jsonb_each(scalar_values) e WHERE inputs.refs->'fields' ? e.key),'{}'::jsonb)
        || CASE WHEN inputs.extraction_header IS NOT NULL AND inputs.extraction_header<>'null'::jsonb
            THEN jsonb_build_object('prepared_source_extraction',inputs.extraction_header) ELSE '{}'::jsonb END
        || CASE WHEN inputs.refs->'tree_route'='true'::jsonb THEN jsonb_build_object('tree_source_route',true) ELSE '{}'::jsonb END
        || jsonb_build_object('_document_inputs',inputs.refs || jsonb_build_object('proof_id',d.formation_evidence_id));
END
$body$;

-- Derived command/status index, still owned by the existing attempt row/version.
-- Old diagnostic bodies are never fetched by ordinary status or reservation.
CREATE TABLE IF NOT EXISTS workflow.processing_attempt_inputs (
    attempt_id TEXT PRIMARY KEY REFERENCES workflow.processing_attempts(attempt_id) ON DELETE CASCADE,
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    command_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    record_version BIGINT NOT NULL,
    state TEXT,
    kind TEXT,
    progress_made BOOLEAN,
    payload JSONB NOT NULL,
    UNIQUE(snapshot_id,command_id)
);
ALTER TABLE workflow.processing_attempt_inputs ADD COLUMN IF NOT EXISTS state TEXT;
ALTER TABLE workflow.processing_attempt_inputs ADD COLUMN IF NOT EXISTS kind TEXT;
ALTER TABLE workflow.processing_attempt_inputs ADD COLUMN IF NOT EXISTS progress_made BOOLEAN;
CREATE INDEX IF NOT EXISTS processing_attempt_inputs_running ON workflow.processing_attempt_inputs(snapshot_id,state);
CREATE INDEX IF NOT EXISTS processing_attempt_inputs_budget ON workflow.processing_attempt_inputs(snapshot_id) INCLUDE(state,kind,progress_made);
CREATE INDEX IF NOT EXISTS processing_attempt_inputs_latest
    ON workflow.processing_attempt_inputs(snapshot_id,started_at DESC,attempt_id DESC);
CREATE OR REPLACE FUNCTION workflow.processing_attempt_input_for(value JSONB)
RETURNS JSONB LANGUAGE SQL IMMUTABLE STRICT AS $body$
    SELECT (value-'diagnostic') || CASE WHEN value ? 'diagnostic' THEN jsonb_build_object('diagnostic',
      COALESCE((SELECT jsonb_object_agg(e.key,e.value) FROM jsonb_each(COALESCE(NULLIF(value->'diagnostic','null'::jsonb),'{}'::jsonb)) e
        WHERE e.key=ANY(ARRAY['version','phase','validator_input_ref','validator_input_hash','validator_identity',
          'semantic_identity','task_plan_ref','source_views_ref','review_source_ref','staged_extraction_hash',
          'final_validation','formation_finalized_ref','formation_evidence_ref','unverified_pages','page_findings',
          'outcome','reason_code','category','recovery_advice','evidence_availability','origin_request_id',
          'origin_runtime','execution_runtime','document_budget_authorized','omitted_evidence','evidence_limit_bytes'])),
        '{}'::jsonb)) ELSE '{}'::jsonb END
$body$;
CREATE OR REPLACE FUNCTION workflow.refresh_processing_attempt_input() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    INSERT INTO workflow.processing_attempt_inputs(attempt_id,snapshot_id,command_id,started_at,record_version,state,kind,progress_made,payload)
        VALUES(NEW.attempt_id,NEW.snapshot_id,NEW.command_id,NEW.started_at,NEW.record_version,
            NEW.payload->>'state',NEW.payload->>'kind',NEW.payload->'formation_progress_made'='true'::jsonb,
            workflow.processing_attempt_input_for(NEW.payload))
        ON CONFLICT(attempt_id) DO UPDATE SET record_version=EXCLUDED.record_version,payload=EXCLUDED.payload,
            state=EXCLUDED.state,kind=EXCLUDED.kind,progress_made=EXCLUDED.progress_made;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS refresh_processing_attempt_input ON workflow.processing_attempts;
CREATE TRIGGER refresh_processing_attempt_input AFTER INSERT OR UPDATE ON workflow.processing_attempts
    FOR EACH ROW EXECUTE FUNCTION workflow.refresh_processing_attempt_input();

-- Reversible binary coexistence: old writers cannot mutate objects or attempts
-- of an admitted aggregate even when they happen to omit envelope UPDATE.
CREATE OR REPLACE FUNCTION workflow.require_operational_writer() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE sid TEXT;
BEGIN
    sid:=CASE WHEN TG_OP='DELETE' THEN OLD.snapshot_id ELSE NEW.snapshot_id END;
    IF EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=sid AND document_storage_version=1)
       AND current_setting('metis.document_storage_writer',true) IS DISTINCT FROM 'v1' THEN
        RAISE EXCEPTION 'document_inputs_compatible_writer_required';
    END IF;
    RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END
$body$;
DROP TRIGGER IF EXISTS require_operational_writer ON workflow.document_objects;
CREATE TRIGGER require_operational_writer BEFORE INSERT OR UPDATE OR DELETE ON workflow.document_objects
    FOR EACH ROW EXECUTE FUNCTION workflow.require_operational_writer();
DROP TRIGGER IF EXISTS require_operational_writer ON workflow.processing_attempts;
CREATE TRIGGER require_operational_writer BEFORE INSERT OR UPDATE OR DELETE ON workflow.processing_attempts
    FOR EACH ROW EXECUTE FUNCTION workflow.require_operational_writer();

ALTER TABLE workflow.document_inputs ADD COLUMN IF NOT EXISTS prepared_capture JSONB;
ALTER TABLE workflow.document_inputs ADD COLUMN IF NOT EXISTS prepared_quality_count INTEGER;
ALTER TABLE workflow.document_inputs ADD COLUMN IF NOT EXISTS prepared_has_replay BOOLEAN;
ALTER TABLE workflow.document_inputs ADD COLUMN IF NOT EXISTS prepared_has_tree BOOLEAN NOT NULL DEFAULT false;

-- Before admission only, validate against the actual old owner outside the
-- workflow lock. Activation later reads this server-owned preparation, not a
-- caller's replaceable carrier. No activation/backfill is performed by DDL.
CREATE OR REPLACE FUNCTION workflow.guard_document_input_preparation() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE layout INTEGER; original JSONB; capture JSONB; fields JSONB; quality_count INTEGER; has_replay BOOLEAN;
BEGIN
    SELECT document_storage_version INTO layout FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id;
    IF layout=1 OR EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='workflow.documents'::regclass
        AND tgname='trg_workflow_documents_lifecycle_identity' AND tgenabled='D') THEN RETURN NEW; END IF;
    SELECT d.envelope_payload,jsonb_build_object('revision',d.revision,'object_generation',d.object_generation,
        'source_sha256',d.source_sha256,'source_version',d.source_version,'review_source_ref',d.review_source_ref,
        'formation_evidence_id',d.formation_evidence_id,'document_storage_version',d.document_storage_version,
        'processing_storage_version',d.processing_storage_version,
        'attempts_token',(SELECT md5(COALESCE(string_agg(a.attempt_id||':'||a.record_version,',' ORDER BY a.attempt_id),''))
            FROM workflow.processing_attempts a WHERE a.snapshot_id=d.snapshot_id))
        INTO original,capture FROM workflow.documents d WHERE d.snapshot_id=NEW.snapshot_id;
    IF NEW.prepared_capture IS DISTINCT FROM capture THEN RAISE EXCEPTION 'document_inputs_stale_preparation'; END IF;
    IF NEW.refs->'shapes' IS DISTINCT FROM (SELECT jsonb_object_agg(k,
        CASE WHEN k='processing_attempts' AND original->>'processing_storage'='task-v1' THEN 'value' WHEN NOT original ? k THEN 'absent' WHEN original->k='null'::jsonb THEN 'null' ELSE 'value' END)
        FROM unnest(ARRAY['semantic_replay','quality_processing_runs','processing_attempts','prepared_source_extraction',
            'decision_graph_evidence','decision_tree_formation','decision_tree_construction']) k)
       OR NEW.refs->'acquired_at_z' IS DISTINCT FROM to_jsonb(COALESCE(right(original->>'acquired_at',1)='Z',false)) THEN
        RAISE EXCEPTION 'document_inputs_preparation_shape_changed';
    END IF;
    IF NOT workflow.exact_archive_json((original - ARRAY['tree_source_route','processing_storage','decision_graph_evidence','decision_tree_formation','decision_tree_construction','_document_header_only','_document_inputs','_prepared_document_write','_processing_counts','_review_check_formation','_review_formation_notice','_review_has_replay','_review_source_ref','acquired_at','class','clinical_rereview_required','console_version','content_kind','date','document_id','family','immutable_storage_locator','ingest_kind','live_url','locator','logical_document_id','object_diff','prepared_source_extraction','processing_attempts','publication_eligibility','quality_processing_runs','replaces_snapshot_id','semantic_replay','sha256','snapshot_id','source_id','state','title','topic_id','uploader_account_id','version','working_revision_id','working_revision_number'])::text::json,NEW.metadata::text::json,true) THEN
        RAISE EXCEPTION 'document_inputs_preparation_changed';
    END IF;
    SELECT COALESCE(jsonb_agg(k ORDER BY k),'[]'::jsonb) INTO fields FROM jsonb_object_keys(original) k WHERE k=ANY(ARRAY['snapshot_id','source_id','document_id','title','family','topic_id','class','state','publication_eligibility','content_kind','ingest_kind','version','date','sha256','locator','immutable_storage_locator','live_url','uploader_account_id','replaces_snapshot_id','object_diff','clinical_rereview_required','acquired_at','console_version','logical_document_id','working_revision_id','working_revision_number']);
    IF NOT fields ? 'processing_storage' THEN fields:=fields || '["processing_storage"]'::jsonb; END IF;
    SELECT jsonb_agg(k ORDER BY k) INTO fields FROM jsonb_array_elements_text(fields) k;
    IF COALESCE(original->>'processing_storage','')<>'task-v1' AND NOT workflow.exact_archive_json(
        COALESCE(NULLIF(original->'processing_attempts','null'::jsonb),'[]'::jsonb)::text::json,
        (SELECT COALESCE(jsonb_agg(payload ORDER BY started_at,attempt_id),'[]'::jsonb)::text::json
            FROM workflow.processing_attempts WHERE snapshot_id=NEW.snapshot_id),true) THEN
        RAISE EXCEPTION 'document_inputs_legacy_attempts_changed';
    END IF;
    quality_count:=jsonb_array_length(COALESCE(NULLIF(original->'quality_processing_runs','null'::jsonb),'[]'::jsonb));
    has_replay:=COALESCE(original->'semantic_replay' NOT IN('null'::jsonb,'{}'::jsonb),false);
    IF NEW.refs->'fields' IS DISTINCT FROM fields OR NEW.prepared_quality_count IS DISTINCT FROM quality_count
       OR NEW.prepared_has_replay IS DISTINCT FROM has_replay
       OR (SELECT count(*) FROM workflow.document_processing_records WHERE snapshot_id=NEW.snapshot_id AND kind='quality_processing_run')<>quality_count
       OR (SELECT count(*) FROM workflow.document_processing_records WHERE snapshot_id=NEW.snapshot_id AND kind='semantic_replay')<>has_replay::integer
       OR NEW.prepared_has_tree IS DISTINCT FROM EXISTS(SELECT 1 FROM jsonb_object_keys(original) k WHERE k IN('decision_graph_evidence','decision_tree_formation','decision_tree_construction'))
       OR (SELECT count(*) FROM workflow.document_processing_records WHERE snapshot_id=NEW.snapshot_id AND kind='tree_formation')<>NEW.prepared_has_tree::integer
       OR COALESCE((SELECT reference FROM workflow.document_processing_records WHERE snapshot_id=NEW.snapshot_id AND kind='tree_formation' AND ordinal=0),'null'::jsonb) IS DISTINCT FROM NEW.refs->'tree'
       OR COALESCE((SELECT reference FROM workflow.document_processing_records WHERE snapshot_id=NEW.snapshot_id
            AND kind='quality_processing_run' AND ordinal=quality_count-1),'null'::jsonb) IS DISTINCT FROM NEW.refs->'quality'
       OR COALESCE((SELECT reference FROM workflow.document_processing_records WHERE snapshot_id=NEW.snapshot_id
            AND kind='semantic_replay' AND ordinal=0),'null'::jsonb) IS DISTINCT FROM NEW.refs->'replay'
       OR COALESCE((original->'prepared_source_extraction')-ARRAY['fragments','docling_record'],'null'::jsonb)
            IS DISTINCT FROM COALESCE(NEW.extraction_header,'null'::jsonb)
       OR NEW.refs->>'extraction_hash' IS DISTINCT FROM NEW.extraction_header->>'record_hash' THEN
        RAISE EXCEPTION 'document_inputs_preparation_changed';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS aa_guard_document_input_preparation ON workflow.document_inputs;
CREATE TRIGGER aa_guard_document_input_preparation BEFORE INSERT OR UPDATE ON workflow.document_inputs
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_document_input_preparation();

CREATE OR REPLACE FUNCTION workflow.guard_document_processing_record() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE layout INTEGER; original JSONB; archive workflow.processing_archives%ROWTYPE; sid TEXT; original_archive TEXT;
BEGIN
    IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'document_inputs_history_immutable'; END IF;
    sid:=CASE WHEN TG_OP='DELETE' THEN OLD.snapshot_id ELSE NEW.snapshot_id END;
    SELECT document_storage_version INTO layout FROM workflow.documents WHERE snapshot_id=sid;
    IF TG_OP='DELETE' AND (layout IS NULL OR layout=0) THEN RETURN OLD; END IF;
    IF TG_OP IN('DELETE','UPDATE') THEN RAISE EXCEPTION 'document_inputs_history_immutable'; END IF;
    SELECT a.snapshot_id,a.kind,a.layout,a.record_key,a.payload_hash INTO archive.snapshot_id,archive.kind,
        archive.layout,archive.record_key,archive.payload_hash FROM workflow.processing_archives a WHERE a.archive_id=NEW.archive_id;
    IF archive.snapshot_id IS DISTINCT FROM sid OR archive.kind IS DISTINCT FROM NEW.kind
       OR NEW.reference IS DISTINCT FROM jsonb_build_object('layout',archive.layout,'archive_id',NEW.archive_id,
            'kind',archive.kind,'record_key',archive.record_key,'payload_hash',archive.payload_hash) THEN
        RAISE EXCEPTION 'document_inputs_preparation_changed';
    END IF;
    IF layout=1 THEN
        IF current_setting('metis.document_storage_writer',true) IS DISTINCT FROM 'v1' THEN
            RAISE EXCEPTION 'document_inputs_stale_preparation';
        END IF;
        RETURN NEW;
    END IF;
    -- Existing offline restore already owns all table locks and has disabled
    -- the identity allocator. Its archived history need not equal frozen v0.
    IF EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='workflow.documents'::regclass
        AND tgname='trg_workflow_documents_lifecycle_identity' AND tgenabled='D') THEN RETURN NEW; END IF;
    SELECT CASE WHEN NEW.kind='semantic_replay' AND NEW.ordinal=0 THEN envelope_payload->'semantic_replay'
        WHEN NEW.kind='quality_processing_run' THEN envelope_payload->'quality_processing_runs'->NEW.ordinal::integer
        WHEN NEW.kind='tree_formation' AND NEW.ordinal=0 THEN (SELECT jsonb_object_agg(e.key,e.value) FROM jsonb_each(envelope_payload) e WHERE e.key IN('decision_graph_evidence','decision_tree_formation','decision_tree_construction'))
        ELSE NULL END INTO original FROM workflow.documents WHERE snapshot_id=sid;
    SELECT payload_text INTO original_archive FROM workflow.processing_archives WHERE archive_id=NEW.archive_id;
    IF original IS NULL OR NOT workflow.exact_archive_json(original::text::json,original_archive::json,true) THEN
        RAISE EXCEPTION 'document_inputs_preparation_changed';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_document_processing_record ON workflow.document_processing_records;
CREATE TRIGGER guard_document_processing_record BEFORE INSERT OR UPDATE OR DELETE ON workflow.document_processing_records
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_document_processing_record();
DROP TRIGGER IF EXISTS guard_document_processing_record_truncate ON workflow.document_processing_records;
CREATE TRIGGER guard_document_processing_record_truncate BEFORE TRUNCATE ON workflow.document_processing_records
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_document_processing_record();

CREATE OR REPLACE FUNCTION workflow.guard_processing_attempt_input() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE original workflow.processing_attempts%ROWTYPE;
BEGIN
    IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'document_inputs_attempt_index_immutable'; END IF;
    IF TG_OP='DELETE' THEN
        IF EXISTS(SELECT 1 FROM workflow.processing_attempts WHERE attempt_id=OLD.attempt_id) THEN
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
DROP TRIGGER IF EXISTS guard_processing_attempt_input ON workflow.processing_attempt_inputs;
CREATE TRIGGER guard_processing_attempt_input BEFORE INSERT OR UPDATE OR DELETE ON workflow.processing_attempt_inputs
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_processing_attempt_input();
DROP TRIGGER IF EXISTS guard_processing_attempt_input_truncate ON workflow.processing_attempt_inputs;
CREATE TRIGGER guard_processing_attempt_input_truncate BEFORE TRUNCATE ON workflow.processing_attempt_inputs
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.guard_processing_attempt_input();

CREATE OR REPLACE FUNCTION workflow.guard_document_input_variant() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE expected TEXT;
BEGIN
    expected:=CASE WHEN COALESCE(NEW.refs->'replay'<>'null'::jsonb,false) THEN 'semantic'
        WHEN COALESCE(NEW.refs->'tree'<>'null'::jsonb,false) OR COALESCE(NEW.metadata->'decision_graph' NOT IN ('null'::jsonb,'{}'::jsonb,'[]'::jsonb),false)
            THEN 'tree' ELSE 'absent' END;
    IF COALESCE(NEW.refs->'tree_route','false'::jsonb) IS DISTINCT FROM COALESCE((SELECT header->'tree_route' FROM workflow.processing_archive_inputs WHERE archive_id=NEW.refs#>>'{tree,archive_id}'),'false'::jsonb) THEN
        RAISE EXCEPTION 'document_inputs_tree_route_changed';
    END IF;
    IF NEW.refs->>'formation_variant' IS DISTINCT FROM expected THEN
        RAISE EXCEPTION 'document_inputs_formation_variant_changed';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS ab_guard_document_input_variant ON workflow.document_inputs;
CREATE TRIGGER ab_guard_document_input_variant BEFORE INSERT OR UPDATE ON workflow.document_inputs
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_document_input_variant();

CREATE OR REPLACE FUNCTION workflow.tree_card_inventory_for(value JSONB) RETURNS JSONB
LANGUAGE SQL IMMUTABLE AS $body$
    SELECT jsonb_build_object('source_sha256',value->'source_sha256','items',
        CASE WHEN jsonb_typeof(value->'items')='object' THEN (
          SELECT COALESCE(jsonb_object_agg(e.key,
            (SELECT COALESCE(jsonb_object_agg(k,e.value->k),'{}'::jsonb)
             FROM unnest(ARRAY['kind','bundle_id','bundle_role']) k WHERE e.value ? k)
            || jsonb_build_object('literal_text_hash',CASE WHEN jsonb_typeof(e.value->'text')='string'
               THEN encode(sha256(convert_to(e.value->>'text','UTF8')),'hex') ELSE NULL END)),'{}'::jsonb)
          FROM jsonb_each(value->'items') e)
          ELSE value->'items' END)
$body$;

CREATE OR REPLACE FUNCTION workflow.guard_processing_storage() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF NEW.document_storage_version=1 THEN
        IF NEW.processing_storage_version IS DISTINCT FROM 1 THEN
            RAISE EXCEPTION 'processing_storage_compatible_writer_required';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.processing_storage_version=1 AND (NEW.processing_storage_version IS DISTINCT FROM 1
        OR NEW.envelope_payload->>'processing_storage' IS DISTINCT FROM 'task-v1'
        OR NEW.envelope_payload ? 'processing_attempts') THEN
        RAISE EXCEPTION 'processing_storage_compatible_writer_required';
    END IF;
    RETURN NEW;
END
$body$;
CREATE OR REPLACE FUNCTION workflow.advance_attempt_record_version() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF NEW.payload IS DISTINCT FROM OLD.payload AND NEW.record_version<=OLD.record_version THEN
        NEW.record_version:=OLD.record_version+1;
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS advance_attempt_record_version ON workflow.processing_attempts;
CREATE TRIGGER advance_attempt_record_version BEFORE UPDATE ON workflow.processing_attempts
    FOR EACH ROW EXECUTE FUNCTION workflow.advance_attempt_record_version();

ALTER TABLE workflow.document_inputs DROP CONSTRAINT IF EXISTS document_inputs_metadata_check;
ALTER TABLE workflow.document_inputs ADD CONSTRAINT document_inputs_metadata_check CHECK(NOT metadata ?| ARRAY[
    'semantic_replay','quality_processing_runs','processing_attempts','prepared_source_extraction',
    'decision_graph_evidence','decision_tree_formation','decision_tree_construction','processing_storage']);
