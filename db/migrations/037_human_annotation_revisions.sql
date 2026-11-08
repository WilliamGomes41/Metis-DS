-- Expand human sealed input with exact existing canonical predecessors.
ALTER TABLE workflow.formation_evidence_members DROP CONSTRAINT IF EXISTS formation_evidence_members_role_check;
ALTER TABLE workflow.formation_evidence_members ADD CONSTRAINT formation_evidence_members_role_check
    CHECK(role IN ('replay','input','source','plan','result','checkpoint','annotation','candidate'));

CREATE OR REPLACE FUNCTION workflow.guard_annotation_revision_producer() RETURNS trigger
LANGUAGE plpgsql AS $body$
DECLARE revision BOOLEAN;
BEGIN
 SELECT payload ? 'revision_basis' INTO revision FROM workflow.annotation_seals WHERE seal_id=NEW.annotation_seal_id;
 IF revision IS TRUE THEN
   IF NEW.header->>'layout'<>'2' OR NEW.header->>'application' IS DISTINCT FROM 'human-annotation-revision-v1' THEN
     RAISE EXCEPTION 'annotation_revision_contract_invalid';
   END IF;
 ELSIF NEW.header ? 'application' OR EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.header->'manifest') m WHERE m->>0='candidate') THEN
   RAISE EXCEPTION 'annotation_revision_contract_invalid';
 END IF;
 RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_revision_producer ON workflow.formation_evidence_roots;
CREATE TRIGGER guard_annotation_revision_producer BEFORE INSERT ON workflow.formation_evidence_roots
 FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_revision_producer();

-- Derived from current source input and current incoming dependencies, never a
-- second mutable pending status. Unchanged shared literal source has no edge.
CREATE OR REPLACE FUNCTION workflow.annotation_pending_objects(sid TEXT)
RETURNS TABLE(object_id TEXT) LANGUAGE SQL STABLE AS $body$
 WITH RECURSIVE current_rows AS (
   SELECT DISTINCT ON (o.object_id) o.object_id,o.payload,o.review_dependency_keys
   FROM workflow.document_objects o WHERE o.snapshot_id=sid ORDER BY o.object_id,o.position DESC
 ), pending(object_id) AS (
   SELECT o.object_id FROM current_rows o JOIN workflow.annotation_heads h
     ON h.snapshot_id=sid AND h.annotation_id=o.payload#>>'{metadata,human_annotation,annotation_id}'
   WHERE h.revision::text IS DISTINCT FROM o.payload#>>'{metadata,human_annotation,revision}'
   UNION
   SELECT o.object_id FROM current_rows o JOIN pending p
     ON o.review_dependency_keys @> jsonb_build_object('objects',jsonb_build_array(p.object_id))
 ) SELECT pending.object_id FROM pending
$body$;

CREATE OR REPLACE FUNCTION workflow.guard_annotation_pending_approval() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id) THEN RETURN NEW; END IF;
 PERFORM 1 FROM workflow.documents WHERE snapshot_id=NEW.snapshot_id FOR UPDATE;
 IF NEW.valid AND EXISTS(SELECT 1 FROM workflow.annotation_pending_objects(NEW.snapshot_id) p WHERE p.object_id=NEW.object_id) THEN
   RAISE EXCEPTION 'annotation_correction_pending';
 END IF;
 RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_pending_approval ON workflow.publish_authorizations;
CREATE TRIGGER guard_annotation_pending_approval BEFORE INSERT OR UPDATE ON workflow.publish_authorizations
 FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_pending_approval();

CREATE OR REPLACE FUNCTION workflow.guard_annotation_current_input() RETURNS trigger
LANGUAGE plpgsql AS $body$
DECLARE first_generation BIGINT;
BEGIN
 -- Offline restore loads bindings before annotation owners. Check the final
 -- transaction as well; an archive cannot restore a valid stale approval.
 IF EXISTS(SELECT 1 FROM workflow.annotation_pending_objects(NEW.snapshot_id) p
   JOIN workflow.publish_authorizations a ON a.snapshot_id=NEW.snapshot_id AND a.object_id=p.object_id WHERE a.valid) THEN
   RAISE EXCEPTION 'annotation_correction_pending';
 END IF;
 SELECT min(s.generation) INTO first_generation FROM workflow.formation_evidence_roots p
   JOIN workflow.annotation_seals s ON s.seal_id=p.annotation_seal_id
   JOIN workflow.processing_attempts a ON a.attempt_id=p.header#>>'{capture,attempt_id}'
   WHERE p.snapshot_id=NEW.snapshot_id AND p.sealed AND p.header->>'layout'='2' AND a.payload->>'state'='succeeded';
 IF first_generation IS NOT NULL AND EXISTS(SELECT 1 FROM workflow.annotation_commands c
   WHERE c.snapshot_id=NEW.snapshot_id AND c.result->>'annotation_id'=NEW.annotation_id
     AND c.result->>'revision'=NEW.revision::text AND (c.result->>'generation')::bigint>first_generation)
   AND NOT EXISTS(SELECT 1 FROM workflow.formation_evidence_roots p JOIN workflow.formation_evidence_members m USING(proof_id)
     WHERE p.snapshot_id=NEW.snapshot_id AND p.sealed AND m.role='result'
       AND m.payload_text::jsonb#>>'{metadata,human_annotation,annotation_id}'=NEW.annotation_id) THEN
   RAISE EXCEPTION 'annotation_replacement_required';
 END IF;
 RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_current_input ON workflow.annotation_heads;
CREATE CONSTRAINT TRIGGER guard_annotation_current_input AFTER INSERT OR UPDATE ON workflow.annotation_heads
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_current_input();

-- A correction basis is a retained actual predecessor, not caller supplied
-- candidate text. Deferred so offline restore can load owner tables in its
-- established dependency order. Governance is deliberately not review authority.
CREATE OR REPLACE FUNCTION workflow.guard_annotation_revision_basis() RETURNS trigger
LANGUAGE plpgsql AS $body$
DECLARE b JSONB; item JSONB;
BEGIN
 b:=NEW.payload->'revision_basis';
 IF b IS NULL THEN RETURN NULL; END IF;
 IF b->>'version' IS DISTINCT FROM 'human-annotation-revision-v1'
   OR jsonb_typeof(b->'objects')<>'array' OR NOT EXISTS(
   SELECT 1 FROM workflow.formation_evidence_roots p
   WHERE p.proof_id=b->>'proof_id' AND p.snapshot_id=NEW.snapshot_id AND p.sealed AND p.header->>'layout'='2')
   OR NOT EXISTS(SELECT 1 FROM workflow.accounts WHERE account_id=b->>'actor_id') THEN
   RAISE EXCEPTION 'annotation_revision_basis_invalid';
 END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(b->'objects') LOOP
   IF NOT EXISTS(SELECT 1 FROM workflow.document_objects o
       WHERE o.snapshot_id=NEW.snapshot_id AND o.object_id=item->>'object_id'
         AND o.object_version=item->>'object_version'
         AND ((o.payload-'governance') #- '{metadata,admission}' #- '{metadata,passage_register}' #- '{metadata,candidate_eligibility}')
           =((item-'governance') #- '{metadata,admission}' #- '{metadata,passage_register}' #- '{metadata,candidate_eligibility}'))
     AND NOT (item#>'{metadata,human_annotation}' IS NULL AND EXISTS(
       SELECT 1 FROM workflow.formation_evidence_members m WHERE m.proof_id=b->>'proof_id'
         AND m.role='result' AND m.member_key=item->>'object_id'
         AND workflow.annotation_candidate_projection(m.payload_text::jsonb)=workflow.annotation_candidate_projection(item))) THEN
     RAISE EXCEPTION 'annotation_revision_basis_invalid';
   END IF;
 END LOOP;
 RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_revision_basis ON workflow.annotation_seals;
CREATE CONSTRAINT TRIGGER guard_annotation_revision_basis AFTER INSERT ON workflow.annotation_seals
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_revision_basis();

CREATE OR REPLACE FUNCTION workflow.guard_annotation_legacy_writes() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
 IF TG_OP='DELETE' THEN
   IF EXISTS(SELECT 1 FROM annotation_written w JOIN workflow.annotation_sets s USING(snapshot_id)
     JOIN workflow.documents d USING(snapshot_id)
     WHERE w.payload#>'{metadata,human_annotation}' IS NOT NULL
       OR NOT EXISTS(SELECT 1 FROM workflow.formation_evidence_roots p
          WHERE p.proof_id=d.formation_evidence_id AND p.sealed AND p.header->>'layout'='2')
       OR EXISTS(SELECT 1 FROM workflow.formation_evidence_members m
          WHERE m.proof_id=d.formation_evidence_id AND m.role='result' AND m.member_key=w.object_id)) THEN
     RAISE EXCEPTION 'annotation_activation_not_available';
   END IF;
   RETURN NULL;
 END IF;
 IF EXISTS(SELECT 1 FROM annotation_written w JOIN workflow.annotation_sets s USING(snapshot_id)
   JOIN workflow.documents d USING(snapshot_id)
   WHERE NOT EXISTS(SELECT 1 FROM workflow.formation_evidence_roots p JOIN workflow.formation_evidence_members m USING(proof_id)
     WHERE p.proof_id=d.formation_evidence_id AND p.sealed AND p.header->>'layout'='2'
       AND m.role='result' AND m.member_key=w.object_id
       AND (TG_OP<>'INSERT' OR workflow.annotation_seal_current(w.snapshot_id,p.annotation_seal_id)
         OR EXISTS(SELECT 1 FROM workflow.document_objects prior WHERE prior.snapshot_id=w.snapshot_id
           AND prior.object_id=w.object_id AND NOT EXISTS(SELECT 1 FROM annotation_written batch
             WHERE (batch.snapshot_id,batch.object_id,batch.object_version)=(prior.snapshot_id,prior.object_id,prior.object_version))))
       AND workflow.annotation_candidate_projection(m.payload_text::jsonb)=workflow.annotation_candidate_projection(w.payload))
   AND NOT (TG_OP='UPDATE' AND EXISTS(SELECT 1 FROM workflow.formation_evidence_roots p JOIN workflow.formation_evidence_members m USING(proof_id)
       WHERE p.snapshot_id=w.snapshot_id AND p.sealed AND p.header->>'layout'='2'
         AND m.role='result' AND m.member_key=w.object_id
         AND workflow.annotation_candidate_projection(m.payload_text::jsonb)=workflow.annotation_candidate_projection(w.payload)))) THEN
   RAISE EXCEPTION 'annotation_activation_not_available';
 END IF;
 RETURN NULL;
END
$body$;

CREATE OR REPLACE FUNCTION workflow.require_human_annotation_binding() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE actual workflow.document_objects%ROWTYPE;
BEGIN
 IF NEW.payload#>>'{metadata,semantic_passage,selection_origin}' IS DISTINCT FROM 'human_annotation'
    AND NEW.payload#>'{metadata,human_annotation}' IS NULL
    AND NOT EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id) THEN RETURN NULL; END IF;
 SELECT * INTO actual FROM workflow.document_objects
   WHERE (snapshot_id,object_id,object_version)=(NEW.snapshot_id,NEW.object_id,NEW.object_version);
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF NOT EXISTS(SELECT 1 FROM workflow.documents d JOIN workflow.annotation_sets s USING(snapshot_id)
   JOIN workflow.formation_evidence_roots p ON p.snapshot_id=d.snapshot_id
   JOIN workflow.formation_evidence_members m ON m.proof_id=p.proof_id AND m.role='result' AND m.member_key=actual.object_id
   WHERE d.snapshot_id=actual.snapshot_id AND p.sealed AND p.header->>'layout'='2'
     AND (p.proof_id=d.formation_evidence_id OR EXISTS(SELECT 1 FROM workflow.document_objects later
       WHERE later.snapshot_id=actual.snapshot_id AND later.object_id=actual.object_id AND later.position>actual.position))
     AND workflow.annotation_candidate_projection(actual.payload)=workflow.annotation_candidate_projection(m.payload_text::jsonb)) THEN
   RAISE EXCEPTION 'annotation_activation_not_available';
 END IF;
 RETURN NULL;
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
        OR (NOT (NEW.payload ? 'revision_basis') AND NEW.payload->>'objects_revision' IS DISTINCT FROM basis.objects_revision)
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


