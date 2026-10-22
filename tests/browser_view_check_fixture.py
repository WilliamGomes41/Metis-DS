"""Real PG production app, synthetic source/model and private evidence transport."""
from tests.semantic_fixture_support import bind_fixture_selections
import os
import json
from hashlib import sha256

from psycopg import sql
from psycopg.rows import tuple_row

from fastapi.responses import JSONResponse

from tests.browser_postgres_support import browser_application
from tests.test_availability_repair import accounts, bind, provider
from tests.test_azure_source_processing import ImmutableBlobFixture
from tests.test_view_check_postgres import configure
from tests.test_source_context_review_v1 import _system

app = browser_application('view-check-browser', processing_binder=bind_fixture_selections,
                          immutable_source_store=ImmutableBlobFixture())
console = app.state.operations_kernel
author, reviewer = accounts(console)


def mixed_provider(url, headers, payload, timeout):
    data = json.loads(payload['input'][1]['content'])
    if any('systematische waarneming' in row['text'] for row in data['source_blocks']):
        block = next(row for row in data['source_blocks'] if 'systematische waarneming' in row['text'])
        proposal = {'objects': [{'spans': [{'block_id': block['block_id'], 'start': 0, 'end': len(block['text'])}],
                                'proposed_object_type': 'definition', 'recommendation_semantics': None}],
                    'relations': [], 'abstain_reason': None}
        return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(proposal)}]}]}
    return provider(url, headers, payload, timeout)


bind(console, mixed_provider)
receipt = console.ingest(actor_id=author, filename='fixture.html', content_type='text/html',
    data=b'<html><body><p>Gebruik geen zalf.</p></body></html>', ingest_kind='new',
    title='Single passage', version='1', date='2026-10-21', live_url='',
    class_='richtlijn', family='fixture', named_reviewers=[reviewer])
_, _, source_reviewer, _, _, command = _system(console.runtime / 'mixed-source', console=console)
configure(app, console, None, console.runtime / 'private-test-evidence',
          origin=os.environ['METIS_BROWSER_BASE'], module=os.environ['METIS_PLAYWRIGHT_MODULE'],
          browser=os.environ['METIS_BROWSER_EXECUTABLE'])


@app.get('/browser-manifest')
def manifest():
    return JSONResponse({'document': receipt['snapshot_id'], 'source_document': command['snapshot_id'],
                         'source_reviewer': source_reviewer['username']})


@app.get('/browser-domain-state')
def domain_state():
    # Compare native authority rows, including source/review/publication state.
    # Browser login may create sessions; only the operational job may change.
    rows = {}
    with app.state.view_checks.store.connect() as con, con.cursor(row_factory=tuple_row) as cursor:
        tables = cursor.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2").fetchall()
        for schema, table in tables:
            if schema == 'workflow' and table in {'sessions', 'entra_sessions', 'view_checks'}:
                continue
            rows[schema+'.'+table] = cursor.execute(sql.SQL('SELECT to_jsonb(t)::text FROM {}.{} t ORDER BY 1').format(
                sql.Identifier(schema), sql.Identifier(table))).fetchall()
    return JSONResponse({'sha256': sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()})
