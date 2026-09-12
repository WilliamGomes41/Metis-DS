-- V&VN Data Services - Canonical storage/publication layer v2.0
-- PostgreSQL reference schema.
-- Publication state is registry-based. Canonical knowledge never carries live
-- publication lifecycle state.

CREATE TABLE IF NOT EXISTS canonical_object_versions (
    object_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    document_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    canonical_schema_version TEXT NOT NULL DEFAULT '1.3',
    validation_status TEXT NOT NULL CHECK (validation_status = 'approved'),
    source_checksum TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    canonical_json JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (object_id, object_version),
    UNIQUE (object_id, object_version, content_hash),
    CONSTRAINT canonical_json_no_publication_authority CHECK (
        NOT COALESCE(
            (canonical_json -> 'governance') ?| ARRAY[
                'publication_status',
                'release_owner',
                'release_date',
                'superseded_by'
            ],
            false
        )
    )
);

CREATE OR REPLACE FUNCTION strip_publication_governance_from_canonical_json()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    governance_json JSONB;
BEGIN
    governance_json := COALESCE(NEW.canonical_json -> 'governance', '{}'::jsonb);
    governance_json := governance_json
        - 'publication_status'
        - 'release_owner'
        - 'release_date'
        - 'superseded_by';

    NEW.canonical_json := jsonb_set(
        NEW.canonical_json,
        '{governance}',
        governance_json,
        true
    );
    NEW.canonical_schema_version := '1.3';
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_strip_publication_governance ON canonical_object_versions;
CREATE TRIGGER trg_strip_publication_governance
BEFORE INSERT OR UPDATE OF canonical_json
ON canonical_object_versions
FOR EACH ROW
EXECUTE FUNCTION strip_publication_governance_from_canonical_json();

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

-- Sole current external publication authority. Release rows are lifecycle/audit
-- evidence only and canonical JSON contains no publication state.
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

CREATE OR REPLACE FUNCTION enforce_active_registry_release_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_status TEXT;
BEGIN
    IF NEW.state = 'active' THEN
        SELECT status INTO release_status
        FROM publication_releases
        WHERE release_id = NEW.release_id;
        IF release_status IS DISTINCT FROM 'published' THEN
            RAISE EXCEPTION 'active publication_registry row requires a published release: %', NEW.release_id;
        END IF;
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_active_registry_release_integrity ON publication_registry;
CREATE TRIGGER trg_active_registry_release_integrity
BEFORE INSERT OR UPDATE OF release_id, state
ON publication_registry
FOR EACH ROW
EXECUTE FUNCTION enforce_active_registry_release_integrity();

CREATE OR REPLACE FUNCTION prevent_release_with_active_registry_from_closing()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = 'published'
       AND NEW.status IS DISTINCT FROM 'published'
       AND EXISTS (
           SELECT 1 FROM publication_registry
           WHERE release_id = OLD.release_id AND state = 'active'
       ) THEN
        RAISE EXCEPTION 'publication_registry must be deactivated before release % can leave published state', OLD.release_id;
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_release_requires_registry_deactivation ON publication_releases;
CREATE TRIGGER trg_release_requires_registry_deactivation
BEFORE UPDATE OF status
ON publication_releases
FOR EACH ROW
EXECUTE FUNCTION prevent_release_with_active_registry_from_closing();

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

-- Serving is intentionally gated only by publication_registry.state. The release join
-- supplies immutable release metadata; release status cannot independently hide data.
CREATE OR REPLACE VIEW published_knowledge_objects AS
SELECT
    c.object_id,
    c.object_version,
    c.document_id,
    c.object_type,
    c.canonical_schema_version,
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
WHERE r.state = 'active';

COMMENT ON TABLE canonical_object_versions IS
    'Immutable canonical knowledge versions. Publication lifecycle state is forbidden inside canonical_json.';
COMMENT ON COLUMN canonical_object_versions.canonical_schema_version IS
    'Durable canonical knowledge contract version. Version 1.3 removes publication lifecycle fields from governance.';
COMMENT ON TABLE publication_registry IS
    'Sole authority for whether an exact canonical object version is externally published.';
COMMENT ON COLUMN publication_registry.state IS
    'Serving state. active means externally published; emergency_unpublished means not externally published.';
COMMENT ON COLUMN publication_releases.status IS
    'Release lifecycle/audit evidence. It is not an independent serving authority.';
