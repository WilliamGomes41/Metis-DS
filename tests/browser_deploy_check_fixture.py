"""Real PG production app for Raad's deploy check; injected faults are fixture-only."""
import json
from hashlib import sha256

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from psycopg import sql
from psycopg.rows import tuple_row

from tests.browser_postgres_support import browser_application
from tests.test_availability_repair import accounts, bind, provider

app = browser_application('deploy-check-browser', processing_binder=lambda state: None)
console = app.state.operations_kernel
author, reviewer = accounts(console)
bind(console, provider)
console.ingest(actor_id=author, filename='fixture.html', content_type='text/html',
               data=b'<html><body><p>Gebruik geen zalf.</p></body></html>', ingest_kind='new',
               title='Single passage', version='1', date='2026-10-23', live_url='',
               class_='richtlijn', family='fixture', named_reviewers=[reviewer])
faults = {}


@app.middleware('http')
async def injected_fault(request: Request, call_next):
    fault = faults.get(request.url.path) if request.method == 'GET' else None
    if fault == 'status':
        return PlainTextResponse('Internal Server Error', status_code=500)
    response = await call_next(request)
    if fault in {'banner', 'script'} and response.headers.get('content-type', '').startswith('text/html'):
        body = b''.join([chunk async for chunk in response.body_iterator]).decode()
        extra = ('<div class="banner err" data-error-code="fixture_failure" data-request-id="req-fixture">Fout</div>'
                 if fault == 'banner' else '<script>setTimeout(() => { throw new Error("fixture"); }, 200);</script>')
        body = body.replace('</body>', extra + '</body>')
        headers = {k: v for k, v in response.headers.items() if k.lower() != 'content-length'}
        return HTMLResponse(body, status_code=response.status_code, headers=headers)
    return response


@app.post('/browser-faults')
async def set_faults(request: Request):
    faults.clear()
    faults.update(await request.json())
    return JSONResponse(faults)


@app.get('/browser-manifest')
def manifest():
    return JSONResponse({'author': 'author', 'reviewer': 'reviewer', 'password': 'fixture-only'})


@app.get('/browser-domain-state')
def domain_state():
    # Every authority row except sign-in sessions must be identical before and after.
    owner = console.workflow_document_store
    connect = getattr(owner, '_metis_workflow_original_connect', owner._connect)
    rows = {}
    with connect() as con, con.cursor(row_factory=tuple_row) as cursor:
        tables = cursor.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN "
                                "('pg_catalog','information_schema') ORDER BY 1,2").fetchall()
        for schema, table in tables:
            if schema == 'workflow' and table in {'sessions', 'entra_sessions'}:
                continue
            rows[schema + '.' + table] = cursor.execute(sql.SQL('SELECT to_jsonb(t)::text FROM {}.{} t ORDER BY 1').format(
                sql.Identifier(schema), sql.Identifier(table))).fetchall()
    return JSONResponse({'sha256': sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()})
