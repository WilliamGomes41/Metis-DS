-- Derived access path only. Objects and their existing writers remain authority.
-- Supports bounded incoming relation/context probes without decoding all payloads.
CREATE INDEX IF NOT EXISTS workflow_document_objects_dependencies
    ON workflow.document_objects USING gin (payload jsonb_path_ops);

-- The scoped event read uses the retained snapshot identity in the event.
CREATE INDEX IF NOT EXISTS workflow_review_events_document_history
    ON workflow.review_events ((event_payload->'details'->>'snapshot_id'), event_id);
