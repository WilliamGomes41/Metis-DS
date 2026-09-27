-- Additive, opt-in Microsoft sign-in. Existing account/review IDs are unchanged.
CREATE TABLE IF NOT EXISTS workflow.entra_identities (
    tenant_id UUID NOT NULL,
    object_id UUID NOT NULL,
    account_id TEXT NOT NULL UNIQUE REFERENCES workflow.accounts(account_id),
    blocked BOOLEAN NOT NULL DEFAULT FALSE,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    PRIMARY KEY (tenant_id, object_id),
    CHECK (jsonb_typeof(evidence) = 'array')
);
CREATE TABLE IF NOT EXISTS workflow.entra_sessions (
    token_hash TEXT PRIMARY KEY REFERENCES workflow.sessions(token_hash) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    object_id UUID NOT NULL,
    FOREIGN KEY (tenant_id, object_id) REFERENCES workflow.entra_identities(tenant_id, object_id)
);
-- Temporary handshake state is deliberately excluded from backups.
CREATE TABLE IF NOT EXISTS workflow.entra_flows (
    browser_hash TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entra_flows_expiry ON workflow.entra_flows(expires_at);
