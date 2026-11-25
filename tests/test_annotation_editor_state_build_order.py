"""Codex P2 on #1095: the editor never pairs stale annotations with a finished build."""
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
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


@pytest.fixture(autouse=True)
def _no_document_round(monkeypatch):
    # These tests script only the build reads; no document-check round exists.
    monkeypatch.setattr(ui.document_check, 'read', lambda connection, snapshot_id: None)


def test_build_finishing_between_reads_never_shows_stale_annotations_as_built(monkeypatch):
    world = {'finished': False}

    def read_then_finish(value):
        world['finished'] = True
        return value

    def overview(console, *, actor_id, snapshot_id, **_options):
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


def _client(monkeypatch, builds, bindings=None):
    """Serve the scripted build states, one per latest_build read; overview reads are counted."""
    reads = {'builds': iter(builds), 'overviews': 0}

    def overview(console, *, actor_id, snapshot_id, **_options):
        reads['overviews'] += 1
        return {'object_bindings': dict(bindings or {}), 'read': reads['overviews']}

    monkeypatch.setattr(ui.domain, 'overview', overview)
    monkeypatch.setattr(build, 'latest_build', lambda connection, snapshot_id: next(reads['builds']))
    app = FastAPI()
    ui.install(app, _Console(), lambda request: {'account_id': 'researcher'},
               lambda *a, **k: '', lambda *a, **k: '', str, dispatcher=None)
    return TestClient(app), reads


def test_build_starting_between_reads_is_read_again_until_consistent(monkeypatch):
    done = {'attempt_id': 'b1', 'state': 'succeeded'}
    started = {'attempt_id': 'b2', 'state': 'running'}
    client, reads = _client(monkeypatch, [done, started, started, started])

    view = client.get('/annotations/api', params={'document': 'doc-1'}).json()

    # The finished b1 was read before the overview, b2 started during it: never show b1 as finished.
    assert view['current_build'] == started, view
    assert reads['overviews'] == 2


def test_build_changing_on_every_read_fails_as_stale_overview(monkeypatch):
    changing = [{'attempt_id': 'b' + str(n), 'state': 'running'} for n in range(20)]
    client, reads = _client(monkeypatch, changing)

    with pytest.raises(ConsoleError) as stale:
        client.get('/annotations/api', params={'document': 'doc-1'})

    assert stale.value.code == 'annotation_overview_stale'
    assert reads['overviews'] == 3
