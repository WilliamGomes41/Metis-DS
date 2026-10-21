-- Operational browser evidence only; no document/review/publication authority.
CREATE TABLE IF NOT EXISTS workflow.view_checks (
    id text PRIMARY KEY,
    owner_account_id text NOT NULL,
    snapshot_id text NOT NULL,
    request_key text NOT NULL,
    context jsonb NOT NULL,
    context_hash text NOT NULL,
    state text NOT NULL CHECK (state IN ('queued','running','completed','failed','cancelled')),
    attempt integer NOT NULL DEFAULT 0,
    capability_hash text UNIQUE,
    lease_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result jsonb,
    events jsonb NOT NULL DEFAULT '[]',
    UNIQUE(owner_account_id, request_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS view_checks_one_active
    ON workflow.view_checks(owner_account_id, snapshot_id, context_hash)
    WHERE state IN ('queued','running');
CREATE INDEX IF NOT EXISTS view_checks_document
    ON workflow.view_checks(snapshot_id, created_at DESC);
