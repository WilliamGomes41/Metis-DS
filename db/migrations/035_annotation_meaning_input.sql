-- Expand the input contract. Existing 034 candidate/model fences stay closed.
-- Version selection is durable: an older binary cannot discard v2 fields.
CREATE OR REPLACE FUNCTION workflow.annotation_relationship_key(entry_id text, anchor jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $body$
DECLARE key jsonb;
BEGIN
    IF anchor ? 'relationship_id' THEN
        IF left(anchor->>'relationship_id',8)<>'link-v1:' THEN
            RAISE EXCEPTION 'annotation_relationship_invalid';
        END IF;
        key := substring(anchor->>'relationship_id' from 9)::jsonb;
        IF jsonb_typeof(key)<>'array' OR jsonb_array_length(key)<>5
            OR key->>0 IS DISTINCT FROM entry_id OR key->>1 IS DISTINCT FROM anchor->>'role' THEN
            RAISE EXCEPTION 'annotation_relationship_invalid';
        END IF;
        RETURN key;
    END IF;
    RETURN jsonb_build_array(entry_id,anchor->>'role',anchor->>'block_id',anchor->'start',anchor->'end');
END
$body$;

CREATE OR REPLACE FUNCTION workflow.guard_annotation_input_transition() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE current_row record; previous_payload jsonb; obligation jsonb; wanted jsonb;
BEGIN
    PERFORM 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id FOR UPDATE;
    -- Check both adjacent transitions after all restore rows have arrived.
    -- Historical v1->v1 is deliberately not reinterpreted as a v2 decision.
    FOR current_row IN SELECT revision,payload FROM workflow.annotation_versions
        WHERE snapshot_id=NEW.snapshot_id AND annotation_id=NEW.annotation_id
          AND revision IN (NEW.revision,NEW.revision+1) ORDER BY revision
    LOOP
        SELECT payload INTO previous_payload FROM workflow.annotation_versions
            WHERE snapshot_id=NEW.snapshot_id AND annotation_id=NEW.annotation_id
              AND revision=current_row.revision-1;
        IF current_row.revision>1 AND NOT FOUND THEN
            RAISE EXCEPTION 'annotation_history_incomplete';
        END IF;
        IF previous_payload->>'selection_version'='human-annotation-input-v2'
            AND current_row.payload->>'selection_version' IS DISTINCT FROM 'human-annotation-input-v2' THEN
            RAISE EXCEPTION 'annotation_client_contract_stale';
        END IF;
        IF current_row.payload->>'selection_version' IS DISTINCT FROM 'human-annotation-input-v2'
            OR current_row.payload->>'status'='withdrawn' THEN CONTINUE; END IF;
        IF previous_payload ? 'field_evidence' AND NOT (current_row.payload ? 'field_evidence')
            AND NOT (current_row.payload ? 'disposition') THEN
            RAISE EXCEPTION 'annotation_client_contract_stale';
        END IF;
        IF current_row.payload->>'status'='ready' AND EXISTS (
            SELECT 1 FROM jsonb_array_elements(COALESCE(current_row.payload->'required_links','[]'::jsonb)) link
            WHERE link->'required_for_meaning'='true'::jsonb
        ) THEN RAISE EXCEPTION 'annotation_required_relationship_missing'; END IF;
        FOR obligation IN
            SELECT value FROM jsonb_array_elements(COALESCE(previous_payload->'ranges','[]'::jsonb))
                WHERE value->>'role'<>'core' AND value->'required_for_meaning'='true'::jsonb
            UNION ALL
            SELECT value FROM jsonb_array_elements(COALESCE(previous_payload->'required_links','[]'::jsonb))
                WHERE value->'required_for_meaning'='true'::jsonb
        LOOP
            wanted := workflow.annotation_relationship_key(NEW.annotation_id,obligation);
            IF NOT EXISTS (
                SELECT 1 FROM jsonb_array_elements(COALESCE(current_row.payload->'ranges','[]'::jsonb)) anchor
                    WHERE anchor->>'role'<>'core' AND anchor->'required_for_meaning'='true'::jsonb
                        AND workflow.annotation_relationship_key(NEW.annotation_id,anchor)=wanted
            ) AND NOT EXISTS (
                SELECT 1 FROM jsonb_array_elements(COALESCE(current_row.payload->'required_links','[]'::jsonb)) link
                    WHERE workflow.annotation_relationship_key(NEW.annotation_id,link)=wanted
                        AND (link->'required_for_meaning'='true'::jsonb
                             OR (link->'required_for_meaning'='false'::jsonb
                                 AND jsonb_typeof(link->'withdrawal_reason')='string'
                                 AND length(btrim(link->>'withdrawal_reason')) BETWEEN 1 AND 1000))
            ) THEN RAISE EXCEPTION 'annotation_required_relationship_missing'; END IF;
        END LOOP;
    END LOOP;
    IF EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id)
        AND (SELECT revision FROM workflow.annotation_heads
             WHERE snapshot_id=NEW.snapshot_id AND annotation_id=NEW.annotation_id)
            IS DISTINCT FROM
            (SELECT max(revision) FROM workflow.annotation_versions
             WHERE snapshot_id=NEW.snapshot_id AND annotation_id=NEW.annotation_id) THEN
        RAISE EXCEPTION 'annotation_head_stale';
    END IF;
    RETURN NULL;
END
$body$;
DROP TRIGGER IF EXISTS guard_annotation_input_transition ON workflow.annotation_versions;
CREATE CONSTRAINT TRIGGER guard_annotation_input_transition AFTER INSERT ON workflow.annotation_versions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_input_transition();
DROP TRIGGER IF EXISTS guard_annotation_head_transition ON workflow.annotation_heads;
CREATE CONSTRAINT TRIGGER guard_annotation_head_transition AFTER INSERT OR UPDATE ON workflow.annotation_heads
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.guard_annotation_input_transition();
