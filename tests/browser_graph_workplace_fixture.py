"""Test-only real PG graph editing with source-bound PDF evidence."""
from copy import deepcopy

from tests.browser_postgres_support import browser_application
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_decision_graph_chain import _accounts, _ingest_boom, source_pdf, policy

app = browser_application('graph-workplace', processing_binder=bind_fixture_selections)
state = app.state.operations_kernel
accounts = _accounts(state)
documents = []
initial = {}
for index in range(2):
    sid = _ingest_boom(state, accounts, data=source_pdf(), filename=f'graph-{index}.pdf',
        content_type='application/pdf', family=f'graph-{index}', named_reviewers=[],
        review_policy=policy(accounts))['snapshot_id']
    rows = [o for o in state.snapshot_objects(sid) if o['object_type'] != 'document']
    evidence = next(k for k, v in state._envelope(sid)['decision_graph_evidence']['items'].items() if v['kind'] == 'graphic')
    documents.append(dict(snapshot_id=sid, ids=[o['object_id'] for o in rows], evidence=evidence))
    initial[sid] = deepcopy(state.snapshot_objects(sid)), state._envelope(sid)['sha256']


@app.get('/browser-manifest')
def manifest():
    return dict(documents=documents, username='researcher.anne', password='anne-secret')


@app.get('/browser-graph-state')
def graph_state():
    result = []
    for d in documents:
        sid = d['snapshot_id']
        envelope = state._envelope(sid)
        rows = state.snapshot_objects(sid)
        before, source_hash = initial[sid]
        identity = lambda rs: [(o['object_id'], o['content'], o['provenance']['source_fragments']) for o in rs]
        result.append(dict(revision=state.objects_revision(sid), graph=envelope['decision_graph'],
            reviews=envelope.get('decision_graph_reviews', []), source_unchanged=envelope['sha256'] == source_hash,
            candidate_sources_unchanged=identity(rows) == identity(before)))
    return result
