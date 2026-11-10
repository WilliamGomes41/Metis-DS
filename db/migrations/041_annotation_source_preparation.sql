-- Additive delivery support: source preparation creates no knowledge objects.
CREATE OR REPLACE FUNCTION workflow.annotation_source_attempt_valid(sid TEXT,input JSONB)
RETURNS BOOLEAN LANGUAGE SQL STABLE AS $body$
 SELECT COALESCE(EXISTS(SELECT 1 FROM workflow.documents d WHERE d.snapshot_id=sid
  AND input->>'kind'='human_annotation_source'
  AND input->>'producer_contract'='human-annotation-source-v1'
  AND COALESCE(input->>'command_id','') ~ '^[A-Za-z0-9_-]{1,128}$'
  AND COALESCE(input->>'expected_revision','')<>''
  AND EXISTS(SELECT 1 FROM workflow.accounts WHERE account_id=input->>'actor_id')
  AND jsonb_typeof(input->'limits')='object'
  AND COALESCE(input#>>'{processing_configuration,working_revision_id}','')<>''
  AND COALESCE(input#>>'{processing_configuration,logical_document_id}','')<>''
  AND input#>>'{processing_configuration,mode}'='human-annotation-source-v1'
  AND NOT input ? 'annotation_seal_id' AND NOT input ? 'reserved_semantic_contract_version'
  AND COALESCE(input#>>'{processing_configuration,extractor_contract}','')<>''
  AND input#>'{processing_configuration,source_identity}'=jsonb_build_object(
      'snapshot_id',d.snapshot_id,'source_id',d.source_id,'document_id',d.document_id,
      'sha256',d.source_sha256,'version',d.source_version,'content_kind',d.content_kind)
  AND input->>'source_hash'=d.source_sha256 AND input->>'source_version'=d.source_version
  AND input->>'state' IN ('running','succeeded','failed','interrupted','incomplete_budget')
  AND (input->>'state'<>'running' OR (
      input#>>'{processing_configuration,working_revision_id}'=d.working_revision_id
      AND input#>>'{processing_configuration,logical_document_id}'=d.logical_document_id
      AND NOT EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=sid)
  ))),false)
$body$;
CREATE OR REPLACE FUNCTION workflow.guard_annotation_source_attempt() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
 IF TG_OP='UPDATE' AND OLD.payload->>'kind'='human_annotation_source' AND (
   (NEW.payload->'kind',NEW.payload->'producer_contract',NEW.payload->'processing_configuration',
    NEW.payload->'actor_id',NEW.payload->'command_id',NEW.payload->'expected_revision',
    NEW.payload->'source_hash',NEW.payload->'source_version',NEW.payload->'started_at',
    NEW.payload->'expires_at',NEW.payload->'limits') IS DISTINCT FROM
   (OLD.payload->'kind',OLD.payload->'producer_contract',OLD.payload->'processing_configuration',
    OLD.payload->'actor_id',OLD.payload->'command_id',OLD.payload->'expected_revision',
    OLD.payload->'source_hash',OLD.payload->'source_version',OLD.payload->'started_at',
    OLD.payload->'expires_at',OLD.payload->'limits')) THEN
   RAISE EXCEPTION 'annotation_source_attempt_changed';
 END IF;
 IF NEW.payload->>'kind'='human_annotation_source' AND (
    NEW.payload->>'attempt_id' IS DISTINCT FROM NEW.attempt_id
    OR NEW.payload->>'command_id' IS DISTINCT FROM NEW.command_id
    OR (NEW.payload->>'started_at')::timestamptz IS DISTINCT FROM NEW.started_at
    OR NOT workflow.annotation_source_attempt_valid(NEW.snapshot_id,NEW.payload)) THEN
   RAISE EXCEPTION 'annotation_source_attempt_invalid';
 END IF;
 RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_source_attempt ON workflow.processing_attempts;
CREATE TRIGGER guard_annotation_source_attempt BEFORE INSERT OR UPDATE ON workflow.processing_attempts
 FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_source_attempt();

-- Additive per-WorkingRevision execution fence. No rows are stopped at install.
CREATE OR REPLACE FUNCTION workflow.prose_execution_stopped(sid TEXT)
RETURNS BOOLEAN LANGUAGE SQL STABLE AS $body$
 SELECT EXISTS(SELECT 1 FROM workflow.documents d,
   LATERAL jsonb_array_elements(COALESCE(workflow.current_document_envelope(d)->'prose_transitions','[]'::jsonb)) p
   WHERE d.snapshot_id=sid AND p->>'working_revision_id'=d.working_revision_id)
$body$;

CREATE OR REPLACE FUNCTION workflow.check_prose_transition_payload(
 d workflow.documents, previous JSONB, submitted JSONB) RETURNS VOID
LANGUAGE plpgsql AS $body$
DECLARE old_records JSONB; records JSONB; entry JSONB; prefix JSONB;
BEGIN
 old_records:=COALESCE(previous->'prose_transitions','[]'::jsonb);
 records:=COALESCE(submitted->'prose_transitions','[]'::jsonb);
 IF jsonb_typeof(old_records)<>'array' OR jsonb_typeof(records)<>'array'
    OR jsonb_array_length(records)<jsonb_array_length(old_records) THEN
   RAISE EXCEPTION 'prose_transition_history_immutable';
 END IF;
 SELECT COALESCE(jsonb_agg(value ORDER BY ord),'[]'::jsonb) INTO prefix
 FROM jsonb_array_elements(records) WITH ORDINALITY v(value,ord)
 WHERE ord<=jsonb_array_length(old_records);
 IF prefix IS DISTINCT FROM old_records THEN RAISE EXCEPTION 'prose_transition_history_immutable'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(records) p GROUP BY p->>'working_revision_id' HAVING count(*)>1) THEN
   RAISE EXCEPTION 'prose_transition_duplicate_revision';
 END IF;
 FOR entry IN SELECT value FROM jsonb_array_elements(records) WITH ORDINALITY v(value,ord)
          WHERE ord>jsonb_array_length(old_records) LOOP
   IF entry->>'version' IS DISTINCT FROM 'prose-transition-v1'
      OR entry->>'snapshot_id' IS DISTINCT FROM d.snapshot_id
      OR entry->>'source_hash' IS DISTINCT FROM d.source_sha256
      OR entry->>'source_version' IS DISTINCT FROM d.source_version
      OR COALESCE(entry->>'working_revision_id','')=''
      OR COALESCE(entry->>'command_id','') !~ '^[A-Za-z0-9_-]{1,128}$'
      OR COALESCE(entry->>'request_hash','') !~ '^[a-f0-9]{64}$'
      OR COALESCE(btrim(entry->>'reason'),'')=''
      OR NOT EXISTS(SELECT 1 FROM workflow.accounts WHERE account_id=entry->>'actor_id') THEN
     RAISE EXCEPTION 'prose_transition_invalid';
   END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(records) p
           WHERE p->>'working_revision_id'=d.working_revision_id) THEN
   IF EXISTS(SELECT 1 FROM jsonb_array_elements(COALESCE(submitted->'processing_attempts','[]'::jsonb)) a
             WHERE a->>'state'='running' AND COALESCE(a->>'kind','') NOT IN ('human_annotation_build','human_annotation_source'))
      OR EXISTS(SELECT 1 FROM workflow.processing_attempts a WHERE a.snapshot_id=d.snapshot_id
             AND a.payload->>'state'='running' AND COALESCE(a.payload->>'kind','') NOT IN ('human_annotation_build','human_annotation_source')) THEN
     RAISE EXCEPTION 'processing_prose_transition_required';
   END IF;
 END IF;
END
$body$;

CREATE OR REPLACE FUNCTION workflow.guard_prose_transition_document() RETURNS trigger
LANGUAGE plpgsql AS $body$
DECLARE previous JSONB:='{}'::jsonb; submitted JSONB;
BEGIN
 IF TG_OP='UPDATE' THEN
   previous:=CASE WHEN OLD.document_storage_version=1 THEN
     (SELECT metadata FROM workflow.document_inputs WHERE snapshot_id=OLD.snapshot_id)
     ELSE OLD.envelope_payload END;
 END IF;
 submitted:=CASE WHEN NEW.document_storage_version=1 THEN
   (SELECT metadata FROM workflow.document_inputs WHERE snapshot_id=NEW.snapshot_id)
   ELSE NEW.envelope_payload END;
 PERFORM workflow.check_prose_transition_payload(NEW,previous,submitted);
 IF TG_OP='UPDATE' AND NEW.formation_evidence_id IS DISTINCT FROM OLD.formation_evidence_id
    AND NEW.formation_evidence_id IS NOT NULL
    AND EXISTS(SELECT 1 FROM jsonb_array_elements(COALESCE(submitted->'prose_transitions','[]'::jsonb)) p
               WHERE p->>'working_revision_id'=NEW.working_revision_id)
    AND NOT EXISTS(SELECT 1 FROM workflow.formation_evidence_roots r
                   WHERE r.proof_id=NEW.formation_evidence_id AND r.annotation_seal_id IS NOT NULL) THEN
   RAISE EXCEPTION 'processing_prose_transition_required';
 END IF;
 RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_prose_transition_document ON workflow.documents;
CREATE TRIGGER guard_prose_transition_document BEFORE INSERT OR UPDATE ON workflow.documents
 FOR EACH ROW EXECUTE FUNCTION workflow.guard_prose_transition_document();

CREATE OR REPLACE FUNCTION workflow.guard_prose_transition_inputs() RETURNS trigger
LANGUAGE plpgsql AS $body$
DECLARE d workflow.documents%ROWTYPE; previous JSONB:='{}'::jsonb;
BEGIN
 SELECT * INTO d FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id;
 IF TG_OP='UPDATE' THEN previous:=OLD.metadata;
 ELSE previous:=d.envelope_payload; END IF;
 PERFORM workflow.check_prose_transition_payload(d,previous,NEW.metadata);
 RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_prose_transition_inputs ON workflow.document_inputs;
CREATE TRIGGER guard_prose_transition_inputs BEFORE INSERT OR UPDATE OF metadata ON workflow.document_inputs
 FOR EACH ROW EXECUTE FUNCTION workflow.guard_prose_transition_inputs();

CREATE OR REPLACE FUNCTION workflow.guard_prose_transition_attempt() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
 -- Serialize alternate SQL/rollback writers with the same document boundary.
 PERFORM 1 FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id FOR UPDATE;
 IF NEW.payload->>'state'='running' AND COALESCE(NEW.payload->>'kind','') NOT IN ('human_annotation_build','human_annotation_source')
    AND workflow.prose_execution_stopped(NEW.snapshot_id) THEN
   RAISE EXCEPTION 'processing_prose_transition_required';
 END IF;
 RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_prose_transition_attempt ON workflow.processing_attempts;
CREATE TRIGGER guard_prose_transition_attempt BEFORE INSERT OR UPDATE ON workflow.processing_attempts
 FOR EACH ROW EXECUTE FUNCTION workflow.guard_prose_transition_attempt();

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
    IF input->>'kind'='human_annotation_source' THEN
        IF input->>'state'='running' OR NOT workflow.annotation_source_attempt_valid(NEW.snapshot_id,input) THEN
            RAISE EXCEPTION 'annotation_source_owned';
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
