-- Durable syntactic Onderwerp identity for workflow documents.
--
-- EXPAND only: old application versions keep using family. topic_id remains
-- nullable until the explicit backfill/cutover has been proven. The Topic
-- registry becomes the unique identity authority for the new runtime; family
-- remains a compatibility/display projection in this migration.

CREATE TABLE IF NOT EXISTS workflow.topics (
    topic_id TEXT PRIMARY KEY,
    identity_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT workflow_topics_identity_key_not_blank CHECK (btrim(identity_key) <> ''),
    CONSTRAINT workflow_topics_display_name_not_blank CHECK (btrim(display_name) <> ''),
    CONSTRAINT workflow_topics_identity_key_unique UNIQUE (identity_key)
);

ALTER TABLE workflow.documents
ADD COLUMN IF NOT EXISTS topic_id TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'workflow_documents_topic_id_fkey'
          AND conrelid = 'workflow.documents'::regclass
    ) THEN
        ALTER TABLE workflow.documents
        ADD CONSTRAINT workflow_documents_topic_id_fkey
        FOREIGN KEY (topic_id)
        REFERENCES workflow.topics(topic_id);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_workflow_documents_topic
ON workflow.documents(topic_id);
