-- Additive, non-authoritative current Review inputs. No backfill or reader cutover.
ALTER TABLE workflow.documents ADD COLUMN IF NOT EXISTS review_card_envelope JSONB;

CREATE TABLE IF NOT EXISTS workflow.review_fact_state (
    snapshot_id TEXT PRIMARY KEY REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    input_epoch BIGINT NOT NULL DEFAULT 0,
    prepared_epoch BIGINT,
    initialized BOOLEAN NOT NULL DEFAULT false,
    expected_heads INTEGER NOT NULL DEFAULT 0 CHECK (expected_heads>=0),
    source_identity JSONB
);
CREATE TABLE IF NOT EXISTS workflow.review_object_facts (
    snapshot_id TEXT NOT NULL REFERENCES workflow.review_fact_state(snapshot_id) ON DELETE CASCADE,
    object_id TEXT NOT NULL,
    history_count INTEGER NOT NULL DEFAULT 0 CHECK (history_count>=0),
    dirty BOOLEAN NOT NULL DEFAULT true,
    current_version TEXT,
    object_order INTEGER,
    record JSONB,
    record_hash TEXT,
    PRIMARY KEY(snapshot_id,object_id)
);
CREATE INDEX IF NOT EXISTS review_object_facts_dirty
    ON workflow.review_object_facts(snapshot_id) WHERE dirty;
CREATE INDEX IF NOT EXISTS review_object_facts_current
    ON workflow.review_object_facts(snapshot_id,object_order,object_id) WHERE history_count>0;

CREATE OR REPLACE FUNCTION workflow.review_card_envelope_for(payload JSONB)
RETURNS JSONB LANGUAGE SQL IMMUTABLE STRICT AS $body$
    SELECT COALESCE((SELECT jsonb_object_agg(k,compact->k)
      FROM unnest(ARRAY['snapshot_id','class','review_policy','named_reviewers','title','version',
        'publication_eligibility','state','date','source_id','document_id','sha256','content_kind',
        'is_live_capture','acquired_at','processing_blocker','source_declaration',
        'review_configuration','configuration_source',
        'prepared_source_extraction','decision_graph','decision_graph_reviews',
        '_review_formation_notice','_review_has_replay']) k WHERE compact ? k),'{}'::jsonb)
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
    FROM (SELECT workflow.review_read_envelope_for(payload) AS compact) s
$body$;

CREATE OR REPLACE FUNCTION workflow.refresh_review_card_envelope()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    NEW.review_card_envelope := workflow.review_card_envelope_for(NEW.envelope_payload)
      || jsonb_build_object('snapshot_id',NEW.snapshot_id,'document_id',NEW.document_id,
        'source_id',NEW.source_id,'title',NEW.title,'class',NEW.class,'state',NEW.state,
        'date',to_char(NEW.source_date,'YYYY-MM-DD'),'version',NEW.source_version,
        'sha256',NEW.source_sha256,'content_kind',NEW.content_kind,
        'publication_eligibility',NEW.publication_eligibility)
      || jsonb_build_object('_source_identity',jsonb_build_object(
        'snapshot_id',NEW.snapshot_id,'source_id',NEW.source_id,'document_id',NEW.document_id,'sha256',NEW.source_sha256,
        'version',NEW.source_version,'content_kind',NEW.content_kind,
        'extraction',NEW.envelope_payload#>'{prepared_source_extraction,record_hash}',
        'extraction_header',NEW.review_read_envelope->'prepared_source_extraction',
        'source_ref',NEW.review_source_ref));
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS zzzz_refresh_review_card_envelope ON workflow.documents;
CREATE TRIGGER zzzz_refresh_review_card_envelope BEFORE INSERT OR UPDATE ON workflow.documents
    FOR EACH ROW EXECUTE FUNCTION workflow.refresh_review_card_envelope();

CREATE OR REPLACE FUNCTION workflow.review_card_document_change()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF TG_OP='INSERT' THEN
        INSERT INTO workflow.review_fact_state(snapshot_id,initialized,prepared_epoch,source_identity)
        VALUES(NEW.snapshot_id,true,0,NEW.review_card_envelope->'_source_identity');
    ELSIF (NEW.review_card_envelope->'_source_identity')::text IS DISTINCT FROM
          (OLD.review_card_envelope->'_source_identity')::text THEN
        UPDATE workflow.review_fact_state SET initialized=false,input_epoch=input_epoch+1
        WHERE snapshot_id=NEW.snapshot_id;
    END IF;
    RETURN NEW;
END
$body$;
DROP TRIGGER IF EXISTS review_card_document_change ON workflow.documents;
CREATE TRIGGER review_card_document_change AFTER INSERT OR UPDATE ON workflow.documents
    FOR EACH ROW EXECUTE FUNCTION workflow.review_card_document_change();

-- These fields are excluded by the canonical hash and by intrinsic source proofs.
-- They remain current read inputs; copying them is not a second Review rulebook.
CREATE OR REPLACE FUNCTION workflow.review_fact_static_input(payload JSONB)
RETURNS TEXT LANGUAGE SQL IMMUTABLE STRICT AS $body$
    SELECT (((payload-'governance') #- '{metadata,admission}')
       #- '{metadata,passage_register}' #- '{metadata,candidate_eligibility}')::text
$body$;
CREATE OR REPLACE FUNCTION workflow.review_fact_live_fields(record JSONB,payload JSONB)
RETURNS JSONB LANGUAGE SQL IMMUTABLE STRICT AS $body$
    SELECT jsonb_set(record,'{fields}',((record->'fields')-'governance')
      || CASE WHEN payload ? 'governance' THEN jsonb_build_object('governance',payload->'governance') ELSE '{}' END
      || jsonb_build_object('metadata',((record#>'{fields,metadata}') - ARRAY['admission','passage_register','candidate_eligibility'])
        || COALESCE((SELECT jsonb_object_agg(k,CASE WHEN k='admission' AND jsonb_typeof(payload->'metadata'->k)='object'
           THEN (SELECT COALESCE(jsonb_object_agg(a,payload->'metadata'->k->a),'{}'::jsonb)
             FROM unnest(ARRAY['gate_result','source_hash','document_version','section_path']) a
             WHERE payload->'metadata'->k ? a) ELSE payload->'metadata'->k END)
          FROM unnest(ARRAY['admission','passage_register']) k
          WHERE payload->'metadata' ? k),'{}'::jsonb)))
$body$;

CREATE OR REPLACE FUNCTION workflow.invalidate_review_object(sid TEXT,oid TEXT,delta INTEGER)
RETURNS VOID LANGUAGE plpgsql AS $body$
DECLARE previous_count INTEGER; following_count INTEGER;
BEGIN
    -- Document deletion owns cascading removal of its derived rows.
    IF NOT EXISTS(SELECT 1 FROM workflow.documents WHERE snapshot_id=sid) THEN RETURN; END IF;
    INSERT INTO workflow.review_fact_state(snapshot_id) VALUES(sid) ON CONFLICT DO NOTHING;
    PERFORM 1 FROM workflow.review_fact_state WHERE snapshot_id=sid FOR UPDATE;
    SELECT history_count INTO previous_count FROM workflow.review_object_facts
      WHERE snapshot_id=sid AND object_id=oid FOR UPDATE;
    IF previous_count IS NULL THEN
        previous_count:=0;
        IF delta<=0 THEN UPDATE workflow.review_fact_state SET initialized=false WHERE snapshot_id=sid; END IF;
    END IF;
    following_count:=GREATEST(0,previous_count+delta);
    INSERT INTO workflow.review_object_facts(snapshot_id,object_id,history_count,dirty)
      VALUES(sid,oid,following_count,true) ON CONFLICT(snapshot_id,object_id)
      DO UPDATE SET history_count=EXCLUDED.history_count,dirty=true;
    UPDATE workflow.review_fact_state SET input_epoch=input_epoch+1,
      expected_heads=GREATEST(0,expected_heads+(following_count>0)::integer-(previous_count>0)::integer)
      WHERE snapshot_id=sid;
END
$body$;
CREATE OR REPLACE FUNCTION workflow.review_card_object_change()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    IF TG_OP='UPDATE' AND (NEW.snapshot_id,NEW.object_id,NEW.object_version,NEW.position)
       IS NOT DISTINCT FROM (OLD.snapshot_id,OLD.object_id,OLD.object_version,OLD.position) THEN
        IF workflow.review_fact_static_input(NEW.payload)=workflow.review_fact_static_input(OLD.payload) THEN
            -- Also protects explicit preparation CAS from a concurrent live-field edit.
            UPDATE workflow.review_fact_state SET input_epoch=input_epoch+1,
              prepared_epoch=CASE WHEN prepared_epoch=input_epoch THEN input_epoch+1 ELSE prepared_epoch END
              WHERE snapshot_id=NEW.snapshot_id;
            UPDATE workflow.review_object_facts SET record=workflow.review_fact_live_fields(record,NEW.payload),
              record_hash=encode(sha256(convert_to(workflow.review_fact_live_fields(record,NEW.payload)::text,'UTF8')),'hex')
              WHERE snapshot_id=NEW.snapshot_id AND object_id=NEW.object_id AND NOT dirty
                AND current_version=NEW.object_version AND record IS NOT NULL
                AND record_hash=encode(sha256(convert_to(record::text,'UTF8')),'hex');
            RETURN NEW;
        END IF;
        PERFORM workflow.invalidate_review_object(NEW.snapshot_id,NEW.object_id,0);
    ELSE
        IF TG_OP IN ('DELETE','UPDATE') THEN
            PERFORM workflow.invalidate_review_object(OLD.snapshot_id,OLD.object_id,-1);
        END IF;
        IF TG_OP IN ('INSERT','UPDATE') THEN
            PERFORM workflow.invalidate_review_object(NEW.snapshot_id,NEW.object_id,1);
        END IF;
    END IF;
    RETURN COALESCE(NEW,OLD);
END
$body$;
DROP TRIGGER IF EXISTS review_card_object_change ON workflow.document_objects;
CREATE TRIGGER review_card_object_change AFTER INSERT OR UPDATE OR DELETE ON workflow.document_objects
    FOR EACH ROW EXECUTE FUNCTION workflow.review_card_object_change();

CREATE OR REPLACE FUNCTION workflow.review_card_truncate()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    UPDATE workflow.review_fact_state SET initialized=false,input_epoch=input_epoch+1,expected_heads=0;
    UPDATE workflow.review_object_facts SET dirty=true,history_count=0;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS review_card_truncate ON workflow.document_objects;
CREATE TRIGGER review_card_truncate AFTER TRUNCATE ON workflow.document_objects
    FOR EACH STATEMENT EXECUTE FUNCTION workflow.review_card_truncate();
