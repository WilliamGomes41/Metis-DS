-- Read-path indexes for authenticated Documenten/Review hot paths.
-- No authority moves: both indexes derive from existing authoritative columns.

CREATE INDEX IF NOT EXISTS workflow_document_objects_snapshot_validation_status_idx
    ON workflow.document_objects (
        snapshot_id,
        (payload->'governance'->>'validation_status')
    );

CREATE INDEX IF NOT EXISTS audit_events_release_snapshot_idx
    ON audit_events ((details->>'snapshot_id'))
    WHERE entity_type='release'
      AND event_type='release_published';
