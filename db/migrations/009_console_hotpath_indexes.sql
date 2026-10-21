-- Read-path indexes for authenticated Documenten/Review hot paths.
-- No authority moves: both indexes derive from existing authoritative columns.
-- The workflow migration runner is also used by workflow-only tests/environments,
-- so the canonical index is installed only when canonical audit_events exists.

CREATE INDEX IF NOT EXISTS workflow_document_objects_snapshot_validation_status_idx
    ON workflow.document_objects (
        snapshot_id,
        (payload->'governance'->>'validation_status')
    );

DO $$
BEGIN
    IF to_regclass('audit_events') IS NOT NULL THEN
        EXECUTE $index$
            CREATE INDEX IF NOT EXISTS audit_events_release_snapshot_idx
                ON audit_events ((details->>'snapshot_id'))
                WHERE entity_type='release'
                  AND event_type='release_published'
        $index$;
    END IF;
END
$$;
