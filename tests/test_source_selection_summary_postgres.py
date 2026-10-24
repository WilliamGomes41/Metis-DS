"""#835: compact source summaries must also bound server-side JSONB reads.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import hashlib
import json
import math
import time

import psycopg
import pytest

from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_insight_v1 import _login


def test_source_summary_does_not_reread_toasted_diagnostics(
    tmp_path, production_console, production_app, monkeypatch
):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    client = _login(console, users['researcher']['username'], production_app=production_app)
    # Five attempts carrying source/validation evidence, as in the incident.
    # Distinct deterministic text keeps the payload genuinely out-of-line.
    fragments = [
        {"index": i, "text": hashlib.sha256(str(i).encode()).hexdigest() * 4}
        for i in range(10000)
    ]
    envelope = store.get_envelope(sid)
    for attempt in envelope['processing_attempts']:
        attempt['diagnostic'] = {"phase": "proposal_received", "validator_input": fragments}
    while len(envelope['processing_attempts']) < 5:
        envelope['processing_attempts'].append(deepcopy(envelope['processing_attempts'][0]))
    store.write_bundle(envelope=envelope)
    queries = []
    original = psycopg.Connection.execute

    def observed(connection, query, *args, **kwargs):
        if isinstance(query, str) and 'SELECT d.snapshot_id,d.title' in query:
            queries.append(query)
        return original(connection, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.Connection, 'execute', observed)
    summaries = console.source_selection_documents(actor_id=users['researcher']['account_id'])
    assert [row['snapshot_id'] for row in summaries] == [sid]
    assert 'validator_input' not in json.dumps(summaries)
    assert len(queries) == 1
    with store._connect() as con:
        size = con.execute(
            'SELECT pg_column_size(envelope_payload) AS n FROM workflow.documents WHERE snapshot_id=%s', (sid,)
        ).fetchone()['n']
        plan = con.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) ' + queries[0]).fetchone()['QUERY PLAN'][0]
    blocks = plan['Plan'].get('Shared Hit Blocks', 0) + plan['Plan'].get('Shared Read Blocks', 0)
    budget = 20 + 4 * math.ceil(size / 8192)
    print('SOURCE_SUMMARY_IO', {'stored_bytes': size, 'buffer_accesses': blocks,
                               'budget': budget, 'execution_ms': plan['Execution Time']})
    assert blocks <= budget, 'Compact output repeatedly reads the full TOASTed envelope'
    with store._connect() as con:
        before = con.execute(
            'SELECT md5(envelope_payload::text) AS digest FROM workflow.documents WHERE snapshot_id=%s', (sid,)
        ).fetchone()['digest']
    started = time.perf_counter()
    response = client.get('/source-selection')
    print('SOURCE_SUMMARY_HTTP_SECONDS', round(time.perf_counter() - started, 3))
    assert response.status_code == 200 and 'Bronselectie' in response.text
    assert 'validator_input' not in response.text
    with store._connect() as con:
        assert con.execute(
            'SELECT md5(envelope_payload::text) AS digest FROM workflow.documents WHERE snapshot_id=%s', (sid,)
        ).fetchone()['digest'] == before


@pytest.mark.parametrize('reviewers', [None, ['not-the-assigned-reviewer']])
def test_summary_still_rejects_invalid_reviewer_authority(
    tmp_path, production_console, reviewers
):
    from src.operations_console_v1 import ConsoleError
    from psycopg.types.json import Jsonb
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    # Bypass the writer only to model corrupt durable data, not a valid command.
    with store._connect() as con:
        con.execute("UPDATE workflow.documents SET envelope_payload=jsonb_set(envelope_payload,"
                    "'{named_reviewers}',%s) WHERE snapshot_id=%s", (Jsonb(reviewers), sid))
    with pytest.raises(ConsoleError, match='workflow_document_unavailable'):
        console.source_selection_documents(actor_id=users['researcher']['account_id'])


def test_source_summary_database_failure_keeps_cause_and_request_id(
    tmp_path, production_console, production_app, monkeypatch
):
    from src.request_diagnostics_v1 import _LOGGER
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    events = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, payload: events.append(json.loads(payload)))
    original = psycopg.Connection.execute

    def blocked(connection, query, *args, **kwargs):
        if isinstance(query, str) and 'SELECT d.snapshot_id,d.title' in query:
            # A real PostgreSQL cancellation on the actual overview connection.
            original(connection, "SET LOCAL statement_timeout='20ms'")
            original(connection, "SELECT pg_sleep(1)")
        return original(connection, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.Connection, 'execute', blocked)
    response = client.get('/source-selection')
    assert response.status_code == 400
    assert 'workflow_document_unavailable' in response.text
    event = next(row for row in events if row.get('event') == 'request_finished'
                 and row.get('request_id') == response.headers['x-metis-request-id'])
    assert event['error']['code'] == 'workflow_document_unavailable'
    assert any(cause['type'] == 'QueryCanceled' and cause['sqlstate'] == '57014'
               for cause in event['error']['causes'])
    assert any('list_source_selection_summaries' in frame
               for cause in event['error']['causes'] for frame in cause.get('frames', []))
