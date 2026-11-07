"""Create only this lane's synthetic native fixture; never connect to production."""
import json, os, sys
from pathlib import Path
import psycopg
from psycopg import sql

BASE = Path('/workspace/Metis-ko5-base')
OUT = Path('/workspace/ko5-perf-final-evidence')
sys.path.insert(0, str(BASE))
from tests.postgres_support import install_schema
from tests.production_support import production_application
from tests.semantic_fixture_support import bind_fixture_selections
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig

name = 'ko5_perf_final_fixture_v1'
dsn = 'postgresql://postgres@127.0.0.1:55440/' + name
with psycopg.connect('postgresql://postgres@127.0.0.1:55440/postgres', autocommit=True) as admin:
    admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(name)))
install_schema(dsn)
app = production_application(OUT/'fixture', PostgresCanonicalConfig(dsn=dsn), processing_binder=bind_fixture_selections)
console = app.state.operations_kernel
author = console.create_account(username='author', password='fixture-only', roles=('researcher',))
reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
texts = [f'Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg. De verpleegkundige legt waarneming {i} vast.' for i in range(923)]
bind_fixture_selections(console, [(text, 'definition') for text in texts[::10][:92]])
sid = console.ingest(actor_id=author['account_id'], filename='source.html', content_type='text/html',
    data=('<html><body><h1>Richtlijn</h1>'+''.join(f'<p>{t}</p>' for t in texts)+'</body></html>').encode(),
    ingest_kind='new', title='KO5 synthetic performance', version='1.0', date='2026-11-07', live_url='',
    class_='richtlijn', family='ko5-perf', named_reviewers=[reviewer['account_id']])['snapshot_id']
objects = console.snapshot_objects(sid)
obj = next(row for row in objects if row.get('object_type') not in {'document','heading'} and row.get('proposed_object_type')!='heading')
with psycopg.connect(dsn) as con:
    version = con.execute('SELECT version()').fetchone()[0]
manifest = {'dsn':dsn, 'database':name, 'snapshot_id':sid, 'object_id':obj['object_id'], 'objects':len(objects),
    'root':str(OUT/'fixture'), 'postgres':version, 'baseline_sha':'07db5080666f0428a454f5a705e50825a4fc5506'}
(OUT/'fixture.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest))
