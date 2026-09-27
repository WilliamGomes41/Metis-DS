#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python -m src.build_synthetic_fixture \
  --input output/v2/fractuurpreventie_page15_semantic_v21.jsonl \
  --out output/v2/retrieval/baseline_fixture_records.jsonl \
  --report output/v2/retrieval/baseline_fixture_meta.json
python -m py_compile src/service_app.py src/cli.py src/build_synthetic_fixture.py
pytest -q
python - <<'PY'
from fastapi.testclient import TestClient
from src.service_app import create_app
real=TestClient(create_app('real'))
fixture=TestClient(create_app('fixture'))
assert real.get('/health').status_code == 200
assert real.post('/search',json={'query':'risicofactorenscore','top_k':5}).json()['behavior']=='abstain'
assert fixture.get('/system/status').json()['synthetic_fixture_mode'] is True
assert fixture.post('/search',json={'query':'Welke score geldt vanaf 60 jaar bij fractuurrisico?','top_k':5}).json()['behavior']=='retrieve'
assert fixture.post('/search',json={'query':'Wat is de aanbevolen dosering morfine bij nierfalen?','top_k':5}).json()['behavior']=='abstain'
print('STEP10_SERVICE_SMOKE=PASS')
PY
