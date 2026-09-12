-- Preserve exact review-ledger events and publication authorization ordering.
-- Apply after 002_workflow_schema.sql (and 003 for the full document cut-over).
-- Historical review events may have synthetic actors or no reliable snapshot/account id;
-- the original hash-chained payload therefore remains the authority.

ALTER TABLE workflow.review_events
ALTER COLUMN snapshot_id DROP NOT NULL;

ALTER TABLE workflow.review_events
ALTER COLUMN actor_account_id DROP NOT NULL;

ALTER TABLE workflow.review_events
ADD COLUMN IF NOT EXISTS actor_text TEXT;

ALTER TABLE workflow.review_events
ADD COLUMN IF NOT EXISTS event_payload JSONB;

ALTER TABLE workflow.publish_authorizations
ADD COLUMN IF NOT EXISTS position INTEGER;

CREATE INDEX IF NOT EXISTS idx_workflow_review_events_hash_chain
ON workflow.review_events(event_id, event_hash);

CREATE INDEX IF NOT EXISTS idx_workflow_publish_authorizations_position
ON workflow.publish_authorizations(snapshot_id, position);
