"""Deterministic source-context browser fixture; never a production endpoint."""
from tests.semantic_fixture_support import bind_fixture_selections
from src.source_context_review_v1 import links_of, role_of
from tests.test_source_context_review_v1 import _system
from tests.browser_postgres_support import browser_application

app = browser_application('context-browser', processing_binder=bind_fixture_selections)
state = app.state.operations_kernel
state, _, _, source, target, command = _system(state.root, console=state)
sid = command['snapshot_id']


@app.get('/browser-manifest')
def manifest():
    return {'target': f'/review?document={sid}&object={target["object_id"]}',
            'source': f'/review?document={sid}&object={source["object_id"]}',
            'target_id': target['object_id'], 'source_id': source['object_id'],
            'username': 'bert', 'password': 'bert-secret'}


@app.get('/browser-context-state')
def context_state():
    rows = {row['object_id']: row for row in state.snapshot_objects(sid)}
    return {'role': role_of(rows[source['object_id']]), 'links': links_of(rows[target['object_id']]),
            'target_status': rows[target['object_id']]['governance']['validation_status']}
