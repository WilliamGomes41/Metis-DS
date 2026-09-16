-- Explicit lifecycle identity for mutable workflow documents.
--
-- `document_id` remains a source-derived technical identifier and MUST NOT be
-- used as the identity of the logical document across source versions.
-- `snapshot_id` remains the SourceSnapshot identity.
-- This migration adds one stable LogicalDocument identity and one explicit
-- WorkingRevision identity/number per currently materialized snapshot.

ALTER TABLE workflow.documents
ADD COLUMN IF NOT EXISTS logical_document_id TEXT;

ALTER TABLE workflow.documents
ADD COLUMN IF NOT EXISTS working_revision_id TEXT;

ALTER TABLE workflow.documents
ADD COLUMN IF NOT EXISTS working_revision_number INTEGER;

-- Existing predecessor chains determine LogicalDocument identity. The root
-- snapshot is immutable, so the derived id is deterministic across restart,
-- backup/restore and repeated migration runs.
WITH RECURSIVE lineage AS (
    SELECT
        d.snapshot_id,
        d.replaces_snapshot_id,
        d.snapshot_id AS root_snapshot_id,
        ARRAY[d.snapshot_id]::TEXT[] AS path
    FROM workflow.documents AS d
    WHERE d.replaces_snapshot_id IS NULL

    UNION ALL

    SELECT
        child.snapshot_id,
        child.replaces_snapshot_id,
        parent.root_snapshot_id,
        parent.path || child.snapshot_id
    FROM workflow.documents AS child
    JOIN lineage AS parent
      ON child.replaces_snapshot_id = parent.snapshot_id
    WHERE NOT child.snapshot_id = ANY(parent.path)
)
UPDATE workflow.documents AS d
SET
    logical_document_id = COALESCE(d.logical_document_id, 'ldoc-' || lineage.root_snapshot_id),
    working_revision_id = COALESCE(d.working_revision_id, 'work-' || d.snapshot_id)
FROM lineage
WHERE d.snapshot_id = lineage.snapshot_id
  AND (d.logical_document_id IS NULL OR d.working_revision_id IS NULL);

-- Number current WorkingRevisions deterministically within each logical
-- document. Do not infer the number from source_version: these are different
-- version dimensions.
WITH numbered AS (
    SELECT
        snapshot_id,
        row_number() OVER (
            PARTITION BY logical_document_id
            ORDER BY acquired_at, snapshot_id
        )::INTEGER AS revision_number
    FROM workflow.documents
    WHERE logical_document_id IS NOT NULL
)
UPDATE workflow.documents AS d
SET working_revision_number = numbered.revision_number
FROM numbered
WHERE d.snapshot_id = numbered.snapshot_id
  AND d.working_revision_number IS NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM workflow.documents
        WHERE logical_document_id IS NULL
           OR working_revision_id IS NULL
           OR working_revision_number IS NULL
    ) THEN
        RAISE EXCEPTION 'lifecycle_identity_backfill_unresolved';
    END IF;
END
$$;

ALTER TABLE workflow.documents
ALTER COLUMN logical_document_id SET NOT NULL;

ALTER TABLE workflow.documents
ALTER COLUMN working_revision_id SET NOT NULL;

ALTER TABLE workflow.documents
ALTER COLUMN working_revision_number SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'workflow_documents_working_revision_id_unique'
          AND conrelid = 'workflow.documents'::regclass
    ) THEN
        ALTER TABLE workflow.documents
        ADD CONSTRAINT workflow_documents_working_revision_id_unique
        UNIQUE (working_revision_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'workflow_documents_logical_revision_unique'
          AND conrelid = 'workflow.documents'::regclass
    ) THEN
        ALTER TABLE workflow.documents
        ADD CONSTRAINT workflow_documents_logical_revision_unique
        UNIQUE (logical_document_id, working_revision_number);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'workflow_documents_working_revision_positive'
          AND conrelid = 'workflow.documents'::regclass
    ) THEN
        ALTER TABLE workflow.documents
        ADD CONSTRAINT workflow_documents_working_revision_positive
        CHECK (working_revision_number > 0);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_workflow_documents_logical_document
ON workflow.documents(logical_document_id);

CREATE OR REPLACE FUNCTION workflow.assign_lifecycle_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    predecessor_logical_document_id TEXT;
    next_revision_number INTEGER;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.logical_document_id IS DISTINCT FROM OLD.logical_document_id
           OR NEW.working_revision_id IS DISTINCT FROM OLD.working_revision_id
           OR NEW.working_revision_number IS DISTINCT FROM OLD.working_revision_number
           OR NEW.replaces_snapshot_id IS DISTINCT FROM OLD.replaces_snapshot_id THEN
            RAISE EXCEPTION 'lifecycle_identity_immutable';
        END IF;
    ELSE
        IF NEW.ingest_kind = 'new_version' THEN
            IF NEW.replaces_snapshot_id IS NULL THEN
                RAISE EXCEPTION 'lifecycle_identity_predecessor_required';
            END IF;

            SELECT logical_document_id
              INTO predecessor_logical_document_id
              FROM workflow.documents
             WHERE snapshot_id = NEW.replaces_snapshot_id;

            IF predecessor_logical_document_id IS NULL THEN
                RAISE EXCEPTION 'lifecycle_identity_predecessor_missing';
            END IF;

            IF NEW.logical_document_id IS NOT NULL
               AND NEW.logical_document_id <> predecessor_logical_document_id THEN
                RAISE EXCEPTION 'lifecycle_identity_logical_document_mismatch';
            END IF;

            NEW.logical_document_id := predecessor_logical_document_id;
        ELSE
            IF NEW.logical_document_id IS NULL THEN
                NEW.logical_document_id := 'ldoc-' || NEW.snapshot_id;
            END IF;
        END IF;

        -- Serialize revision allocation per LogicalDocument. This keeps two
        -- concurrent successor captures from receiving the same work number.
        PERFORM pg_advisory_xact_lock(hashtextextended(NEW.logical_document_id, 0));

        SELECT COALESCE(MAX(working_revision_number), 0) + 1
          INTO next_revision_number
          FROM workflow.documents
         WHERE logical_document_id = NEW.logical_document_id;

        IF NEW.working_revision_number IS NOT NULL
           AND NEW.working_revision_number <> next_revision_number THEN
            RAISE EXCEPTION 'lifecycle_identity_working_revision_number_mismatch';
        END IF;

        NEW.working_revision_number := next_revision_number;

        IF NEW.working_revision_id IS NULL THEN
            NEW.working_revision_id := 'work-' || NEW.snapshot_id;
        END IF;
    END IF;

    -- envelope_payload is a read projection, not a second identity authority.
    -- Enrich it only when a complete envelope already exists; migration-stage
    -- rows with NULL payload remain migration-stage rows.
    IF NEW.envelope_payload IS NOT NULL THEN
        NEW.envelope_payload := NEW.envelope_payload || jsonb_build_object(
            'logical_document_id', NEW.logical_document_id,
            'source_snapshot_id', NEW.snapshot_id,
            'source_version', NEW.source_version,
            'working_revision_id', NEW.working_revision_id,
            'working_revision_number', NEW.working_revision_number
        );
    END IF;

    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_workflow_documents_lifecycle_identity
ON workflow.documents;

CREATE TRIGGER trg_workflow_documents_lifecycle_identity
BEFORE INSERT OR UPDATE ON workflow.documents
FOR EACH ROW
EXECUTE FUNCTION workflow.assign_lifecycle_identity();

-- Backfill the projection after identities are durable. Do not manufacture a
-- partial envelope for migration-stage rows that have not completed cut-over.
UPDATE workflow.documents
SET envelope_payload = envelope_payload || jsonb_build_object(
    'logical_document_id', logical_document_id,
    'source_snapshot_id', snapshot_id,
    'source_version', source_version,
    'working_revision_id', working_revision_id,
    'working_revision_number', working_revision_number
)
WHERE envelope_payload IS NOT NULL;
