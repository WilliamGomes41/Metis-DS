-- Remove the remaining mutable /home/data authority from the shared workflow mode.
-- Apply after 004_workflow_review_authority.sql and before enabling the final
-- PostgreSQL workflow cut-over. Publication authority stays in the canonical
-- publication tables; these tables only cover Audit workspace state.

CREATE TABLE IF NOT EXISTS workflow.audit_records (
    audit_id TEXT PRIMARY KEY,
    audit_type TEXT NOT NULL,
    title TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    CONSTRAINT workflow_audit_records_type_not_empty CHECK (length(audit_type) > 0),
    CONSTRAINT workflow_audit_records_title_not_empty CHECK (length(title) > 0)
);

CREATE INDEX IF NOT EXISTS idx_workflow_audit_records_created
ON workflow.audit_records(created_at DESC, audit_id);

CREATE TABLE IF NOT EXISTS workflow.audit_secrets (
    secret_name TEXT PRIMARY KEY,
    secret_payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT workflow_audit_secrets_name_not_empty CHECK (length(secret_name) > 0)
);
