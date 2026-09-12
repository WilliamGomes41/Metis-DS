-- Publication registry is the sole authority for externally visible publication state.
-- Canonical JSON may retain legacy publication-shaped governance fields for schema
-- compatibility, but those fields are inert and may never claim live publication.
-- Release status remains lifecycle/audit evidence and must never gate serving reads.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM canonical_object_versions
        WHERE COALESCE(canonical_json #>> '{governance,publication_status}', 'unpublished') <> 'unpublished'
           OR NULLIF(canonical_json #>> '{governance,release_owner}', '') IS NOT NULL
           OR NULLIF(canonical_json #>> '{governance,release_date}', '') IS NOT NULL
           OR NULLIF(canonical_json #>> '{governance,superseded_by}', '') IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'canonical JSON contains publication authority; migrate/repair before applying registry-only authority';
    END IF;
END
$$;

ALTER TABLE canonical_object_versions
    DROP CONSTRAINT IF EXISTS canonical_json_no_publication_authority;

ALTER TABLE canonical_object_versions
    ADD CONSTRAINT canonical_json_no_publication_authority CHECK (
        COALESCE(canonical_json #>> '{governance,publication_status}', 'unpublished') = 'unpublished'
        AND NULLIF(canonical_json #>> '{governance,release_owner}', '') IS NULL
        AND NULLIF(canonical_json #>> '{governance,release_date}', '') IS NULL
        AND NULLIF(canonical_json #>> '{governance,superseded_by}', '') IS NULL
    );

-- An active pointer may only be created for a release that completed the publish
-- transaction. This is an integrity invariant; release.status is not a serving gate.
CREATE OR REPLACE FUNCTION enforce_active_registry_release_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_status TEXT;
BEGIN
    IF NEW.state = 'active' THEN
        SELECT status
          INTO release_status
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

-- A release cannot be marked withdrawn while it still owns an active registry
-- pointer. Unpublish/supersede the registry first, then close the historical release.
CREATE OR REPLACE FUNCTION prevent_release_with_active_registry_from_closing()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = 'published'
       AND NEW.status IS DISTINCT FROM 'published'
       AND EXISTS (
           SELECT 1
           FROM publication_registry
           WHERE release_id = OLD.release_id
             AND state = 'active'
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

-- Serving view: registry.state is intentionally the only publication-state filter.
-- The release join supplies immutable release metadata only.
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
WHERE r.state = 'active';

COMMENT ON TABLE publication_registry IS
    'Sole authority for whether an exact canonical object version is externally published.';
COMMENT ON COLUMN publication_registry.state IS
    'Serving state. active means externally published; emergency_unpublished means not externally published.';
COMMENT ON COLUMN publication_releases.status IS
    'Release lifecycle/audit evidence. It is not an independent serving authority.';
