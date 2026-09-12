-- Shared transactional workflow state for the Metis operations console.
--
-- This migration intentionally adds schema only. Existing console runtime behavior
-- remains file-backed until later migrations move data and callers explicitly.
-- Publication authority remains in the existing public canonical/publication tables.

CREATE SCHEMA IF NOT EXISTS workflow;

CREATE TABLE IF NOT EXISTS workflow.accounts (
    account_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    roles TEXT[] NOT NULL,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT workflow_accounts_roles_not_empty CHECK (cardinality(roles) > 0),
    CONSTRAINT workflow_accounts_roles_allowed CHECK (
        roles <@ ARRAY['researcher','reviewer','publisher']::TEXT[]
    )
);

CREATE TABLE IF NOT EXISTS workflow.sessions (
    token_hash TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES workflow.accounts(account_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT workflow_sessions_expiry_after_creation CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_workflow_sessions_account
ON workflow.sessions(account_id);

CREATE INDEX IF NOT EXISTS idx_workflow_sessions_expiry
ON workflow.sessions(expires_at);

CREATE TABLE IF NOT EXISTS workflow.documents (
    snapshot_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    family TEXT NOT NULL,
    class TEXT NOT NULL,
    state TEXT NOT NULL,
    publication_eligibility TEXT NOT NULL,
    content_kind TEXT NOT NULL,
    ingest_kind TEXT NOT NULL,
    source_version TEXT NOT NULL,
    source_date DATE NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    immutable_storage_locator TEXT,
    live_url TEXT NOT NULL DEFAULT '',
    uploader_account_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    replaces_snapshot_id TEXT REFERENCES workflow.documents(snapshot_id),
    object_diff JSONB,
    clinical_rereview_required BOOLEAN NOT NULL DEFAULT FALSE,
    acquired_at TIMESTAMPTZ NOT NULL,
    console_version TEXT NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT workflow_documents_revision_positive CHECK (revision > 0)
);

CREATE INDEX IF NOT EXISTS idx_workflow_documents_document
ON workflow.documents(document_id);

CREATE INDEX IF NOT EXISTS idx_workflow_documents_uploader
ON workflow.documents(uploader_account_id);

CREATE TABLE IF NOT EXISTS workflow.document_reviewers (
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_id, account_id)
);

CREATE TABLE IF NOT EXISTS workflow.document_objects (
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    object_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    payload JSONB NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_id, object_id, object_version),
    CONSTRAINT workflow_document_objects_revision_positive CHECK (revision > 0)
);

CREATE INDEX IF NOT EXISTS idx_workflow_document_objects_current
ON workflow.document_objects(snapshot_id, object_id);

CREATE TABLE IF NOT EXISTS workflow.review_events (
    event_id BIGSERIAL PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    object_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_account_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    occurred_at TIMESTAMPTZ NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::JSONB,
    previous_event_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_workflow_review_events_object
ON workflow.review_events(snapshot_id, object_id, occurred_at);

CREATE TABLE IF NOT EXISTS workflow.publish_authorizations (
    authorization_id BIGSERIAL PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    object_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    canonical_object_hash TEXT NOT NULL,
    confirmed_object_type TEXT NOT NULL,
    reviewer_account_id TEXT NOT NULL REFERENCES workflow.accounts(account_id),
    reviewer_display_name TEXT NOT NULL,
    decision TEXT NOT NULL,
    valid BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        snapshot_id,
        object_id,
        object_version,
        canonical_object_hash,
        reviewer_account_id,
        decision
    )
);

CREATE INDEX IF NOT EXISTS idx_workflow_publish_authorizations_object
ON workflow.publish_authorizations(snapshot_id, object_id, valid);
