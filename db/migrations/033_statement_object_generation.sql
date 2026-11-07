-- Preserve migration021's exact per-row generation, with one document update
-- per affected snapshot/statement. Row-level history/fact guards remain intact.
-- Transition tables include only actual writes, after BEFORE-trigger refusals.
CREATE OR REPLACE FUNCTION workflow.advance_statement_object_generation() RETURNS trigger
LANGUAGE plpgsql AS $body$
DECLARE changed RECORD;
BEGIN
    FOR changed IN
        SELECT snapshot_id,count(*) AS affected FROM changed_objects
        GROUP BY snapshot_id ORDER BY snapshot_id
    LOOP
        UPDATE workflow.documents SET object_generation=object_generation+changed.affected
        WHERE snapshot_id=changed.snapshot_id AND processing_storage_version=1;
    END LOOP;
    RETURN NULL;
END
$body$;

DROP TRIGGER IF EXISTS advance_object_generation ON workflow.document_objects;
DROP TRIGGER IF EXISTS advance_object_generation_insert ON workflow.document_objects;
DROP TRIGGER IF EXISTS advance_object_generation_update ON workflow.document_objects;
DROP TRIGGER IF EXISTS advance_object_generation_delete ON workflow.document_objects;

CREATE TRIGGER advance_object_generation_insert AFTER INSERT ON workflow.document_objects
    REFERENCING NEW TABLE AS changed_objects FOR EACH STATEMENT
    EXECUTE FUNCTION workflow.advance_statement_object_generation();
CREATE TRIGGER advance_object_generation_update AFTER UPDATE ON workflow.document_objects
    REFERENCING NEW TABLE AS changed_objects FOR EACH STATEMENT
    EXECUTE FUNCTION workflow.advance_statement_object_generation();
CREATE TRIGGER advance_object_generation_delete AFTER DELETE ON workflow.document_objects
    REFERENCING OLD TABLE AS changed_objects FOR EACH STATEMENT
    EXECUTE FUNCTION workflow.advance_statement_object_generation();
