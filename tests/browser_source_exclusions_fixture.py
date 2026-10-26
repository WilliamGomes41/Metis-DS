"""Synthetic metadata batch over the real PostgreSQL application; test-only routes."""
from copy import deepcopy

from tests.browser_postgres_support import browser_application
from tests.test_source_accountability_v1 import system
from src.source_context_review_v1 import role_of

app = browser_application('source-exclusions-browser', processing_binder=lambda console: None)
state = app.state.operations_kernel
state, initial, command = system(state.root, console=state, production_console=None)
sid = command['snapshot_id']
source_hash = state._envelope(sid)['sha256']
unchanged = deepcopy([row for row in initial if row['object_id'] not in command['source_object_ids']])


@app.get('/browser-manifest')
def manifest():
    return {'review': '/review?document=' + sid + '&task=inventory',
            'metadata_ids': command['source_object_ids'],
            'username': 'reviewer', 'password': 'long-test-password'}


@app.get('/browser-exclusions-state')
def exclusions_state():
    current = state.snapshot_objects(sid)
    return {'excluded': sorted(row['object_id'] for row in current if role_of(row).get('role') == 'excluded'),
            'unselected_unchanged': all(row in current for row in unchanged),
            'source_unchanged': state._envelope(sid)['sha256'] == source_hash}
