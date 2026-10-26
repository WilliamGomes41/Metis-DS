"""Literal continuation over the real PostgreSQL app; test-only evidence routes."""
from copy import deepcopy

from tests.browser_postgres_support import browser_application
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_source_bound_continuation_repair import (
    FIRST, CONTINUATION, MERGED, _console, _split_existing_object,
)

app = browser_application('continuation-workplace', processing_binder=bind_fixture_selections)
state = app.state.operations_kernel
state, researcher, reviewer = _console(state.root, production_console=lambda **_: state)
documents = []
initial = {}
for index in range(2):
    receipt = state.ingest(actor_id=researcher['account_id'], filename=f'continuation-{index}.html',
        data=f'<html><body><h1>Eenzaamheid</h1><p>{FIRST}</p><p>{CONTINUATION}</p></body></html>'.encode(),
        content_type='text/html', ingest_kind='new', title=f'Bronaanvulling {index}',
        version='1.0', date='2026-10-26', live_url='', class_='richtlijn',
        family=f'continuation-{index}', named_reviewers=[reviewer['account_id']])
    sid = receipt['snapshot_id']
    oid = _split_existing_object(state, sid)
    documents.append({'snapshot_id': sid, 'object_id': oid})
    initial[sid] = (deepcopy(state.snapshot_objects(sid)), state._envelope(sid)['sha256'])


@app.get('/browser-manifest')
def manifest():
    return {'documents': documents, 'username': 'reviewer.bert', 'password': 'bert-secret'}


@app.get('/browser-continuation-state')
def continuation_state():
    result = []
    for item in documents:
        sid, oid = item['snapshot_id'], item['object_id']
        rows = state.snapshot_objects(sid)
        obj = next(row for row in rows if row['object_id'] == oid)
        before, source_hash = initial[sid]
        result.append({'object_id': oid, 'version': obj['object_version'],
            'revision': state.objects_revision(sid), 'status': obj['governance']['validation_status'],
            'merged': obj['content']['clean_text'] == MERGED,
            'history_count': len([row for row in state.snapshot_objects(sid, include_blocked=True) if row['object_id'] == oid]),
            'others_unchanged': all(row in rows for row in before if row['object_id'] != oid),
            'source_unchanged': state._envelope(sid)['sha256'] == source_hash})
    return result
