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
             WHERE a->>'state'='running' AND a->>'kind' IS DISTINCT FROM 'human_annotation_build')
      OR EXISTS(SELECT 1 FROM workflow.processing_attempts a WHERE a.snapshot_id=d.snapshot_id
             AND a.payload->>'state'='running' AND a.payload->>'kind' IS DISTINCT FROM 'human_annotation_build') THEN
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
 IF NEW.payload->>'state'='running' AND NEW.payload->>'kind' IS DISTINCT FROM 'human_annotation_build'
    AND workflow.prose_execution_stopped(NEW.snapshot_id) THEN
   RAISE EXCEPTION 'processing_prose_transition_required';
 END IF;
 RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_prose_transition_attempt ON workflow.processing_attempts;
CREATE TRIGGER guard_prose_transition_attempt BEFORE INSERT OR UPDATE ON workflow.processing_attempts
 FOR EACH ROW EXECUTE FUNCTION workflow.guard_prose_transition_attempt();
