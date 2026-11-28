-- Issue 1191. A tree seal binds one ready graph input to the existing manifest.
-- Historical seals remain immutable. Currentness still depends on the live source and generation.
CREATE OR REPLACE FUNCTION workflow.guard_annotation_seal_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE basis workflow.annotation_sets%ROWTYPE; manifest JSONB; context JSONB;
BEGIN
    SELECT * INTO basis FROM workflow.annotation_sets WHERE snapshot_id=NEW.snapshot_id FOR UPDATE;
    SELECT workflow.annotation_materialization_context(d) INTO context FROM workflow.documents d WHERE snapshot_id=NEW.snapshot_id;
    WITH versions AS (
        SELECT DISTINCT ON (v.annotation_id) v.*,
            min((c.result->>'generation')::bigint) OVER (PARTITION BY v.annotation_id) AS position
        FROM workflow.annotation_commands c JOIN workflow.annotation_versions v
          ON v.snapshot_id=c.snapshot_id AND v.annotation_id=c.result->>'annotation_id'
          AND v.revision=(c.result->>'revision')::bigint
        WHERE c.snapshot_id=NEW.snapshot_id AND (c.result->>'generation')::bigint<=NEW.generation
        ORDER BY v.annotation_id,v.revision DESC
    ) SELECT COALESCE(jsonb_agg(jsonb_build_object('annotation_id',annotation_id,'revision',revision,
           'payload_hash',payload_hash) ORDER BY position),'[]'::jsonb) INTO manifest FROM versions;
    IF NEW.payload->>'version' IS DISTINCT FROM 'human-annotation-v1'
        OR NEW.payload#>>'{context,class}' IS DISTINCT FROM context->>'class'
        OR (NEW.payload->>'route' IS NOT DISTINCT FROM 'decision-tree-annotation-v1')
           IS DISTINCT FROM (context->>'class' = 'beslisboom')
        OR (context->>'class' = 'beslisboom' AND (
            jsonb_array_length(manifest) <> 1
            OR NOT EXISTS (
                SELECT 1 FROM workflow.annotation_versions v
                WHERE v.snapshot_id=NEW.snapshot_id AND v.annotation_id=manifest->0->>'annotation_id'
                  AND v.revision=(manifest->0->>'revision')::bigint AND v.status='ready'
                  AND v.payload->>'contract' = 'decision-tree-annotation-input-v1'
            )
        ))
        OR NEW.generation>basis.generation OR NEW.extraction_hash<>basis.extraction_hash
        OR NOT ((NEW.payload->'source_identity') <@ (NEW.payload->'context'))
        OR NEW.payload#>>'{context,working_revision_id}' IS DISTINCT FROM basis.working_revision_id
        OR NEW.payload->'source_identity' IS DISTINCT FROM basis.source_identity
        OR NEW.payload->>'working_revision_id' IS DISTINCT FROM basis.working_revision_id
        OR NEW.payload->>'normalization' IS DISTINCT FROM basis.normalization
        OR (NOT (NEW.payload ? 'revision_basis') AND NEW.payload->>'objects_revision' IS DISTINCT FROM basis.objects_revision)
        OR NEW.payload->'entries' IS DISTINCT FROM manifest
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(manifest) e JOIN workflow.annotation_versions v
            ON v.snapshot_id=NEW.snapshot_id AND v.annotation_id=e->>'annotation_id'
              AND v.revision=(e->>'revision')::bigint
            WHERE v.status<>'withdrawn' AND NOT(v.payload ? 'disposition')
            GROUP BY (SELECT jsonb_agg(jsonb_build_array(a->'block_id',a->'start',a->'end') ORDER BY position)
              FROM jsonb_array_elements(v.payload->'ranges') WITH ORDINALITY AS r(a,position) WHERE a->>'role'='core')
            HAVING count(*)>1)
        OR NEW.payload->>'overview_hash' IS DISTINCT FROM NEW.overview_hash
        OR NEW.payload->>'snapshot_id' IS DISTINCT FROM NEW.snapshot_id
        OR NEW.payload->>'extraction_hash' IS DISTINCT FROM NEW.extraction_hash
        OR NEW.payload->>'generation' IS DISTINCT FROM NEW.generation::text
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(manifest) e JOIN workflow.annotation_versions v
            ON v.snapshot_id=NEW.snapshot_id AND v.annotation_id=e->>'annotation_id'
              AND v.revision=(e->>'revision')::bigint WHERE v.status NOT IN ('ready','withdrawn')) THEN
        RAISE EXCEPTION 'annotation_seal_input_changed';
    END IF;
    RETURN NEW;
END
$body$;

CREATE OR REPLACE FUNCTION workflow.annotation_seal_current(sid TEXT, identity TEXT)
RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY DEFINER SET search_path=pg_catalog AS $body$
    SELECT EXISTS(SELECT 1 FROM workflow.annotation_sets a JOIN workflow.annotation_seals s ON s.seal_id=a.current_seal_id
        JOIN workflow.documents d ON d.snapshot_id=a.snapshot_id
        WHERE a.snapshot_id=sid AND s.seal_id=identity AND s.snapshot_id=sid
          AND (s.payload->>'route' IS NOT DISTINCT FROM 'decision-tree-annotation-v1') = (d.class='beslisboom')
          AND a.generation=s.generation AND a.extraction_hash=s.extraction_hash
          AND s.payload->'context'=workflow.annotation_materialization_context(d))
$body$;

-- Operational storage keeps human proof as producer and pins the graph to that same seal.
CREATE OR REPLACE FUNCTION workflow.guard_document_input_variant() RETURNS TRIGGER LANGUAGE plpgsql AS $body$
DECLARE expected TEXT;
BEGIN
    expected:=CASE WHEN COALESCE(NEW.refs->'human'<>'null'::jsonb,false) THEN 'human' WHEN COALESCE(NEW.refs->'replay'<>'null'::jsonb,false) THEN 'semantic'
        WHEN COALESCE(NEW.refs->'tree'<>'null'::jsonb,false) OR COALESCE(NEW.metadata->'decision_graph' NOT IN ('null'::jsonb,'{}'::jsonb,'[]'::jsonb),false)
            THEN 'tree' ELSE 'absent' END;
    IF COALESCE(NEW.refs->'tree_route','false'::jsonb) IS DISTINCT FROM COALESCE((SELECT header->'tree_route' FROM workflow.processing_archive_inputs WHERE archive_id=NEW.refs#>>'{tree,archive_id}'),'false'::jsonb) THEN
        RAISE EXCEPTION 'document_inputs_tree_route_changed';
    END IF;
    IF TG_OP='UPDATE' AND OLD.refs->>'formation_variant'='human' AND expected<>'human' THEN
        RAISE EXCEPTION 'document_inputs_human_binding_changed';
    END IF;
    IF expected='human' AND EXISTS(SELECT 1 FROM workflow.documents d WHERE d.snapshot_id=NEW.snapshot_id
        AND d.formation_evidence_id IS NOT NULL AND d.formation_evidence_id IS DISTINCT FROM NEW.refs#>>'{human,proof_id}') THEN
        RAISE EXCEPTION 'document_inputs_human_binding_changed';
    END IF;
    IF expected='human' AND (NEW.refs->'replay' IS DISTINCT FROM 'null'::jsonb
        OR NOT EXISTS(SELECT 1 FROM workflow.formation_evidence_roots p
          WHERE p.proof_id=NEW.refs#>>'{human,proof_id}' AND p.snapshot_id=NEW.snapshot_id AND p.sealed
            AND p.header->>'layout'='2' AND NEW.refs#>>'{human,layout}'='2'
            AND p.extraction_hash=NEW.refs->>'extraction_hash'
            AND EXISTS (
                SELECT 1 FROM workflow.annotation_seals s
                WHERE s.seal_id=p.annotation_seal_id AND s.snapshot_id=p.snapshot_id
                  AND CASE WHEN s.payload->>'route'='decision-tree-annotation-v1' THEN EXISTS (
                      SELECT 1 FROM workflow.processing_archives a
                      WHERE a.archive_id=NEW.refs#>>'{tree,archive_id}' AND a.snapshot_id=p.snapshot_id
                        AND a.kind='tree_formation'
                        AND a.payload_text::jsonb#>>'{decision_tree_formation,route}'='decision-tree-annotation-v1'
                        AND a.payload_text::jsonb#>>'{decision_tree_formation,annotation_seal_id}'=s.seal_id
                        AND a.payload_text::jsonb#>'{decision_tree_formation,model}'='null'::jsonb
                        AND a.payload_text::jsonb->'decision_graph_evidence'=s.payload#>'{tree_source,inventory}'
                  ) ELSE NOT COALESCE(NEW.refs->'tree'<>'null'::jsonb,false) END
            ))) THEN
        RAISE EXCEPTION 'document_inputs_human_binding_changed';
    END IF;
    IF NEW.refs->>'formation_variant' IS DISTINCT FROM expected THEN
        RAISE EXCEPTION 'document_inputs_formation_variant_changed';
    END IF;
    RETURN NEW;
END
$body$;
