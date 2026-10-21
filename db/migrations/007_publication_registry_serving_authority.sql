-- publication_registry.state is the sole serving-eligibility authority.
-- Release status remains release metadata/history and is not a second serving gate.

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
