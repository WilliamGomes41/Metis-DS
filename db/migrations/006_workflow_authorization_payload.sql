-- Preserve the complete per-object authorization tuple used by the review
-- workflow. Relational columns remain indexes and are validated against this
-- exact payload by the application.

ALTER TABLE workflow.publish_authorizations
ADD COLUMN IF NOT EXISTS authorization_payload JSONB;
