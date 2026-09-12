-- Preserve the complete mutable console envelope while keeping queryable workflow columns.
-- Apply after 002_workflow_schema.sql and before enabling PostgreSQL document authority.

ALTER TABLE workflow.documents
ADD COLUMN IF NOT EXISTS envelope_payload JSONB;

-- Deliberately nullable during migration. The runtime cut-over verifies every existing
-- workflow document has a payload before PostgreSQL can become document authority.
