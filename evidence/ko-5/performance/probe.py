"""Fresh process cold build_app, followed by ordinary authenticated card reads."""
import time
START = time.perf_counter()
import sys, os, json, logging, math, subprocess
from pathlib import Path
checkout, side, round_id, expected_sha = sys.argv[1:]
sys.path.insert(0, checkout)
from tests.production_support import production_application
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from fastapi.testclient import TestClient
from src.request_diagnostics_v1 import _LOGGER

OUT = Path('/workspace/ko5-perf-final-evidence')
config = json.loads((OUT/'fixture.json').read_text())
# Runtime copies and DB state are isolated by side; both derive from same fixture.
app = production_application(OUT/f'runtime-{side}', PostgresCanonicalConfig(dsn=config[f'{side}_dsn']),
    source_store=Path(config['root'])/'sources')
cold_ms = (time.perf_counter()-START)*1000
actual_sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()
assert actual_sha == expected_sha, (actual_sha,expected_sha)
client = TestClient(app, base_url='https://testserver', raise_server_exceptions=False)
login = client.post('/login',data={'username':'reviewer','password':'fixture-only'},headers={'origin':'https://testserver'},follow_redirects=False)
assert login.status_code in (302,303), login.status_code
url = f"/review?document={config['snapshot_id']}&object={config['object_id']}&task=individual"
seen=[]
class Capture(logging.Handler):
    def emit(self,record):
        msg=record.getMessage()
        if msg.startswith('metis_diagnostic '):
            seen.append(json.loads(msg[len('metis_diagnostic '):]))
handler=Capture()
_LOGGER.addHandler(handler)
rows=[]
for index in range(21):
    seen.clear()
    started=time.perf_counter()
    response=client.get(url)
    wall_ms=(time.perf_counter()-started)*1000
    assert response.status_code==200,(response.status_code,response.text[:1000])
    assert config['object_id'] in response.text, 'ordinary candidate absent'
    diagnostics=[row for row in seen if row.get('event')=='request_finished']
    assert diagnostics,seen
    row=diagnostics[-1]
    assert isinstance(row.get('elapsed_ms'),(float,int)),row
    if index:
        rows.append({'index':index,'wall_ms':wall_ms,'server_ms':row['elapsed_ms'],'db':row.get('db'),
            'counters':row.get('counters'), 'response_bytes':len(response.content),'status':response.status_code})
_LOGGER.removeHandler(handler)
receipt={'side':side,'round':int(round_id),'sha':actual_sha,'cold_ms':cold_ms,'card':rows,
    'url':url,'metric':'ordinary card GET; actual build_app startup','pid':os.getpid()}
(OUT/f'{side}-{round_id}.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps({'cold_ms':cold_ms,'server_p95_ms':sorted(r['server_ms'] for r in rows)[18]}))
