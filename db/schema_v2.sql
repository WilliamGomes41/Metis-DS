-- V&VN Data Services - Canonical storage/publication layer v2.0
-- PostgreSQL reference schema.
-- Publication is release-based: approved canonical JSON is never mutated merely
-- because a version is published, superseded, or emergency-unpublished.

CREATE TABLE IF NOT EXISTS canonical_object_versions (
    object_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    document_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status = 'approved'),
    source_checksum TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    canonical_json JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (object_id, object_version),
    UNIQUE (object_id, object_version, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_cov_document ON canonical_object_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_cov_content_hash ON canonical_object_versions(content_hash);

CREATE TABLE IF NOT EXISTS publication_releases (
    release_id TEXT PRIMARY KEY,
    release_version TEXT NOT NULL UNIQUE,
    release_owner TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','withdrawn')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMPTZ,
    withdrawn_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS publication_release_items (
    release_id TEXT NOT NULL REFERENCES publication_releases(release_id),
    object_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'publish' CHECK (action IN ('publish','supersede')),
    replaces_object_version TEXT,
    content_hash TEXT NOT NULL,
    PRIMARY KEY (release_id, object_id, object_version),
    FOREIGN KEY (object_id, object_version)
      REFERENCES canonical_object_versions(object_id, object_version)
);

-- Current external publication pointer. This is deliberately separate from the
-- approved canonical object row. Historical state remains in releases + audit.
CREATE TABLE IF NOT EXISTS publication_registry (
    object_id TEXT PRIMARY KEY,
    object_version TEXT NOT NULL,
    release_id TEXT NOT NULL REFERENCES publication_releases(release_id),
    state TEXT NOT NULL CHECK (state IN ('active','emergency_unpublished')),
    published_at TIMESTAMPTZ NOT NULL,
    unpublished_at TIMESTAMPTZ,
    unpublish_reason TEXT,
    FOREIGN KEY (object_id, object_version)
      REFERENCES canonical_object_versions(object_id, object_version)
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('object','release')),
    entity_id TEXT NOT NULL,
    entity_version TEXT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_type, entity_id, event_at);

CREATE OR REPLACE VIEW published_knowledge_objects AS
SELECT
    c.object_id,
    c.object_version,
    c.document_id,
    c.object_type,
    c.content_hash,
    c.canonical_json,
    r.release_id,
    rel.release_version,
    r.published_at
FROM publication_registry r
JOIN canonical_object_versions c
  ON c.object_id = r.object_id AND c.object_version = r.object_version
JOIN publication_releases rel
  ON rel.release_id = r.release_id
WHERE r.state = 'active'
  AND rel.status = 'published';
