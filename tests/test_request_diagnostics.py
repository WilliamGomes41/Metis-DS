"""Active-request diagnostics: not a performance repair claim.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# Request-local diagnostics: concurrent IDs stay isolated and cancelled requests
# clear stale context. Authenticated reads preserve the object snapshot.
# Durable storage algorithms are unchanged; these are not write-conflict tests.
# release-control-evidence: slop
# release-control-evidence: metrics
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: releasebewijs
"""
import asyncio
import contextlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.request_diagnostics_v1 import (
    RequestDiagnostics, diagnostic_phase, _LOGGER, _CURRENT, MAX_PHASE_EVENTS,
)


@pytest.fixture
def events(monkeypatch):
    monkeypatch.delenv('APPLICATIONINSIGHTS_CONNECTION_STRING', raising=False)
    records=[]
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: records.append(json.loads(msg)))
    return records


def test_blocked_request_is_visible_before_response_and_redacted(events):
    app=FastAPI(); entered=threading.Event(); release=threading.Event()
    @app.get('/source-selection')
    def blocked():
        with diagnostic_phase('document_list'):
            entered.set(); assert release.wait(5)
        return {'unchanged': True}
    app.add_middleware(RequestDiagnostics, heartbeat_seconds=0.01)
    with TestClient(app) as client, ThreadPoolExecutor() as pool:
        pending=pool.submit(client.get, '/source-selection?token=private-secret',
                            headers={'Authorization':'Bearer private-token'})
        try:
            assert entered.wait(2)
            limit=time.monotonic()+2
            while not any(r['event']=='request_running' for r in events) and time.monotonic()<limit:
                time.sleep(0.005)
            assert not pending.done()
            assert any(r['event']=='request_started' for r in events)
            heartbeat=next(r for r in events if r['event']=='request_running')
            assert heartbeat['phase']=='document_list'
            assert not any(r['event']=='request_finished' for r in events)
        finally:release.set()
        response=pending.result(2)
        assert response.json()=={'unchanged':True}
        assert response.headers['x-metis-request-id']==heartbeat['request_id']
    finished=next(r for r in events if r['event']=='request_finished')
    assert finished['status']==200 and finished['outcome']=='completed'
    assert finished['phases']['document_list']['calls']==1
    assert 'private' not in json.dumps(events)
    assert _CURRENT.get() is None


def test_concurrent_requests_have_distinct_ids_and_bounded_phase_logs(events):
    barrier=threading.Barrier(2);app=FastAPI()
    @app.get('/review')
    def review():
        barrier.wait(timeout=3)
        for _ in range(150):
            with diagnostic_phase('objects_read'):pass
        return 'ok'
    app.add_middleware(RequestDiagnostics)
    with TestClient(app) as client,ThreadPoolExecutor() as pool:
        results=list(pool.map(lambda _:client.get('/review'),range(2)))
    ids={r.headers['x-metis-request-id'] for r in results}
    assert len(ids)==2
    for rid in ids:
        rows=[r for r in events if r.get('request_id')==rid]
        assert sum(r['event']=='phase_started' for r in rows)==MAX_PHASE_EVENTS
        assert rows[-1]['phases']['objects_read']['calls']==150


def test_failures_and_telemetry_outage_do_not_change_http_behavior(events,monkeypatch):
    app=FastAPI()
    @app.get('/review')
    def review():raise ValueError('private exception payload')
    app.add_middleware(RequestDiagnostics)
    with TestClient(app,raise_server_exceptions=False) as client:
        assert client.get('/review').status_code==500
    assert events[-1]['outcome']=='exception'
    assert 'private' not in json.dumps(events)
    def broken(*args,**kwargs):raise OSError('private exporter error')
    fake=type('Broken',(),{'request':broken,'emit':broken,'shutdown':broken})()
    good=FastAPI()
    @good.get('/review')
    def ok():return {'ok':True}
    good.add_middleware(RequestDiagnostics,telemetry=fake)
    monkeypatch.setattr(_LOGGER,'info',broken)
    with TestClient(good) as client:
        assert client.get('/review').json()=={'ok':True}


def test_cancelled_request_has_final_evidence_and_cleans_context(events):
    async def run():
        entered=asyncio.Event()
        async def blocked(scope,receive,send):
            with diagnostic_phase('source_read'):
                entered.set();await asyncio.Future()
        observer=RequestDiagnostics(blocked,heartbeat_seconds=0.01)
        async def call():
            try:await observer({'type':'http','method':'GET','path':'/review'},None,None)
            finally:assert _CURRENT.get() is None
        task=asyncio.create_task(call());await entered.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    asyncio.run(run())
    assert events[-1]['outcome']=='cancelled'
    assert events[-1]['phases']['source_read']['calls']==1


def test_unrelated_routes_are_not_collected(events):
    app=FastAPI()
    @app.get('/session/status')
    def status():return {'ok':True}
    app.add_middleware(RequestDiagnostics)
    with TestClient(app) as client:
        response=client.get('/session/status')
        assert response.status_code==200 and 'x-metis-request-id' not in response.headers
    assert not any(r['event']=='request_started' for r in events)


def test_actual_authenticated_routes_report_owner_phases(review_client,events):
    console,client,sid=review_client
    observed=TestClient(RequestDiagnostics(client.app), base_url="https://testserver", cookies=client.cookies)
    before=json.dumps(console.snapshot_objects(sid),sort_keys=True)
    for route,phase in [('/source-selection','selection_projection'),('/review','review_render')]:
        response=observed.get(route,params={'document':sid})
        assert response.status_code==200
        finished=[r for r in events if r['event']=='request_finished' and r['route']==route][-1]
        assert finished['phases'][phase]['calls']>=1
        assert finished['phases']['document_list']['calls']>=1
    assert before==json.dumps(console.snapshot_objects(sid),sort_keys=True)
    assert sid not in json.dumps(events)
    observed.close()


from tests.test_review_render_source_reuse import review_client  # real authenticated route fixture


def test_real_azure_sdk_exports_start_before_request_finishes(events,monkeypatch):
    """Actual exporter serialization + HTTP transport to a local intake endpoint.

    Does not claim Azure resource credentials/ingestion are verified.
    """
    import gzip
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from src.request_diagnostics_v1 import AzureTelemetry
    # Some executor sandboxes expose /proc in the host PID namespace while
    # getpid() reports a virtual PID. Adapt only this irrelevant process probe;
    # leave the Azure SDK serialization, batching and HTTP transport real.
    import os
    from pathlib import Path
    import psutil
    proc_stat=Path('/proc/self/stat')
    if proc_stat.exists():
        proc_pid=int(proc_stat.read_text().split()[0])
        if proc_pid != os.getpid():
            original_process=psutil.Process
            monkeypatch.setattr(psutil,'Process',lambda pid=None: original_process(proc_pid if pid is None else pid))
    received=[];started_exported=threading.Event()
    class Intake(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            raw=self.rfile.read(int(self.headers['Content-Length']))
            if self.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
            data=json.loads(raw)
            received.extend(data if isinstance(data,list) else [data])
            if 'request_started' in raw.decode():started_exported.set()
            response=json.dumps({'itemsReceived':len(data),'itemsAccepted':len(data),'errors':[]}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(response)));self.end_headers();self.wfile.write(response)
    server=ThreadingHTTPServer(('127.0.0.1',0),Intake)
    listener=threading.Thread(target=server.serve_forever,daemon=True);listener.start()
    telemetry=AzureTelemetry('InstrumentationKey=00000000-0000-0000-0000-000000000001;'
        f'IngestionEndpoint=http://127.0.0.1:{server.server_port}',{'version':'test-build','instance':'test-instance'})
    entered=threading.Event();release=threading.Event();app=FastAPI()
    @app.get('/source-selection')
    def blocked():
        with diagnostic_phase('source_read'):
            entered.set();assert release.wait(8)
        return {'ok':True}
    app.add_middleware(RequestDiagnostics,telemetry=telemetry,heartbeat_seconds=0.05)
    try:
        with TestClient(app) as client,ThreadPoolExecutor() as pool:
            pending=pool.submit(client.get,'/source-selection?secret=never-export',
                                headers={'Cookie':'secret-cookie'})
            try:
                assert entered.wait(2)
                assert started_exported.wait(5), 'SDK failed to export while HTTP request was unfinished'
                assert not pending.done()
            finally:release.set()
            assert pending.result(2).status_code==200
        serialized=json.dumps(received)
        assert 'request_running' in serialized and 'request_finished' in serialized
        assert 'never-export' not in serialized and 'secret-cookie' not in serialized
        requests=[r for r in received if r['data']['baseType']=='RequestData']
        assert requests, 'No completed request trace exported'
        request=requests[0]
        assert request['data']['baseData']['responseCode']=='200'
        assert request['tags']['ai.application.ver']=='test-build'
        operation=request['tags']['ai.operation.id']
        logs=[r for r in received if r['data']['baseType']=='MessageData']
        assert any(r['tags'].get('ai.operation.id')==operation and
                   'request_started' in r['data']['baseData']['message'] for r in logs)
    finally:
        server.shutdown();server.server_close();listener.join(2)
