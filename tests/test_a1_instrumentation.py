"""A1: instrumentation only. Diagnostics evidence grows; behaviour does not.

# release-control-evidence: scope/belofte
# release-control-evidence: metrics
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
# Request-local evidence only: no durable state, no responses or verdicts change.
"""
from tests.semantic_fixture_support import bind_fixture_selections
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.request_diagnostics_v1 as diagnostics
from src.request_diagnostics_v1 import RequestDiagnostics, diagnostic_phase, _LOGGER, _CURRENT


@pytest.fixture
def events(monkeypatch):
    monkeypatch.delenv('APPLICATIONINSIGHTS_CONNECTION_STRING', raising=False)
    records = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: records.append(json.loads(msg)))
    return records


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _finished(events):
    return [row for row in events if row['event'] == 'request_finished'][-1]


# --- 1. exclusive time and parent/child phase tree ---------------------------

def test_phase_totals_report_exclusive_time_and_parent_child_tree(events, monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(diagnostics.time, 'perf_counter', clock)
    app = FastAPI()

    @app.get('/review')
    def review():
        with diagnostic_phase('review_render'):
            clock.now += 0.010
            with diagnostic_phase('objects_read'):
                clock.now += 0.030
                with diagnostic_phase('db_execute'):
                    clock.now += 0.005
            with diagnostic_phase('objects_read'):
                clock.now += 0.020
            with diagnostic_phase('not_a_known_phase'):  # ignored: fixed names only
                clock.now += 0.001
        return {'unchanged': True}

    app.add_middleware(RequestDiagnostics)
    with TestClient(app) as client:
        assert client.get('/review').json() == {'unchanged': True}
    phases = _finished(events)['phases']
    assert phases['review_render'] == {'calls': 1, 'inclusive_ms': 66.0, 'exclusive_ms': 11.0}
    assert phases['objects_read'] == {'calls': 2, 'inclusive_ms': 55.0, 'exclusive_ms': 50.0}
    assert phases['db_execute'] == {'calls': 1, 'inclusive_ms': 5.0, 'exclusive_ms': 5.0}
    # Exclusive times partition the outermost inclusive time exactly.
    assert sum(v['exclusive_ms'] for v in phases.values()) == phases['review_render']['inclusive_ms']
    assert _finished(events)['phase_tree'] == {
        'review_render': {'calls': 1, 'inclusive_ms': 66.0, 'exclusive_ms': 11.0},
        'review_render/objects_read': {'calls': 2, 'inclusive_ms': 55.0, 'exclusive_ms': 50.0},
        'review_render/objects_read/db_execute': {'calls': 1, 'inclusive_ms': 5.0, 'exclusive_ms': 5.0},
    }
    started = [r for r in events if r['event'] == 'phase_started']
    assert [(r['phase'], r['parent_phase']) for r in started] == [
        ('review_render', None), ('objects_read', 'review_render'),
        ('db_execute', 'objects_read'), ('objects_read', 'review_render')]
    assert _CURRENT.get() is None


def test_phase_tree_is_bounded(events, monkeypatch):
    monkeypatch.setattr(diagnostics, 'MAX_TREE_NODES', 2)
    app = FastAPI()

    @app.get('/tree')
    def tree():
        with diagnostic_phase('document_list'):
            with diagnostic_phase('db_connect'):
                pass
            with diagnostic_phase('db_execute'):
                pass
        return 'ok'

    app.add_middleware(RequestDiagnostics)
    with TestClient(app) as client:
        assert client.get('/tree').status_code == 200
    finished = _finished(events)
    assert len(finished['phase_tree']) == 2
    assert finished['phase_tree_truncated'] is True
    assert finished['phases']['db_execute']['calls'] == 1  # flat totals stay complete


def test_phase_exception_keeps_exclusive_accounting_and_propagates(events):
    app = FastAPI()

    @app.get('/review')
    def review():
        with diagnostic_phase('review_render'):
            with diagnostic_phase('objects_read'):
                raise ValueError('private failure')

    app.add_middleware(RequestDiagnostics)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get('/review').status_code == 500
    finished = _finished(events)
    assert set(finished['phase_tree']) == {'review_render', 'review_render/objects_read'}
    assert finished['phases']['review_render']['exclusive_ms'] <= finished['phases']['review_render']['inclusive_ms']
    assert 'private' not in json.dumps(events)


# --- 2. source reconstruction / reuse / input comparison counters -----------

from tests.test_navigation_source_reuse import source_navigation  # noqa: E402,F401


def test_source_reconstruction_counters_are_reported_without_changing_results(events, source_navigation):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    probe, fragments = source_navigation
    spans = next(o for o in probe.objects['synthetic-0']
                 if o.get('metadata', {}).get('semantic_passage', {}).get('spans'))['metadata']['semantic_passage']['spans']
    expected = materialisation.resolve_source_selection(spans, fragments=deepcopy(fragments))
    app = FastAPI()
    results = []

    @app.get('/review')
    def review():
        with materialisation.source_reconstruction_scope():
            results.append(materialisation.resolve_source_selection(spans, fragments=fragments))  # build
            results.append(materialisation.resolve_source_selection(spans, fragments=fragments))  # reuse
            changed = deepcopy(fragments)
            changed[-1]['fragment_hash'] = 'changed-source-hash'
            materialisation.resolve_source_selection(spans, fragments=changed)  # build (new input)
        materialisation.resolve_source_selection(spans, fragments=fragments)  # unscoped build
        return 'ok'

    app.add_middleware(RequestDiagnostics)
    with TestClient(app) as client:
        assert client.get('/review').status_code == 200
    assert results == [expected, expected]
    counters = _finished(events)['counters']
    assert counters == {
        'source_reconstruction_built': 2,
        'source_reconstruction_reused': 1,
        'source_reconstruction_unscoped': 1,
        'source_input_compared': 2,
        'source_input_hashed': 2,
    }


def test_counters_outside_a_request_are_noops():
    from src.request_diagnostics_v1 import diagnostic_count
    assert _CURRENT.get() is None
    diagnostic_count('source_reconstruction_built')
    diagnostic_count('not_a_counter')


def test_unknown_counter_names_are_ignored(events):
    from src.request_diagnostics_v1 import diagnostic_count
    app = FastAPI()

    @app.get('/review')
    def review():
        diagnostic_count('private-free-text')
        diagnostic_count('source_input_compared')
        return 'ok'

    app.add_middleware(RequestDiagnostics)
    with TestClient(app) as client:
        client.get('/review')
    assert _finished(events)['counters'] == {'source_input_compared': 1}
    assert 'private' not in json.dumps(events)


# --- 3. deployed commit on /health and as diagnostics fallback --------------

COMMIT = 'c7a99596c5ed8a9c705870ae7dfd84a545558360'


@pytest.fixture
def marker(tmp_path, monkeypatch):
    path = tmp_path / 'deployed_commit.txt'
    monkeypatch.setattr(diagnostics, 'DEPLOYED_COMMIT_MARKER', path)
    return path


@pytest.mark.parametrize('content,expected', [
    (COMMIT + '\n', COMMIT), (None, None), ('not-a-commit', None), (COMMIT.upper(), None), (COMMIT[:12], None)])
def test_deployed_commit_reads_only_a_full_lowercase_sha(marker, content, expected):
    if content is not None:
        marker.write_text(content)
    assert diagnostics.deployed_commit() == expected


def test_diagnostics_identity_falls_back_to_deployed_commit_file(events, marker, monkeypatch):
    marker.write_text(COMMIT)
    monkeypatch.delenv('METIS_BUILD_COMMIT', raising=False)
    assert RequestDiagnostics(FastAPI()).identity['version'] == COMMIT
    monkeypatch.setenv('METIS_BUILD_COMMIT', 'abc1234')
    assert RequestDiagnostics(FastAPI()).identity['version'] == 'abc1234'  # env stays authoritative
    monkeypatch.delenv('METIS_BUILD_COMMIT')
    marker.unlink()
    assert RequestDiagnostics(FastAPI()).identity['version'] == 'unknown'  # unchanged default


def test_console_health_reports_running_commit(tmp_path, marker, *, production_app, production_console):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path, source_store=tmp_path / 'sources' / 'private',
                                runtime=tmp_path / 'output' / 'runtime' / 'operations-console')
    client = TestClient(production_app(console))
    assert client.get('/health').json()['deployed_commit'] == 'not_recorded'
    marker.write_text(COMMIT + '\n')
    health = client.get('/health').json()
    assert health['deployed_commit'] == COMMIT
    assert health['status'] == 'ok' and health['product_api'] is False


def test_inspection_service_health_reports_running_commit(marker):
    from src.service_app import create_app
    client = TestClient(create_app('fixture'))
    assert client.get('/health').json()['deployed_commit'] == 'not_recorded'
    marker.write_text(COMMIT + '\n')
    health = client.get('/health').json()
    assert health['deployed_commit'] == COMMIT
    assert health['status'] == 'ok'


def test_product_api_health_reports_running_commit(tmp_path, marker):
    from tests.test_product_api_v1 import client
    c, _ = client(tmp_path)
    assert c.get('/v1/health').json()['deployed_commit'] == 'not_recorded'
    marker.write_text(COMMIT + '\n')
    health = c.get('/v1/health').json()
    assert health['deployed_commit'] == COMMIT
    assert health['status'] == 'ok' and health['generation_enabled'] is False
    schema = c.get('/openapi.json').json()['components']['schemas']['HealthResponse']
    assert 'deployed_commit' in schema['properties']
    assert 'deployed_commit' not in schema.get('required', [])  # additive, backward compatible
