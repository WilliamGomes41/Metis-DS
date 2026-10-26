"""Synthetic headings over the real PG application; test-only evidence routes."""
from copy import deepcopy

from tests.browser_postgres_support import browser_application
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_a08_heading_batch_atomic import _setup

app = browser_application('heading-workplace', processing_binder=bind_fixture_selections)
state = app.state.operations_kernel
state, accounts, sid, ids = _setup(state.root, production_console=lambda **_: state)
initial = deepcopy(state.snapshot_objects(sid))
source_hash = state._envelope(sid)['sha256']


@app.get('/browser-manifest')
def manifest():
    return {'snapshot_id': sid, 'heading_ids': ids,
            'username': 'reviewer.bert', 'password': 'bert-secret'}


@app.get('/browser-heading-state')
def heading_state():
    current = state.snapshot_objects(sid)
    approved = sorted(row['object_id'] for row in current
        if row['object_id'] in ids and row['governance']['validation_status'] == 'approved')
    return {'approved': approved, 'revision': state.objects_revision(sid),
            'unselected_unchanged': all(row in current for row in initial if row['object_id'] not in approved),
            'source_unchanged': state._envelope(sid)['sha256'] == source_hash}
