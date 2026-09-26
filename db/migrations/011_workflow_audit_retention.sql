-- Offline additive cutover: deploy matching readers before retention is used.
-- Existing records remain LIVE. Non-LIVE payloads contain compact references.
ALTER TABLE workflow.audit_records
    ADD COLUMN IF NOT EXISTS retention_state TEXT NOT NULL DEFAULT 'LIVE'
    CONSTRAINT workflow_audit_retention_state_check
    CHECK (retention_state IN ('LIVE', 'ARCHIVED', 'PURGING'));
