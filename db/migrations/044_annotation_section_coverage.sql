CREATE TABLE IF NOT EXISTS workflow.annotation_section_coverage (
    snapshot_id TEXT PRIMARY KEY REFERENCES workflow.annotation_structure_confirmations(snapshot_id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK (scope IN ('selection', 'full')),
    confirmations JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(confirmations) = 'object'),
    updated_by TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
