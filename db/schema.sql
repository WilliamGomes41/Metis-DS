-- V&VN Data Service - Step 5 storage schema v0.1
-- PostgreSQL-compatible baseline. Embedding columns intentionally omitted until validation is complete.

CREATE TABLE IF NOT EXISTS knowledge_documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    publisher TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    version TEXT,
    publication_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_objects (
    object_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES knowledge_documents(document_id),
    parent_object_id TEXT REFERENCES knowledge_objects(object_id),
    object_type TEXT NOT NULL,
    section_path JSONB NOT NULL DEFAULT '[]'::jsonb,
    heading TEXT,
    sequence_no INTEGER,
    raw_text TEXT NOT NULL,
    clean_text TEXT NOT NULL,
    context_text TEXT,
    target_group JSONB NOT NULL DEFAULT '[]'::jsonb,
    care_setting JSONB NOT NULL DEFAULT '[]'::jsonb,
    topic JSONB NOT NULL DEFAULT '[]'::jsonb,
    logic JSONB,
    source_page INTEGER,
    validation_status TEXT NOT NULL,
    validated_by TEXT,
    validation_date DATE,
    valid_from DATE,
    valid_until DATE,
    content_hash TEXT,
    parser_version TEXT,
    chunk_method TEXT,
    source_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_approved_has_validator CHECK (
        validation_status <> 'approved'
        OR (validated_by IS NOT NULL AND validation_date IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_knowledge_objects_document ON knowledge_objects(document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_objects_type ON knowledge_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_objects_status ON knowledge_objects(validation_status);
CREATE INDEX IF NOT EXISTS idx_knowledge_objects_content_hash ON knowledge_objects(content_hash);

-- Retrieval must only expose approved, currently valid objects.
CREATE OR REPLACE VIEW approved_knowledge_objects AS
SELECT *
FROM knowledge_objects
WHERE validation_status = 'approved'
  AND (valid_from IS NULL OR valid_from <= CURRENT_DATE)
  AND (valid_until IS NULL OR valid_until >= CURRENT_DATE);
