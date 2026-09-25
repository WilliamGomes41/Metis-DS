-- Durable runtime API access authority for Product API consumers.
-- Publication eligibility remains exclusively owned by publication_registry.

CREATE SCHEMA IF NOT EXISTS api_access;

CREATE TABLE IF NOT EXISTS api_access.tenants (
    tenant_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'SUSPENDED', 'CLOSED')),
    content_scope TEXT NOT NULL CHECK (content_scope IN ('ALL_PUBLISHED', 'RESOURCE_SET')),
    requests_per_minute INTEGER NOT NULL CHECK (requests_per_minute > 0),
    max_top_k INTEGER NOT NULL CHECK (max_top_k > 0),
    policy_version BIGINT NOT NULL DEFAULT 1 CHECK (policy_version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_access.tenant_scopes (
    tenant_id TEXT NOT NULL REFERENCES api_access.tenants(tenant_id) ON DELETE RESTRICT,
    scope TEXT NOT NULL,
    PRIMARY KEY (tenant_id, scope)
);

CREATE TABLE IF NOT EXISTS api_access.tenant_resources (
    tenant_id TEXT NOT NULL REFERENCES api_access.tenants(tenant_id) ON DELETE RESTRICT,
    resource_type TEXT NOT NULL CHECK (resource_type = 'DOCUMENT'),
    resource_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, resource_type, resource_id)
);

CREATE TABLE IF NOT EXISTS api_access.applications (
    application_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES api_access.tenants(tenant_id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    environment TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'SUSPENDED', 'RETIRED')),
    content_scope TEXT NOT NULL CHECK (content_scope IN ('ALL_PUBLISHED', 'RESOURCE_SET')),
    requests_per_minute INTEGER NOT NULL CHECK (requests_per_minute > 0),
    max_top_k INTEGER NOT NULL CHECK (max_top_k > 0),
    policy_version BIGINT NOT NULL DEFAULT 1 CHECK (policy_version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_access_applications_tenant
ON api_access.applications(tenant_id);

CREATE TABLE IF NOT EXISTS api_access.application_scopes (
    application_id TEXT NOT NULL REFERENCES api_access.applications(application_id) ON DELETE RESTRICT,
    scope TEXT NOT NULL,
    PRIMARY KEY (application_id, scope)
);

CREATE TABLE IF NOT EXISTS api_access.application_resources (
    application_id TEXT NOT NULL REFERENCES api_access.applications(application_id) ON DELETE RESTRICT,
    resource_type TEXT NOT NULL CHECK (resource_type = 'DOCUMENT'),
    resource_id TEXT NOT NULL,
    PRIMARY KEY (application_id, resource_type, resource_id)
);

CREATE TABLE IF NOT EXISTS api_access.credentials (
    credential_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES api_access.applications(application_id) ON DELETE RESTRICT,
    secret_sha256 CHAR(64) NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'REVOKED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_access_credentials_application
ON api_access.credentials(application_id);

CREATE TABLE IF NOT EXISTS api_access.audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    tenant_id TEXT,
    application_id TEXT,
    credential_id TEXT,
    event_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_api_access_audit_tenant_event_at
ON api_access.audit_events(tenant_id, event_at DESC);
