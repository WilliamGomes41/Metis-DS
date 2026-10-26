"""Test-only native PG documents for correction followed by exact approval."""
from copy import deepcopy

from tests.browser_postgres_support import browser_application
from tests.semantic_fixture_support import bind_fixture_selections

app = browser_application('formation-repair', processing_binder=bind_fixture_selections)
state = app.state.operations_kernel
researcher = state.create_account(username='anne', password='anne-secret', roles=('researcher',))
reviewer = state.create_account(username='bert', password='bert-secret', roles=('reviewer',))
text = 'Eenzaamheid is een gevoel van gemis.'
bind_fixture_selections(state, [(text, 'definition')])
documents = []
initial = {}
for index in range(2):
    sid = state.ingest(actor_id=researcher['account_id'], filename=f'correctie-{index}.html',
        data=('<html><body><h1>Richtlijn</h1><h2>1 Begin</h2><p>' + text + '</p><h2>2 Vervolg</h2></body></html>').encode(),
        content_type='text/html', ingest_kind='new', title=f'Correctie {index}', version='1.0', date='2026-10-26',
        live_url='', class_='richtlijn', family=f'correction-{index}', named_reviewers=[reviewer['account_id']])['snapshot_id']
    rows = state.snapshot_objects(sid)
    oid = next(o['object_id'] for o in rows if o.get('proposed_object_type') == 'definition')
    parent = next(o['object_id'] for o in rows if '2 Vervolg' in o['content']['clean_text'])
    documents.append(dict(snapshot_id=sid, object_id=oid, parent_id=parent))
    initial[sid] = deepcopy(rows), state._envelope(sid)['sha256']


@app.get('/browser-manifest')
def manifest():
    return dict(documents=documents, username='bert', password='bert-secret')


@app.get('/browser-repair-state')
def repair_state():
    result = []
    for d in documents:
        sid, oid = d['snapshot_id'], d['object_id']
        rows = state.snapshot_objects(sid)
        obj = next(o for o in rows if o['object_id'] == oid)
        before, source_hash = initial[sid]
        result.append(dict(object_id=oid, version=obj['object_version'], status=obj['governance']['validation_status'],
            type=obj.get('confirmed_object_type'), parent=obj.get('parent_object_id'),
            revision=state.objects_revision(sid), source_unchanged=state._envelope(sid)['sha256'] == source_hash,
            text_unchanged=obj['content'] == next(o['content'] for o in before if o['object_id'] == oid),
            others_unchanged=all(o in rows for o in before if o['object_id'] != oid)))
    return result
