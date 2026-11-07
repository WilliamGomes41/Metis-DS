"""Separate untimed response capture; frozen perf files are never changed."""
import json, subprocess, sys
from pathlib import Path
checkout,side,sha=sys.argv[1:]
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()==sha
sys.path.insert(0,checkout)
from tests.production_support import production_application
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from fastapi.testclient import TestClient
out=Path('/workspace/ko5-perf-final-evidence')
config=json.loads((out/'fixture.json').read_text())
app=production_application(out/f'runtime-{side}',PostgresCanonicalConfig(dsn=config[f'{side}_dsn']),
                           source_store=Path(config['root'])/'sources')
client=TestClient(app,base_url='https://testserver',raise_server_exceptions=False)
login=client.post('/login',data={'username':'reviewer','password':'fixture-only'},
                  headers={'origin':'https://testserver'},follow_redirects=False)
assert login.status_code in (302,303)
url=f"/review?document={config['snapshot_id']}&object={config['object_id']}&task=individual"
response=client.get(url)
assert response.status_code==200,response.status_code
(out/f'view-{side}.html').write_text(response.text)
(out/f'view-{side}-capture.json').write_text(json.dumps({'untimed':True,'sha':sha,'checkout':checkout,
    'side':side,'status':response.status_code,'url':url,'object_id':config['object_id'],
    'snapshot_id':config['snapshot_id'],'purpose':'DOM view confirmation only; no new performance metric'},indent=2))
