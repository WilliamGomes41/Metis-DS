-- Derived lookup only. Original object payload/version remains authoritative.
-- Generated storage also covers legacy writers and restore, without dual-write.
CREATE OR REPLACE FUNCTION workflow.review_dependency_keys(value JSONB)
RETURNS JSONB LANGUAGE SQL IMMUTABLE PARALLEL SAFE AS $body$
WITH object_links AS (
    SELECT edge->'target_object_id' AS target
    FROM unnest(ARRAY[
        value->'proposed_knowledge_relations', value->'confirmed_knowledge_relations',
        value->'relations', value->'confirmed_relations'
    ]) AS family(links)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(links)='array' THEN links ELSE '[]'::jsonb END
    ) AS edge
    UNION ALL
    SELECT edge->'source_object_id'
    FROM jsonb_array_elements(CASE
        WHEN jsonb_typeof(value#>'{metadata,confirmed_source_context}')='array'
        THEN value#>'{metadata,confirmed_source_context}' ELSE '[]'::jsonb END) AS edge
), block_links AS (
    SELECT entry#>'{span,block_id}' AS target
    FROM jsonb_array_elements(CASE
        WHEN jsonb_typeof(value#>'{metadata,source_bound_context,entries}')='array'
        THEN value#>'{metadata,source_bound_context,entries}' ELSE '[]'::jsonb END) AS entry
)
SELECT jsonb_build_object(
    'objects', (SELECT COALESCE(jsonb_agg(DISTINCT target ORDER BY target),'[]'::jsonb)
                FROM object_links WHERE target IS NOT NULL),
    'blocks', (SELECT COALESCE(jsonb_agg(DISTINCT target ORDER BY target),'[]'::jsonb)
               FROM block_links WHERE target IS NOT NULL)
)
$body$;

ALTER TABLE workflow.document_objects ADD COLUMN IF NOT EXISTS
    review_dependency_keys JSONB GENERATED ALWAYS AS
        (workflow.review_dependency_keys(payload)) STORED NOT NULL;

DO $body$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_attribute a JOIN pg_attrdef d
            ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE a.attrelid='workflow.document_objects'::regclass
          AND a.attname='review_dependency_keys' AND a.attgenerated='s'
          AND replace(replace(pg_get_expr(d.adbin,d.adrelid),' ',''),'workflow.','')
              = 'review_dependency_keys(payload)'
    ) THEN RAISE EXCEPTION 'workflow_review_dependency_schema_invalid'; END IF;
END
$body$;

CREATE INDEX IF NOT EXISTS workflow_document_objects_review_dependency_keys
    ON workflow.document_objects USING gin(review_dependency_keys jsonb_path_ops);
CREATE INDEX IF NOT EXISTS workflow_document_objects_latest_position
    ON workflow.document_objects(snapshot_id,object_id,position DESC);
