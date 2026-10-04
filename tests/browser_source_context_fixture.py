"""Deterministic source-context browser fixture; never a production endpoint."""
import tempfile
from pathlib import Path

from src.operations_console_app import create_console_app
from src.source_context_review_v1 import links_of, role_of
from tests.test_source_context_review_v1 import _system

state, _, _, source, target, command = _system(Path(tempfile.mkdtemp(prefix='metis-context-browser-')))
sid = command['snapshot_id']
app = create_console_app(state)


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
