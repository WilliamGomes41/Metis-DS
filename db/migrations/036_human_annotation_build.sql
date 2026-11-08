-- Expand the existing workflow producer, never a second queue or approval store.
CREATE TABLE IF NOT EXISTS workflow.annotation_seals (
    seal_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES workflow.annotation_sets(snapshot_id) ON DELETE CASCADE,
    extraction_hash TEXT NOT NULL REFERENCES workflow.prepared_extraction_versions(record_hash),
    generation BIGINT NOT NULL,
    overview_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    payload_text TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_id,overview_hash),
    CHECK(seal_id=encode(sha256(convert_to(payload_text,'UTF8')),'hex')),
    CHECK(payload_text::jsonb=payload)
);
ALTER TABLE workflow.annotation_sets ADD COLUMN IF NOT EXISTS current_seal_id TEXT
    REFERENCES workflow.annotation_seals(seal_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE IF NOT EXISTS workflow.annotation_build_commands (
    snapshot_id TEXT NOT NULL REFERENCES workflow.annotation_sets(snapshot_id) ON DELETE CASCADE,
    command_id TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    request_hash TEXT NOT NULL,
    seal_id TEXT NOT NULL REFERENCES workflow.annotation_seals(seal_id),
    attempt_id TEXT NOT NULL REFERENCES workflow.processing_attempts(attempt_id) DEFERRABLE INITIALLY DEFERRED,
    result JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(snapshot_id,command_id)
);
DROP TRIGGER IF EXISTS guard_annotation_seal_history ON workflow.annotation_seals;
CREATE TRIGGER guard_annotation_seal_history BEFORE UPDATE OR DELETE ON workflow.annotation_seals
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_history();
DROP TRIGGER IF EXISTS guard_annotation_build_commands ON workflow.annotation_build_commands;
CREATE TRIGGER guard_annotation_build_commands BEFORE UPDATE OR DELETE ON workflow.annotation_build_commands
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_history();

-- A single context projection is used by seal, worker validation and activation.
CREATE OR REPLACE FUNCTION workflow.annotation_materialization_context(d workflow.documents)
RETURNS JSONB LANGUAGE SQL STABLE AS $body$
    SELECT (SELECT jsonb_object_agg(k,COALESCE(e->k,'null'::jsonb)) FROM unnest(ARRAY[
        'snapshot_id','source_id','document_id','sha256','version','content_kind',
        'logical_document_id','working_revision_id','successor_guard','replaces_snapshot_id','title','family','class','date',
        'live_url','locator','immutable_storage_locator','review_policy','review_configuration','source_declaration']) k)
        || jsonb_build_object('named_reviewers',COALESCE((SELECT jsonb_agg(account_id ORDER BY account_id)
           FROM workflow.document_reviewers WHERE snapshot_id=d.snapshot_id),'[]'::jsonb))
    FROM (SELECT workflow.current_document_envelope(d) AS e) source
$body$;

CREATE OR REPLACE FUNCTION workflow.guard_annotation_source() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF (NEW.snapshot_id,NEW.working_revision_id,NEW.extraction_hash,NEW.source_identity,NEW.objects_revision,NEW.normalization,NEW.created_by,NEW.created_at)
        IS DISTINCT FROM
       (OLD.snapshot_id,OLD.working_revision_id,OLD.extraction_hash,OLD.source_identity,OLD.objects_revision,OLD.normalization,OLD.created_by,OLD.created_at)
       OR NOT ((NEW.generation=OLD.generation+1 AND NEW.current_seal_id IS NULL)
           OR (NEW.generation=OLD.generation AND NEW.current_seal_id IS DISTINCT FROM OLD.current_seal_id)) THEN
        RAISE EXCEPTION 'annotation_source_immutable';
    END IF;
    IF NEW.current_seal_id IS NOT NULL AND NOT EXISTS(
        SELECT 1 FROM workflow.annotation_seals seal JOIN workflow.documents d USING(snapshot_id)
        WHERE seal.seal_id=NEW.current_seal_id AND seal.snapshot_id=NEW.snapshot_id
          AND seal.generation=NEW.generation AND seal.extraction_hash=NEW.extraction_hash
          AND seal.payload->'context'=workflow.annotation_materialization_context(d)) THEN
        RAISE EXCEPTION 'annotation_seal_stale';
    END IF;
    RETURN NEW;
END
$body$;

CREATE OR REPLACE FUNCTION workflow.guard_annotation_seal_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE basis workflow.annotation_sets%ROWTYPE; manifest JSONB; context JSONB;
BEGIN
    SELECT * INTO basis FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id FOR UPDATE;
    SELECT workflow.annotation_materialization_context(d) INTO context FROM workflow.documents d WHERE snapshot_id=NEW.snapshot_id;
    WITH versions AS (
        SELECT DISTINCT ON (v.annotation_id) v.*,
            min((c.result->>'generation')::bigint) OVER (PARTITION BY v.annotation_id) AS position
        FROM workflow.annotation_commands c JOIN workflow.annotation_versions v
          ON v.snapshot_id=c.snapshot_id AND v.annotation_id=c.result->>'annotation_id'
          AND v.revision=(c.result->>'revision')::bigint
        WHERE c.snapshot_id=NEW.snapshot_id AND (c.result->>'generation')::bigint<=NEW.generation
        ORDER BY v.annotation_id,v.revision DESC
    ) SELECT COALESCE(jsonb_agg(jsonb_build_object('annotation_id',annotation_id,'revision',revision,
           'payload_hash',payload_hash) ORDER BY position),'[]'::jsonb) INTO manifest FROM versions;
    IF NEW.payload->>'version' IS DISTINCT FROM 'human-annotation-v1'
        OR NEW.payload#>>'{context,class}'='beslisboom'
        OR NEW.generation>basis.generation OR NEW.extraction_hash<>basis.extraction_hash
        OR NOT ((NEW.payload->'source_identity') <@ (NEW.payload->'context'))
        OR NEW.payload#>>'{context,working_revision_id}' IS DISTINCT FROM basis.working_revision_id
        OR NEW.payload->'source_identity' IS DISTINCT FROM basis.source_identity
        OR NEW.payload->>'working_revision_id' IS DISTINCT FROM basis.working_revision_id
        OR NEW.payload->>'normalization' IS DISTINCT FROM basis.normalization
        OR NEW.payload->>'objects_revision' IS DISTINCT FROM basis.objects_revision
        OR NEW.payload->'entries' IS DISTINCT FROM manifest
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(manifest) e JOIN workflow.annotation_versions v
            ON v.snapshot_id=NEW.snapshot_id AND v.annotation_id=e->>'annotation_id'
              AND v.revision=(e->>'revision')::bigint
            WHERE v.status<>'withdrawn' AND NOT(v.payload ? 'disposition')
            GROUP BY (SELECT jsonb_agg(jsonb_build_array(a->'block_id',a->'start',a->'end') ORDER BY position)
              FROM jsonb_array_elements(v.payload->'ranges') WITH ORDINALITY AS r(a,position) WHERE a->>'role'='core')
            HAVING count(*)>1)
        OR NEW.payload->>'overview_hash' IS DISTINCT FROM NEW.overview_hash
        OR NEW.payload->>'snapshot_id' IS DISTINCT FROM NEW.snapshot_id
        OR NEW.payload->>'extraction_hash' IS DISTINCT FROM NEW.extraction_hash
        OR NEW.payload->>'generation' IS DISTINCT FROM NEW.generation::text
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(manifest) e JOIN workflow.annotation_versions v
            ON v.snapshot_id=NEW.snapshot_id AND v.annotation_id=e->>'annotation_id'
              AND v.revision=(e->>'revision')::bigint WHERE v.status NOT IN ('ready','withdrawn')) THEN
        RAISE EXCEPTION 'annotation_seal_input_changed';
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_seal_insert ON workflow.annotation_seals;
CREATE TRIGGER guard_annotation_seal_insert BEFORE INSERT ON workflow.annotation_seals
    FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_seal_insert();

CREATE OR REPLACE FUNCTION workflow.annotation_seal_current(sid TEXT, identity TEXT)
RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY DEFINER SET search_path=pg_catalog AS $body$
    SELECT EXISTS(SELECT 1 FROM workflow.annotation_sets a JOIN workflow.annotation_seals s ON s.seal_id=a.current_seal_id
        JOIN workflow.documents d ON d.snapshot_id=a.snapshot_id
        WHERE a.snapshot_id=sid AND s.seal_id=identity AND s.snapshot_id=sid AND d.class<>'beslisboom'
          AND a.generation=s.generation AND a.extraction_hash=s.extraction_hash
          AND s.payload->'context'=workflow.annotation_materialization_context(d))
$body$;

-- A genuine human attempt references its sealed input, never model configuration.
-- Exact terminal copies are the existing operational-storage migration, not new work.
CREATE OR REPLACE FUNCTION workflow.guard_annotation_legacy_attempt() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE input JSONB; seal workflow.annotation_seals%ROWTYPE; original JSONB;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id) THEN RETURN NEW; END IF;
    input:=NEW.payload;
    IF TG_TABLE_NAME='processing_attempt_inputs' THEN
        SELECT payload INTO original FROM workflow.processing_attempts WHERE attempt_id=NEW.attempt_id AND snapshot_id=NEW.snapshot_id;
        IF input IS DISTINCT FROM workflow.processing_attempt_input_for(original) THEN
            RAISE EXCEPTION 'annotation_attempt_input_changed';
        END IF;
        RETURN NEW;
    END IF;
    IF input->>'kind' IS DISTINCT FROM 'human_annotation_build' THEN
        SELECT a INTO original FROM workflow.documents d CROSS JOIN LATERAL
            jsonb_array_elements(COALESCE(d.envelope_payload->'processing_attempts','[]'::jsonb)) a
            WHERE d.snapshot_id=NEW.snapshot_id AND a->>'attempt_id'=NEW.attempt_id
              AND a->>'state' IN ('failed','succeeded','interrupted','incomplete_budget');
        IF original=input OR (TG_OP='UPDATE' AND input=OLD.payload AND input->>'state'<>'running') THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'annotation_source_owned';
    END IF;
    SELECT * INTO seal FROM workflow.annotation_seals WHERE seal_id=input->>'annotation_seal_id' AND snapshot_id=NEW.snapshot_id;
    IF NOT FOUND OR input->>'producer_contract' IS DISTINCT FROM 'human-annotation-v1'
        OR input ? 'reserved_semantic_contract_version' OR input ? 'processing_configuration'
        OR input->>'expected_revision' IS DISTINCT FROM seal.payload->>'objects_revision'
        OR input->>'source_hash' IS DISTINCT FROM seal.payload#>>'{source_identity,sha256}'
        OR input->>'source_version' IS DISTINCT FROM seal.payload#>>'{source_identity,version}' THEN
        RAISE EXCEPTION 'annotation_attempt_input_changed';
    END IF;
    IF input->>'state'='running' AND NOT workflow.annotation_seal_current(NEW.snapshot_id,seal.seal_id)
        AND NOT EXISTS(SELECT 1 FROM workflow.annotation_build_commands c WHERE c.snapshot_id=NEW.snapshot_id
            AND c.attempt_id=NEW.attempt_id AND c.seal_id=seal.seal_id AND c.command_id=input->>'command_id'
            AND c.actor_id=input->>'actor_id') THEN
        RAISE EXCEPTION 'annotation_seal_stale';
    END IF;
    IF TG_OP='UPDATE' AND (
        (input->>'annotation_seal_id',input->>'producer_contract',input->>'actor_id',input->>'command_id')
        IS DISTINCT FROM
        (OLD.payload->>'annotation_seal_id',OLD.payload->>'producer_contract',OLD.payload->>'actor_id',OLD.payload->>'command_id')) THEN
        RAISE EXCEPTION 'annotation_attempt_input_changed';
    END IF;
    RETURN NEW;
END
$body$;

-- Closed producer sum type in the existing evidence owner.
ALTER TABLE workflow.formation_evidence_roots ALTER COLUMN context_id DROP NOT NULL;
ALTER TABLE workflow.formation_evidence_roots ADD COLUMN IF NOT EXISTS annotation_seal_id TEXT
    REFERENCES workflow.annotation_seals(seal_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE workflow.formation_evidence_roots DROP CONSTRAINT IF EXISTS formation_evidence_producer;
ALTER TABLE workflow.formation_evidence_roots ADD CONSTRAINT formation_evidence_producer CHECK ((
    (header->>'layout'='1' AND context_id IS NOT NULL AND annotation_seal_id IS NULL)
    OR (header->>'layout'='2' AND context_id IS NULL AND annotation_seal_id IS NOT NULL
        AND header->>'variant'='human-annotation-v1')) IS TRUE);
ALTER TABLE workflow.formation_evidence_members DROP CONSTRAINT IF EXISTS formation_evidence_members_role_check;
ALTER TABLE workflow.formation_evidence_members ADD CONSTRAINT formation_evidence_members_role_check
    CHECK(role IN ('replay','input','source','plan','result','checkpoint','annotation'));
CREATE OR REPLACE FUNCTION workflow.guard_formation_evidence_root() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'formation_evidence_immutable'; END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.sealed OR NOT ((NEW.header->>'layout'='1' AND NEW.context_id IS NOT NULL AND NEW.annotation_seal_id IS NULL)
           OR (NEW.header->>'layout'='2' AND NEW.context_id IS NULL AND NEW.annotation_seal_id IS NOT NULL
               AND NEW.header->>'variant'='human-annotation-v1'
               AND NEW.header#>>'{capture,annotation_seal_id}'=NEW.annotation_seal_id))
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
       OR NEW.context_id IS DISTINCT FROM OLD.context_id OR NEW.annotation_seal_id IS DISTINCT FROM OLD.annotation_seal_id OR NEW.extraction_hash<>OLD.extraction_hash OR NEW.header<>OLD.header THEN
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
CREATE OR REPLACE FUNCTION workflow.guard_annotated_document() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
    IF EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id) AND (
        (NEW.source_id,NEW.document_id,NEW.source_sha256,NEW.source_version,NEW.content_kind,NEW.working_revision_id,NEW.logical_document_id)
            IS DISTINCT FROM (OLD.source_id,OLD.document_id,OLD.source_sha256,OLD.source_version,OLD.content_kind,OLD.working_revision_id,OLD.logical_document_id)
        OR (NEW.envelope_payload->'processing_attempts' IS DISTINCT FROM OLD.envelope_payload->'processing_attempts'
            AND NOT (NEW.envelope_payload->'processing_attempts' IS NULL
                AND NEW.envelope_payload->>'processing_storage'='task-v1'
                AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(COALESCE(OLD.envelope_payload->'processing_attempts','[]'::jsonb)) a
                    WHERE a->>'state' NOT IN ('failed','succeeded','interrupted','incomplete_budget')
                    OR NOT EXISTS(SELECT 1 FROM workflow.processing_attempts p WHERE p.snapshot_id=NEW.snapshot_id
                        AND p.attempt_id=a->>'attempt_id' AND p.payload=a))))
        OR NEW.envelope_payload->'semantic_replay' IS DISTINCT FROM OLD.envelope_payload->'semantic_replay'
    ) THEN
        RAISE EXCEPTION 'annotation_source_immutable';
    END IF;
    RETURN NEW;
END
$body$;

-- The native boundary validates source-bearing producer fields, while existing
-- revision/review owners may update their own confirmations and status.
CREATE OR REPLACE FUNCTION workflow.annotation_candidate_projection(value JSONB)
RETURNS JSONB LANGUAGE SQL IMMUTABLE STRICT AS $body$
 SELECT jsonb_build_object('object_id',value->'object_id','document_id',value->'document_id',
   'content',value->'content','source',value->'source','provenance',(value->'provenance')-ARRAY['content_hash','canonical_object_hash','previous_object_version','revision_reason','revision_patch_hash'],
   'proposed_object_type',value->'proposed_object_type',
   'proposed_recommendation_semantics',value->'proposed_recommendation_semantics',
   'semantic_passage',value#>'{metadata,semantic_passage}',
   'human_annotation',value#>'{metadata,human_annotation}',
   'confirmed_source_context',value#>'{metadata,confirmed_source_context}',
   'source_bound_fields',value#>'{metadata,source_bound_fields}',
   'source_bound_context',value#>'{metadata,source_bound_context}',
   'source_accountability',value#>'{metadata,source_accountability}',
   'recommendation_semantics_evidence',value#>'{metadata,recommendation_semantics_evidence}')
$body$;
CREATE OR REPLACE FUNCTION workflow.guard_annotation_legacy_writes() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
 IF TG_OP='DELETE' AND EXISTS(SELECT 1 FROM annotation_written w
      JOIN workflow.annotation_sets s USING(snapshot_id) JOIN workflow.documents d USING(snapshot_id)) THEN
   RAISE EXCEPTION 'annotation_activation_not_available';
 END IF;
 IF EXISTS(SELECT 1 FROM annotation_written w JOIN workflow.annotation_sets s USING(snapshot_id)
    JOIN workflow.documents d USING(snapshot_id) LEFT JOIN workflow.formation_evidence_roots p
      ON p.proof_id=d.formation_evidence_id
    WHERE p.proof_id IS NULL OR NOT p.sealed OR p.header->>'layout'<>'2'
       OR (TG_OP='INSERT' AND NOT workflow.annotation_seal_current(w.snapshot_id,p.annotation_seal_id)
         AND NOT EXISTS(SELECT 1 FROM workflow.document_objects prior WHERE prior.snapshot_id=w.snapshot_id
           AND prior.object_id=w.object_id AND NOT EXISTS(SELECT 1 FROM annotation_written batch
             WHERE (batch.snapshot_id,batch.object_id,batch.object_version)=(prior.snapshot_id,prior.object_id,prior.object_version))))
       OR NOT EXISTS(SELECT 1 FROM workflow.formation_evidence_members m WHERE m.proof_id=p.proof_id
          AND m.role='result' AND m.member_key=w.object_id
          AND workflow.annotation_candidate_projection(m.payload_text::jsonb)
            =workflow.annotation_candidate_projection(w.payload))) THEN
   RAISE EXCEPTION 'annotation_activation_not_available';
 END IF;
 RETURN NULL;
END
$body$;

CREATE OR REPLACE FUNCTION workflow.guard_document_input_variant() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE expected TEXT;
BEGIN
    expected:=CASE WHEN COALESCE(NEW.refs->'human'<>'null'::jsonb,false) THEN 'human' WHEN COALESCE(NEW.refs->'replay'<>'null'::jsonb,false) THEN 'semantic'
        WHEN COALESCE(NEW.refs->'tree'<>'null'::jsonb,false) OR COALESCE(NEW.metadata->'decision_graph' NOT IN ('null'::jsonb,'{}'::jsonb,'[]'::jsonb),false)
            THEN 'tree' ELSE 'absent' END;
    IF COALESCE(NEW.refs->'tree_route','false'::jsonb) IS DISTINCT FROM COALESCE((SELECT header->'tree_route' FROM workflow.processing_archive_inputs WHERE archive_id=NEW.refs#>>'{tree,archive_id}'),'false'::jsonb) THEN
        RAISE EXCEPTION 'document_inputs_tree_route_changed';
    END IF;
    IF TG_OP='UPDATE' AND OLD.refs->>'formation_variant'='human' AND expected<>'human' THEN
        RAISE EXCEPTION 'document_inputs_human_binding_changed';
    END IF;
    IF expected='human' AND EXISTS(SELECT 1 FROM workflow.documents d WHERE d.snapshot_id=NEW.snapshot_id
        AND d.formation_evidence_id IS NOT NULL AND d.formation_evidence_id IS DISTINCT FROM NEW.refs#>>'{human,proof_id}') THEN
        RAISE EXCEPTION 'document_inputs_human_binding_changed';
    END IF;
    IF expected='human' AND (NEW.refs->'replay' IS DISTINCT FROM 'null'::jsonb
        OR COALESCE(NEW.refs->'tree'<>'null'::jsonb,false)
        OR NOT EXISTS(SELECT 1 FROM workflow.formation_evidence_roots p
          WHERE p.proof_id=NEW.refs#>>'{human,proof_id}' AND p.snapshot_id=NEW.snapshot_id AND p.sealed
            AND p.header->>'layout'='2' AND NEW.refs#>>'{human,layout}'='2'
            AND p.extraction_hash=NEW.refs->>'extraction_hash')) THEN
        RAISE EXCEPTION 'document_inputs_human_binding_changed';
    END IF;
    IF NEW.refs->>'formation_variant' IS DISTINCT FROM expected THEN
        RAISE EXCEPTION 'document_inputs_formation_variant_changed';
    END IF;
    RETURN NEW;
END
$body$;
CREATE OR REPLACE FUNCTION workflow.guard_active_formation_evidence() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE document workflow.documents%ROWTYPE; proof workflow.formation_evidence_roots%ROWTYPE;
BEGIN
    SELECT * INTO document FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id;
    IF FOUND AND document.formation_evidence_id IS NOT NULL THEN
        SELECT * INTO proof FROM workflow.formation_evidence_roots WHERE proof_id=document.formation_evidence_id;
        IF proof.header->>'layout'='2' THEN
            IF NOT proof.sealed OR proof.snapshot_id<>document.snapshot_id
              OR proof.header#>'{capture,source_ref}' IS DISTINCT FROM document.review_source_ref
              OR proof.header->'source' IS DISTINCT FROM jsonb_build_object('snapshot_id',document.snapshot_id,
                'source_id',document.source_id,'document_id',document.document_id,'sha256',document.source_sha256,
                'version',document.source_version,'content_kind',document.content_kind,
                'logical_document_id',document.logical_document_id,'working_revision_id',document.working_revision_id)
              OR (document.document_storage_version=1 AND NOT EXISTS(SELECT 1 FROM workflow.document_inputs i
                WHERE i.snapshot_id=document.snapshot_id AND i.refs->>'formation_variant'='human'
                  AND i.refs#>>'{human,proof_id}'=proof.proof_id AND i.refs->>'extraction_hash'=proof.extraction_hash))
              OR (document.document_storage_version<>1 AND (document.envelope_payload#>>'{human_formation_ref,proof_id}'
                IS DISTINCT FROM proof.proof_id OR document.envelope_payload#>>'{prepared_source_extraction,record_hash}'
                IS DISTINCT FROM proof.extraction_hash))
              OR (SELECT COALESCE(jsonb_agg(DISTINCT object_id ORDER BY object_id),'[]'::jsonb)
                FROM workflow.document_objects WHERE snapshot_id=document.snapshot_id)
                IS DISTINCT FROM (SELECT COALESCE(jsonb_agg(member_key ORDER BY member_key),'[]'::jsonb)
                FROM workflow.formation_evidence_members WHERE proof_id=proof.proof_id AND role='result') THEN
                RAISE EXCEPTION 'formation_evidence_active_binding_changed';
            END IF;
            RETURN NULL;
        END IF;
        IF EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id) THEN
            RAISE EXCEPTION 'annotation_human_evidence_required';
        END IF;
    END IF;
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


-- Receipt and attempt are one committed command, including offline restore.
CREATE UNIQUE INDEX IF NOT EXISTS annotation_build_attempt_command ON workflow.annotation_build_commands(attempt_id);
CREATE OR REPLACE FUNCTION workflow.guard_annotation_build_receipt() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE sid TEXT; aid TEXT; c workflow.annotation_build_commands%ROWTYPE; a workflow.processing_attempts%ROWTYPE;
        seal workflow.annotation_seals%ROWTYPE;
BEGIN
 IF TG_TABLE_NAME='processing_attempts' THEN
   IF NEW.payload->>'kind' IS DISTINCT FROM 'human_annotation_build' THEN RETURN NULL; END IF;
 END IF;
 sid:=NEW.snapshot_id; aid:=NEW.attempt_id;
 SELECT * INTO a FROM workflow.processing_attempts WHERE attempt_id=aid;
 IF NOT FOUND OR a.payload->>'kind' IS DISTINCT FROM 'human_annotation_build' THEN
   IF TG_TABLE_NAME='annotation_build_commands' AND EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=sid) THEN
     RAISE EXCEPTION 'annotation_build_receipt_invalid';
   END IF;
   RETURN NULL;
 END IF;
 SELECT * INTO c FROM workflow.annotation_build_commands WHERE attempt_id=aid;
 SELECT * INTO seal FROM workflow.annotation_seals WHERE seal_id=a.payload->>'annotation_seal_id';
 IF c.attempt_id IS NULL OR seal.seal_id IS NULL OR (c.snapshot_id,c.command_id,c.actor_id,c.seal_id)
      IS DISTINCT FROM (a.snapshot_id,a.command_id,a.payload->>'actor_id',seal.seal_id)
    OR c.result IS DISTINCT FROM jsonb_build_object('seal_id',seal.seal_id,'attempt_id',aid,
         'generation',seal.generation,'overview_hash',seal.overview_hash)
    OR c.request_hash !~ '^[a-f0-9]{64}$' THEN
   RAISE EXCEPTION 'annotation_build_receipt_invalid';
 END IF;
 RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_build_receipt ON workflow.annotation_build_commands;
CREATE CONSTRAINT TRIGGER guard_annotation_build_receipt AFTER INSERT ON workflow.annotation_build_commands
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_build_receipt();
DROP TRIGGER IF EXISTS require_annotation_build_receipt ON workflow.processing_attempts;
CREATE CONSTRAINT TRIGGER require_annotation_build_receipt AFTER INSERT OR UPDATE ON workflow.processing_attempts
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_build_receipt();

-- Global provenance is checked at aggregate commit, allowing the existing
-- offline restore to insert object history before its sealed producer records.
-- No caller flag, alternate creator or unproved human marker is admitted.
CREATE OR REPLACE FUNCTION workflow.require_human_annotation_binding() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE actual workflow.document_objects%ROWTYPE;
BEGIN
 IF NEW.payload#>>'{metadata,semantic_passage,selection_origin}' IS DISTINCT FROM 'human_annotation'
    AND NEW.payload#>'{metadata,human_annotation}' IS NULL THEN RETURN NULL; END IF;
 SELECT * INTO actual FROM workflow.document_objects
   WHERE (snapshot_id,object_id,object_version)=(NEW.snapshot_id,NEW.object_id,NEW.object_version);
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF NOT EXISTS(SELECT 1 FROM workflow.documents d JOIN workflow.annotation_sets s USING(snapshot_id)
   JOIN workflow.formation_evidence_roots p ON p.proof_id=d.formation_evidence_id
   JOIN workflow.formation_evidence_members m ON m.proof_id=p.proof_id AND m.role='result' AND m.member_key=actual.object_id
   WHERE d.snapshot_id=actual.snapshot_id AND p.snapshot_id=d.snapshot_id AND p.sealed AND p.header->>'layout'='2'
     AND workflow.annotation_candidate_projection(actual.payload)=workflow.annotation_candidate_projection(m.payload_text::jsonb)) THEN
   RAISE EXCEPTION 'annotation_activation_not_available';
 END IF;
 RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS require_human_annotation_binding ON workflow.document_objects;
CREATE CONSTRAINT TRIGGER require_human_annotation_binding AFTER INSERT OR UPDATE ON workflow.document_objects
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.require_human_annotation_binding();
