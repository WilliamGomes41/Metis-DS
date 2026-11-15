-- #1060 deel 2 (besluit William, 2026-11-15): the essential relationship is gone.
-- The card never marks a link as essential and the kernel no longer knows required_links,
-- so the guard keeps only the version and field-evidence fences of 035, and fences the retired
-- fields at the database boundary: a writer that still sends them (the pre-change application
-- during cutover, or an old backup) is refused instead of storing a head the kernel can no longer read.
-- Rows already stored are not re-checked; this is an AFTER INSERT guard.
CREATE OR REPLACE FUNCTION workflow.guard_annotation_input_transition() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE current_row record; previous_payload jsonb;
BEGIN
    IF TG_TABLE_NAME='annotation_versions' THEN
        IF NEW.payload ? 'required_links'
            OR jsonb_path_exists(NEW.payload,'$.ranges[*].required_for_meaning')
            OR jsonb_path_exists(NEW.payload,'$.pending_range.required_for_meaning') THEN
            RAISE EXCEPTION 'annotation_client_contract_stale';
        END IF;
    END IF;
    PERFORM 1 FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id FOR UPDATE;
    -- Check both adjacent transitions after all restore rows have arrived.
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
-- Only the essential-relationship check used this key.
DROP FUNCTION IF EXISTS workflow.annotation_relationship_key(text,jsonb);
