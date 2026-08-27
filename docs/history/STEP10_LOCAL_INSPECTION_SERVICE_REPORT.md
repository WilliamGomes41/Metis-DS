# Step 10 - Local API and inspection interface

## Gate result

**PASS for local technical inspection.** This does not change the clinical/publication gate, which remains BLOCKED for the real Fractuurpreventie corpus until source verification and expert review are complete.

## What was built

A read-only FastAPI service and browser UI were added above the existing publication and hybrid-retrieval layers.

### Endpoints

- `GET /health`
- `GET /system/status`
- `GET /sources`
- `GET /documents`
- `GET /knowledge/{object_id}`
- `POST /search`
- `POST /retrieval/explain`
- `GET /releases`
- `GET /` - local browser inspector

### Safety modes

**REAL (default)**

- searches only `real_current_retrieval_records.jsonl`, which is derived from published objects;
- unpublished canonical objects cannot be fetched through `/knowledge/{id}`;
- current real corpus has 0 published objects and therefore retrieval abstains.

**FIXTURE (explicit only)**

- uses release id `SYNTHETIC-TEST-ONLY`;
- UI and API always expose a synthetic-data warning;
- fixture generation does not mutate canonical, approved, or publication state;
- intended only to inspect retrieval behavior before the expert validation is complete.

## Current runtime status

REAL:

- semantic objects: 21
- approved: 0
- high-risk requiring second review: 12
- verified canonical sources: 0
- published envelopes: 0
- retrieval records: 0
- pre-publication gate: BLOCKED
- search behavior: abstain (`empty_published_corpus`)

FIXTURE:

- synthetic retrieval records: 19
- test query about score from age 60: retrieve
- out-of-corpus morphine/renal-failure query: abstain

## Repository checks

- full test suite: **71 passed**
- HTTP runtime smoke: PASS in REAL and FIXTURE modes
- CLI `serve`: PASS
- browser root endpoint: HTTP 200
- regenerated synthetic fixture: 19 records, 0 blocked
- hybrid golden-set check remains 100% top-5 / 100% abstention on the development golden set (not an independent holdout claim)

During the step-10 full-suite gate, two stale repository-contract issues were repaired before release:

1. `canonical_source.source_id` was restored in `source_manifest.v2.json`;
2. `structured_logic` was restored as part of the deterministic retrieval projection and projection hash.

No step-10 API result bypasses the publication gate.

## Run locally

Install:

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
```

REAL mode:

```bash
vvn-data-service serve --mode real --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

Explicit synthetic demonstration:

```bash
vvn-data-service serve --mode fixture --host 127.0.0.1 --port 8000
```

Or:

```bash
VVN_SERVICE_MODE=fixture ./scripts/run_local_service.sh
```

## Docker

The image now defaults to the read-only REAL service:

```bash
docker build -t vvn-data-service:step10 .
docker run --rm -p 8000:8000 vvn-data-service:step10
```

Docker itself is not available in the current sandbox, so the Dockerfile could not be executed here. The same Uvicorn command used by the container was smoke-tested directly.

## What this step deliberately does not do

- no RAG answer generation;
- no chatbot model call;
- no Azure deployment;
- no automatic approval/publication;
- no production embeddings;
- no mutation endpoints.

The next engineering gate should be an independent retrieval holdout set and/or a real embedding-provider adapter. RAG should only be added after that retrieval acceptance gate.
