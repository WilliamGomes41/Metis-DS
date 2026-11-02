-- Derived execution inputs; document_objects remains the history authority.
-- Identifier coverage only; no content backfill, candidate creation or publication decision.
CREATE TABLE IF NOT EXISTS workflow.object_revision_frontiers (
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    object_id TEXT NOT NULL,
    mutation_epoch BIGINT NOT NULL DEFAULT 0,
    certificate JSONB,
    certificate_hash TEXT,
    PRIMARY KEY(snapshot_id,object_id)
);
-- Identifier coverage only: existing histories acquire NO positive certificate.
INSERT INTO workflow.object_revision_frontiers(snapshot_id,object_id)
    SELECT DISTINCT snapshot_id,object_id FROM workflow.document_objects ON CONFLICT DO NOTHING;
DO $body$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='workflow.object_revision_frontiers'::regclass
                  AND conname='workflow_revision_frontier_integrity') THEN
        UPDATE workflow.object_revision_frontiers SET certificate=NULL,certificate_hash=NULL;
        ALTER TABLE workflow.object_revision_frontiers ADD CONSTRAINT workflow_revision_frontier_integrity
            CHECK ((certificate IS NULL AND certificate_hash IS NULL) OR
                   (certificate IS NOT NULL AND certificate_hash IS NOT NULL
                    AND jsonb_typeof(certificate)='object' AND certificate->>'epoch' IS NOT NULL
                    AND certificate->>'epoch'=mutation_epoch::text
                    AND certificate ?& ARRAY['contract','snapshot_id','object_id','first_position',
                        'source_sequence','object_type']
                    AND jsonb_typeof(certificate->'first_position')='number'
                    AND (certificate->>'first_position') ~ '^[0-9]+$'
                    AND certificate->>'snapshot_id'=snapshot_id AND certificate->>'object_id'=object_id
                    AND certificate_hash=encode(sha256(convert_to(certificate::text,'UTF8')),'hex')) IS TRUE);
    END IF;
END
$body$;
CREATE INDEX IF NOT EXISTS workflow_source_command_receipt
    ON workflow.review_events ((event_payload#>>'{details,snapshot_id}'),event_type,
                              (event_payload#>>'{details,command_id}'),event_id);

CREATE OR REPLACE FUNCTION workflow.invalidate_revision_frontier(sid TEXT,oid TEXT)
RETURNS VOID LANGUAGE plpgsql AS $body$
BEGIN
    -- Share the existing document serialization boundary even for native0 writers.
    -- An unselected passage cannot change adjacency during a protected command.
    PERFORM 1 FROM workflow.documents WHERE snapshot_id=sid FOR UPDATE;
    IF NOT FOUND THEN RETURN; END IF;
    INSERT INTO workflow.object_revision_frontiers(snapshot_id,object_id,mutation_epoch)
      VALUES(sid,oid,1) ON CONFLICT(snapshot_id,object_id) DO UPDATE
      SET mutation_epoch=workflow.object_revision_frontiers.mutation_epoch+1,
          certificate=NULL,certificate_hash=NULL;
END
$body$;
CREATE OR REPLACE FUNCTION workflow.object_revision_frontier_change()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF TG_OP='UPDATE' THEN
        PERFORM workflow.invalidate_revision_frontier(OLD.snapshot_id,OLD.object_id);
        IF (NEW.snapshot_id,NEW.object_id) IS DISTINCT FROM (OLD.snapshot_id,OLD.object_id) THEN
            PERFORM workflow.invalidate_revision_frontier(NEW.snapshot_id,NEW.object_id);
        END IF;
    ELSIF TG_OP='DELETE' THEN
        PERFORM workflow.invalidate_revision_frontier(OLD.snapshot_id,OLD.object_id);
    ELSE
        PERFORM workflow.invalidate_revision_frontier(NEW.snapshot_id,NEW.object_id);
    END IF;
    RETURN COALESCE(NEW,OLD);
END
$body$;
DROP TRIGGER IF EXISTS zz_object_revision_frontier_change ON workflow.document_objects;
CREATE TRIGGER zz_object_revision_frontier_change AFTER INSERT OR UPDATE OR DELETE
    ON workflow.document_objects FOR EACH ROW EXECUTE FUNCTION workflow.object_revision_frontier_change();

CREATE OR REPLACE FUNCTION workflow.object_revision_frontier_truncate()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    UPDATE workflow.object_revision_frontiers SET mutation_epoch=mutation_epoch+1,
        certificate=NULL,certificate_hash=NULL;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS zz_object_revision_frontier_truncate ON workflow.document_objects;
CREATE TRIGGER zz_object_revision_frontier_truncate AFTER TRUNCATE ON workflow.document_objects
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.object_revision_frontier_truncate();

-- An index entry cannot disappear while authoritative rows still refer to it.
-- Deferred because the AFTER INSERT trigger creates the derived entry.
DO $body$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='workflow.document_objects'::regclass
                  AND conname='workflow_object_revision_frontier_fk') THEN
        ALTER TABLE workflow.document_objects ADD CONSTRAINT workflow_object_revision_frontier_fk
            FOREIGN KEY(snapshot_id,object_id) REFERENCES workflow.object_revision_frontiers(snapshot_id,object_id)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END
$body$;

CREATE OR REPLACE FUNCTION workflow.revision_source_sequence(value JSONB)
RETURNS NUMERIC LANGUAGE SQL IMMUTABLE STRICT PARALLEL SAFE AS $body$
    SELECT CASE WHEN jsonb_typeof(value->'source_sequence')='number'
                THEN (value->>'source_sequence')::numeric ELSE NULL END
$body$;
CREATE INDEX IF NOT EXISTS workflow_revision_source_order ON workflow.object_revision_frontiers
    (snapshot_id,workflow.revision_source_sequence(certificate),((certificate->>'first_position')::integer))
    WHERE certificate IS NOT NULL;
CREATE INDEX IF NOT EXISTS workflow_revision_frontier_unprepared ON workflow.object_revision_frontiers(snapshot_id)
    WHERE certificate IS NULL OR workflow.revision_source_sequence(certificate) IS NULL;

-- Existing object-writer roles need these trigger privileges atomically with
-- installation. Copy only explicit SELECT+INSERT+UPDATE grants, never ALL/PUBLIC.
DO $body$
DECLARE writer TEXT;
BEGIN
    FOR writer IN
        SELECT r.rolname FROM pg_class c
        CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a
        JOIN pg_roles r ON r.oid=a.grantee
        WHERE c.oid='workflow.document_objects'::regclass
          AND a.privilege_type IN ('SELECT','INSERT','UPDATE')
        GROUP BY r.rolname HAVING count(DISTINCT a.privilege_type)=3
    LOOP
        EXECUTE format('GRANT SELECT,INSERT,UPDATE ON workflow.object_revision_frontiers TO %I',writer);
    END LOOP;
END
$body$;
