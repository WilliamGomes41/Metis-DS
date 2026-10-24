-- Expand only. Keep the previous application active during explicit batch
-- backfill; deploy the summary-only reader after no NULL projections remain.
ALTER TABLE workflow.documents
    ADD COLUMN IF NOT EXISTS source_selection_summary JSONB;

CREATE OR REPLACE FUNCTION workflow.source_selection_summary_for(payload JSONB)
RETURNS JSONB LANGUAGE SQL IMMUTABLE STRICT AS $body$
    SELECT jsonb_build_object(
        'schema_version', 1,
        'binary_path', e.binary_path,
        'received_source', e.received_source,
        'processing_configuration', e.processing_configuration,
        'semantic_replay', jsonb_build_object('provider_evidence', jsonb_build_object(
            'formation_incomplete', e.semantic_replay->'provider_evidence'->'formation_incomplete',
            'formation_progress', e.semantic_replay->'provider_evidence'->'formation_progress')),
        'pending_rejection_count', jsonb_array_length(COALESCE(NULLIF(
            e.semantic_replay->'provider_evidence'->'pending_rejections', 'null'::jsonb), '[]'::jsonb)),
        'source_fragment_count', CASE WHEN jsonb_array_length(COALESCE(NULLIF(
            e.quality_processing_runs, 'null'::jsonb), '[]'::jsonb)) > 0
            THEN jsonb_array_length(COALESCE(NULLIF(
                e.quality_processing_runs->-1->'source_fragments', 'null'::jsonb), '[]'::jsonb))
            ELSE NULL END,
        'processing_attempts', CASE WHEN jsonb_array_length(COALESCE(NULLIF(
            e.processing_attempts, 'null'::jsonb), '[]'::jsonb)) > 0
            THEN jsonb_build_array(jsonb_build_object(
                'state', e.processing_attempts->-1->'state',
                'kind', e.processing_attempts->-1->'kind',
                'started_at', e.processing_attempts->-1->'started_at',
                'finished_at', e.processing_attempts->-1->'finished_at',
                'expires_at', e.processing_attempts->-1->'expires_at',
                'phase', e.processing_attempts->-1->'phase',
                'diagnostic', jsonb_build_object('phase', e.processing_attempts->-1->'diagnostic'->'phase'),
                'dispatch', jsonb_build_object('state', e.processing_attempts->-1->'dispatch'->'state')))
            ELSE '[]'::jsonb END,
        -- Preserve every observation used by the existing estimator, without
        -- copying failed/resume histories, diagnoses, proposals or fragments.
        'ingest_observations', COALESCE((SELECT jsonb_agg(jsonb_build_object(
            'started_at', a->'started_at', 'finished_at', a->'finished_at') ORDER BY n)
            FROM jsonb_array_elements(COALESCE(NULLIF(e.processing_attempts, 'null'::jsonb), '[]'::jsonb))
                WITH ORDINALITY AS attempts(a,n)
            WHERE a->>'state' = 'succeeded' AND a->>'kind' = 'ingest'), '[]'::jsonb)
    ) || CASE WHEN payload ? 'named_reviewers'
              THEN jsonb_build_object('named_reviewers', payload->'named_reviewers')
              ELSE '{}'::jsonb END
    FROM jsonb_to_record(payload) AS e(binary_path TEXT, received_source JSONB,
        processing_configuration JSONB, semantic_replay JSONB,
        quality_processing_runs JSONB, processing_attempts JSONB)
$body$;

CREATE OR REPLACE FUNCTION workflow.refresh_source_selection_summary()
RETURNS TRIGGER LANGUAGE plpgsql AS $body$
BEGIN
    NEW.source_selection_summary := workflow.source_selection_summary_for(NEW.envelope_payload);
    RETURN NEW;
END
$body$;

DROP TRIGGER IF EXISTS refresh_source_selection_summary ON workflow.documents;
CREATE TRIGGER refresh_source_selection_summary
    BEFORE INSERT OR UPDATE OF envelope_payload, source_selection_summary ON workflow.documents
    FOR EACH ROW EXECUTE FUNCTION workflow.refresh_source_selection_summary();
