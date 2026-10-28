"""Actual production composition; controlled diagnostic evidence, native storage."""
from copy import deepcopy
from pathlib import Path

from tests.browser_postgres_support import browser_application
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_document_diagnosis_redesign_v1 import _system, PASSWORD
from tests.production_support import restart_production
from src.vorming.processing_diagnostics_v1 import processing_diagnostic_rows
from src.review.review_ledger import read_events

app = browser_application('insight-owner', processing_binder=bind_fixture_selections)
state = app.state.operations_kernel
_, sid = _system(Path('/tmp'), production_console=lambda **kwargs: state)


@app.get('/browser-manifest')
def manifest():
    return dict(document=sid, username='reviewer.854', password=PASSWORD,
                objects=processing_diagnostic_rows(state.snapshot_objects(sid)))


@app.get('/browser-owner-state')
def current_state():
    fresh = restart_production(state)
    return deepcopy(dict(envelope=fresh._envelope(sid), objects=fresh.snapshot_objects(sid),
                         revision=fresh.objects_revision(sid), bindings=fresh.object_review_bindings(sid),
                         events=read_events(fresh._ledger_path)))
