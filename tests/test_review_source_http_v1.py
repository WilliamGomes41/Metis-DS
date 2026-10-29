"""WP7 actual prepared Review GETs reject rebuilds and full source transfer.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit metrics slop releasebewijs
"""
import json
import time

from fastapi.testclient import TestClient
import psycopg
import pytest

from tests.test_review_formation_problems import FIRST, SECOND, received, execute
from tests.test_review_command_bounded_http_v1 import physical_state


@pytest.mark.parametrize('size', [32, 128])
@pytest.mark.parametrize('azure', [False, True])
def test_prepared_passage_reads_no_unused_payload_and_survives_restart(
    tmp_path, production_console, production_app, monkeypatch, size, azure,
):
    texts = [FIRST, SECOND, *[f'Gebruik geen middel {i:04d} bij deze situatie; leg de keuze vast.'
                             for i in range(size-2)]]
    source = ('<html><body><h1>Adviezen</h1>' + ''.join(f'<p>{t}</p>' for t in texts) + '</body></html>').encode()
    def configured(**kwargs):
        return production_console(azure=azure, **kwargs)
    console, sid, author, _, _, mode, _ = received(tmp_path, configured,
        monkeypatch, source_html=source, all_blocks=True)
    mode['broken'] = False
    execute(console, sid, author, 'prepared-reader-proof')
    objects = console.snapshot_objects(sid)
    focal = next(o for o in objects if o.get('content',{}).get('clean_text') == FIRST)
    before = physical_state(console, sid)
    from tests.production_support import restart_production
    console = restart_production(console)
    from src.vorming import prepared_source_views_v1 as views
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    original_prepare = views.prepare
    def retained_only(fragments):
        assert isinstance(fragments, views.SourceFragments), 'Prepared GET rebuilt raw source'
        return original_prepare(fragments)
    def forbidden(*args, **kwargs):
        raise AssertionError('Prepared Review may not load/reconstruct full source')
    monkeypatch.setattr(views, 'prepare', retained_only)
    monkeypatch.setattr(FormationTaskStore, 'load_source_views', forbidden)
    monkeypatch.setattr(FormationTaskStore, 'resolve_preparation', forbidden)
    monkeypatch.setattr('src.vorming.source_reconstruction_v1.reconstruct_source_fragments', forbidden)
    monkeypatch.setattr('src.vorming.source_preparation_context_v1.stored_extraction', forbidden)
    monkeypatch.setattr(console, '_extract', forbidden)
    original_execute = psycopg.Connection.execute
    from src.request_diagnostics_v1 import RequestDiagnostics
    original_emit = RequestDiagnostics.emit
    events = []
    def capture(self, payload):
        if payload.get('event') == 'request_finished':
            events.append(json.loads(json.dumps(payload)))
        return original_emit(self, payload)
    monkeypatch.setattr(RequestDiagnostics, 'emit', capture)
    measurements = []
    class Cursor:
        def __init__(self, cursor, query):
            self.cursor, self.query = cursor, query
        def __getattr__(self, key):
            return getattr(self.cursor, key)
        def record(self, rows):
            if 'source_read_' in self.query:
                measurements.append((self.query, len(rows), len(json.dumps(rows, default=str))))
            return rows
        def fetchone(self):
            row = self.cursor.fetchone()
            self.record([row] if row is not None else [])
            return row
        def fetchall(self):
            return self.record(self.cursor.fetchall())
    def checked_execute(connection, query, params=None, **kwargs):
        sql = str(query)
        assert not sql.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','CREATE','ALTER','TRUNCATE'))
        return Cursor(original_execute(connection, query, params, **kwargs), sql)
    origin = 'https://console.example.test' if azure else 'https://testserver'
    with TestClient(production_app(console), base_url=origin, headers={'Origin':origin}) as client:
        assert client.post('/login', data={'username':'reviewer','password':'fixture-only'},
                           follow_redirects=False).status_code == 303
        monkeypatch.setattr(psycopg.Connection, 'execute', checked_execute)
        for _ in range(2):
            measurements.clear()
            started = time.perf_counter()
            page = client.get('/review', params={'document':sid,'object':focal['object_id']})
            elapsed = time.perf_counter() - started
            assert page.status_code == 200
            assert FIRST in page.text
            assert 'name="snapshot_revision"' in page.text
            selected = [(q,n,b) for q,n,b in measurements if 'SELECT * FROM workflow.source_read_fragments' in q]
            assert selected and all('fragment_id=ANY' in q for q,_,_ in selected)
            # Existing passage choice exposes at most25 peers plus the focal
            # object and its single shared heading, independent of source size.
            assert sum(n for _,n,_ in selected) <= 27
            finished = [event for event in events if event.get('route') == '/review']
            assert finished
            phases = finished[-1]['phases']
            assert 'source_views_hydrate' in phases and 'source_views_validate' in phases
            assert 'source_build_blocks' not in phases
            print(json.dumps({'size':size,'azure':azure,'seconds':round(elapsed,4),
                'rows':sum(n for _,n,_ in measurements),'bytes':sum(b for _,_,b in measurements),
                'hydrate_exclusive_ms':phases['source_views_hydrate']['exclusive_ms'],
                'validate_ms':phases['source_views_validate']['inclusive_ms']}))
        monkeypatch.setattr(psycopg.Connection, 'execute', original_execute)
    assert physical_state(console, sid) == before


def test_partial_formation_reads_complete_prepared_evidence_without_rebuild(
    tmp_path, production_console, production_app, monkeypatch,
):
    console, sid, author, _, _, mode, _ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'partial-prepared-proof')
    before = physical_state(console, sid)
    candidate = next(o for o in console.snapshot_objects(sid)
                     if o.get('proposed_object_type') == 'recommendation')
    assert console.processing_status(sid)['formation_incomplete']
    from tests.production_support import restart_production
    console = restart_production(console)
    from src.vorming import prepared_source_views_v1 as views
    original = views.prepare
    def retained_only(fragments):
        assert isinstance(fragments, views.SourceFragments)
        return original(fragments)
    def forbidden(*args, **kwargs):
        raise AssertionError('Partial formation rebuilt committed source')
    monkeypatch.setattr(views, 'prepare', retained_only)
    monkeypatch.setattr('src.vorming.source_preparation_context_v1.stored_extraction', forbidden)
    monkeypatch.setattr('src.vorming.source_reconstruction_v1.reconstruct_source_fragments', forbidden)
    assert console.processing_status(sid)['formation_incomplete']
    with TestClient(production_app(console), base_url='https://testserver') as client:
        assert client.post('/login', data={'username':'reviewer','password':'fixture-only'},
                           follow_redirects=False).status_code == 303
        page = client.get('/review', params={'document':sid,'object':candidate['object_id']})
        assert page.status_code == 200
        assert FIRST in page.text and 'data-formation-incomplete' in page.text
    assert physical_state(console, sid) == before


def test_cold_source_cache_is_verified_without_get_writes(tmp_path, production_console, production_app, monkeypatch):
    from tests.test_azure_blob_publication_authority_v1 import _SourceStore
    from src.g2_source_store import build_g2_locator
    from src.workflows.workflow_documents_postgres_v1 import _json_text
    console, sid, author, _, _, mode, _ = received(tmp_path, production_console, monkeypatch)
    mode['broken'] = False
    execute(console, sid, author, 'cold-source-proof')
    envelope = console._envelope(sid)
    focal = next(o for o in console.snapshot_objects(sid) if o.get('content',{}).get('clean_text') == FIRST)
    path = console._source_cache_path(envelope)
    source = _SourceStore(path.read_bytes())
    console.immutable_source_store = source
    locator = build_g2_locator(sha256=envelope['sha256'], filename=path.name)
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.documents SET envelope_payload=jsonb_set(envelope_payload,"
                    "'{immutable_storage_locator}',%s::jsonb) WHERE snapshot_id=%s", (_json_text(locator),sid))
    before = physical_state(console, sid)
    with TestClient(production_app(console), base_url='https://testserver') as client:
        assert client.post('/login', data={'username':'reviewer','password':'fixture-only'},
                           follow_redirects=False).status_code == 303
        path.unlink()
        def forbidden(*args, **kwargs):
            raise AssertionError('Prepared Review GET wrote a source cache')
        monkeypatch.setattr('src.operations_console_v1._atomic_write_bytes', forbidden)
        page = client.get('/review', params={'document':sid,'object':focal['object_id']})
        assert page.status_code == 200 and FIRST in page.text
        assert source.reads and not path.exists()
        assert 'name="confirmed_object_type" value="recommendation" disabled' not in page.text
    assert physical_state(console, sid) == before
