"""Codex P2 on #1095: the editor never pairs stale annotations with a finished build."""
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_ui_v1 as ui


class _Connection:
    read_only = False


class _Store:
    @contextmanager
    def _connect(self):
        yield _Connection()


class _Console:
    workflow_document_store = _Store()


def test_build_finishing_between_reads_never_shows_stale_annotations_as_built(monkeypatch):
    world = {'finished': False}

    def read_then_finish(value):
        world['finished'] = True
        return value

    def overview(console, *, actor_id, snapshot_id):
        bindings = {'a1': 'bound'} if world['finished'] else {}
        return read_then_finish({'object_bindings': bindings})

    def latest_build(connection, snapshot_id):
        state = 'succeeded' if world['finished'] else 'running'
        return read_then_finish({'attempt_id': 'b1', 'state': state})

    monkeypatch.setattr(ui.domain, 'overview', overview)
    monkeypatch.setattr(build, 'latest_build', latest_build)
    app = FastAPI()
    ui.install(app, _Console(), lambda request: {'account_id': 'researcher'},
               lambda *a, **k: '', lambda *a, **k: '', str, dispatcher=None)

    view = TestClient(app).get('/annotations/api', params={'document': 'doc-1'}).json()

    stale_but_finished = view['current_build']['state'] == 'succeeded' and not view['object_bindings']
    assert not stale_but_finished, view
    # A build read as running keeps the editor polling, so the newer bindings are picked up.
    assert view['current_build']['state'] == 'running' and view['object_bindings'] == {'a1': 'bound'}
