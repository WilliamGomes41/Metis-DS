"""Read the annotation build commands and the results they actually produced."""

from datetime import datetime, timezone

from src.operations_console_v1 import ConsoleError
from src.vorming.human_annotation_v1 import authorize
from src.workflows.workflow_transaction_v1 import workflow_read_transaction


def _quality_candidates(con, snapshot_id, attempt):
    # In operational storage, only linked archives are activated results.
    # Read only the candidate identifiers, never their source text or replay.
    row = con.execute("""
        WITH runs AS (
            SELECT a.payload_text::jsonb AS run
              FROM workflow.document_processing_records r
              JOIN workflow.processing_archives a
                ON a.archive_id = r.archive_id AND a.snapshot_id = r.snapshot_id
             WHERE r.snapshot_id = %(snapshot)s AND r.kind = 'quality_processing_run'
            UNION ALL
            SELECT run
              FROM workflow.documents d
              CROSS JOIN LATERAL jsonb_array_elements(
                  COALESCE(NULLIF(d.envelope_payload->'quality_processing_runs', 'null'), '[]')
              ) AS legacy(run)
             WHERE d.snapshot_id = %(snapshot)s AND d.document_storage_version = 0
        )
        SELECT ARRAY(
            SELECT candidate->>'object_id'
              FROM jsonb_array_elements(run->'candidates') AS items(candidate)
             WHERE candidate->>'structural' IS DISTINCT FROM 'true'
               AND candidate->'origin'->>'route' IS DISTINCT FROM 'remainder'
        ) AS object_ids
          FROM runs
         WHERE run->>'attempt_id' = %(attempt)s
           AND run->>'annotation_seal_id' = %(seal)s
           AND run->>'outcome' = 'succeeded'
           AND jsonb_typeof(run->'candidates') = 'array'
         LIMIT 1
        """, {'snapshot': snapshot_id, 'attempt': attempt['attempt_id'], 'seal': attempt['seal_id']}).fetchone()
    return None if row is None else set(row['object_ids'])


def _review_count(console, actor, snapshot_id, object_ids):
    from src.review.review_passage_read_v1 import read_review_navigation
    from src.review.review_duty_v1 import review_duty_counts
    from src.review.beslisboom_path_v1 import review_path_for_klasse

    try:
        inputs = read_review_navigation(console, actor, snapshot_id)
    except ConsoleError as error:
        if error.code in {'reviewer_not_named_on_snapshot', 'workflow_document_unavailable',
                          'workflow_review_unavailable'}:
            return None
        raise
    return review_duty_counts(
        (obj for obj in inputs.objects if obj['object_id'] in object_ids),
        review_path=review_path_for_klasse(inputs.envelope['class']),
        bindings=inputs.bindings, fragments=inputs.fragments,
    )['review_duties']


def status_overview(console, actor, snapshot_id, attempt_id, *, history):
    envelope = console._envelope(snapshot_id)
    authorize(console, actor['account_id'], envelope)
    store = console.workflow_document_store
    with workflow_read_transaction(store) as con:
        rows = con.execute("""
            SELECT a.attempt_id, a.started_at, a.payload->>'finished_at' AS finished_at,
                   a.payload->>'state' AS state, a.payload->>'error_code' AS error_code,
                   a.payload->'dispatch'->>'state' AS dispatch_state,
                   a.payload->'dispatch'->>'claimed_at' AS claimed_at,
                   s.seal_id, s.generation, s.payload ? 'document_check' AS document_check,
                   heads.generation = s.generation
                       AND heads.working_revision_id = s.payload->>'working_revision_id' AS current_generation
              FROM workflow.annotation_build_commands c
              JOIN workflow.annotation_sets heads ON heads.snapshot_id = c.snapshot_id
              JOIN workflow.processing_attempts a
                ON a.attempt_id = c.attempt_id AND a.snapshot_id = c.snapshot_id
              JOIN workflow.annotation_seals s
                ON s.seal_id = c.seal_id AND s.snapshot_id = c.snapshot_id
             WHERE c.snapshot_id = %(snapshot)s AND a.payload->>'kind' = 'human_annotation_build'
             ORDER BY a.started_at DESC, a.attempt_id DESC
            """, {'snapshot': snapshot_id}).fetchall()
        selected = next((row for row in rows if not attempt_id or row['attempt_id'] == attempt_id), None)
        if selected is None and attempt_id:
            raise ConsoleError('annotation_build_unknown')
        outline = None
        if history and selected:
            outline = con.execute(
                "SELECT payload->'confirmed_document_structure' AS definition "
                "FROM workflow.annotation_seals WHERE snapshot_id = %s AND seal_id = %s",
                (snapshot_id, selected['seal_id']),
            ).fetchone()['definition']
        object_ids = (_quality_candidates(con, snapshot_id, selected)
                      if history and selected and selected['state'] == 'succeeded' else None)

    if selected is None:
        return envelope, None, []

    latest = selected['attempt_id'] == rows[0]['attempt_id']
    current = latest and selected['current_generation']
    review_count = None
    if (current and object_ids is not None and 'reviewer' in actor['roles']
            and actor['account_id'] in envelope.get('named_reviewers', [])):
        review_count = _review_count(console, actor, snapshot_id, object_ids)
        # Review is captured by its own reader. A concurrent save or a new
        # attempt between both reads invalidates the proposed Review link.
        with workflow_read_transaction(store) as con:
            still_current = con.execute("""
                SELECT heads.generation = s.generation AND c.attempt_id = %(attempt)s
                    AND heads.working_revision_id = s.payload->>'working_revision_id' AS ok
                  FROM workflow.annotation_build_commands c
                  JOIN workflow.annotation_sets heads ON heads.snapshot_id = c.snapshot_id
                  JOIN workflow.annotation_seals s ON s.seal_id = c.seal_id
                  JOIN workflow.processing_attempts a ON a.attempt_id = c.attempt_id
                 WHERE c.snapshot_id = %(snapshot)s
                 ORDER BY a.started_at DESC, a.attempt_id DESC LIMIT 1
                """, {'snapshot': snapshot_id, 'attempt': selected['attempt_id']}).fetchone()
        if not still_current or not still_current['ok']:
            current = False
            review_count = None

    finish = selected['finished_at']
    if finish:
        end = datetime.fromisoformat(finish)
    else:
        end = datetime.now(timezone.utc) if selected['state'] == 'running' else None
    return envelope, {
        **selected,
        'outline': outline,
        'latest': latest,
        'current': current,
        'duration_seconds': max(0, int((end - selected['started_at']).total_seconds())) if end else None,
        'built_count': len(object_ids) if object_ids is not None else None,
        'review_count': review_count,
        'can_recover': current and selected['state'] not in {'running', 'succeeded'}
                       and not console.snapshot_is_published(snapshot_id),
    }, rows if history else []
