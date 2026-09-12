-- Preserve the complete mutable console envelope and source/review object order.
-- Apply after 002_workflow_schema.sql and before enabling PostgreSQL document authority.

ALTER TABLE workflow.documents
ADD COLUMN IF NOT EXISTS envelope_payload JSONB;

ALTER TABLE workflow.document_objects
ADD COLUMN IF NOT EXISTS position INTEGER;

-- Deliberately nullable during migration. The explicit cut-over preparation verifies
-- every existing workflow document has a full envelope and gives every object its
-- original JSONL position before PostgreSQL can become runtime authority.
