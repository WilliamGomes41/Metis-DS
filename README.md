# Metis V&VN Data Services

Technical pilot for converting V&VN source knowledge into deterministic, versioned, reviewed and publishable knowledge objects.

## Safety model

The canonical knowledge layer is the truth. Retrieval projections, embeddings, APIs and chatbots are derived and disposable.

Publication is fail-closed. An object cannot be published unless the source binary has been cryptographically verified, the exact canonical object version has been reviewed, high-risk fields have passed four-eyes review, provenance resolves to raw source fragments, and schema/hash checks pass.

## Current state

The Fractuurpreventie pilot source binary is not locally available, so the real publication gate is expected to remain `BLOCKED`. This is a valid safety state.

## Documentation

The repository root is the operating surface. Read current work in this order:

`PROTOCOL.md` → `ROADMAP.md` → `HANDOFF.md` → tests → code

- `docs/` — current protocol and technical documentation
- `docs/history/` — historical step, audit and repair reports; not steering documents
- `docs/REPOSITORY_CONVENTIONS.md` — directory contract

## Reproduce

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
pytest -q
vvn-data-service audit-current
```

## Docker

```bash
docker build -t vvn-data-service:pilot .
docker run --rm vvn-data-service:pilot
```

## Main CLI

```bash
vvn-data-service audit-current
vvn-data-service review-queue --input <objects.jsonl> --track clinical --out <queue.jsonl>
vvn-data-service source-register --source-id <id> --binary <file.pdf> --source-url <url> --out <registry.json>
vvn-data-service source-bind --manifest data/source_manifest.v2.json --source-registry <registry.json> --out <verified-manifest.json>
vvn-data-service prepublish --input <reviewed.jsonl> --schema schemas/knowledge_object.schema.v1.1.json --source-registry <registry.json> --raw-extract <raw.jsonl>
vvn-data-service serve-console --host 127.0.0.1 --port 8090
```

The researcher path for Continentie (bron 2) is the operations console mailbox, not a parallel engineer-only ingest UX. Existing CLI extract/register tools remain for engineers and tests. Capture is not publication; G2 remains BLOCKED.
## Protocol v2.1 safe retrieval

The Product API uses `SafeRetrievalIndex`: hybrid search produces candidates, after which a deterministic Answerability/Evidence Gate checks concept coverage, requested relations and explicit numeric constraints. A high similarity score alone never establishes answerability.

`POST /v1/retrieve` returns `answerability=supported` only when the evidence gate passes; otherwise it returns `status=abstain` with an explicit reason.

Current v2.1 development metrics: 100% expected-object hit@5, 100% no-answer abstention, FAR 0% on the development/golden set. Independent acceptance is still pending a new holdout B.


## Source 2 / generic HTML factory (Step 12B)

Protocol v2.1 now supports source-neutral HTML ingestion for locally supplied source files:

```bash
vvn-data-service extract-html \
  --input <source.html> \
  --document-id <document-id> \
  --source-id <source-id> \
  --out <raw.jsonl>

vvn-data-service semantic-generic \
  --spec <semantic-spec.json> \
  --manifest <source-manifest.json> \
  --raw <raw.jsonl> \
  --out <canonical.jsonl>
```

HTML uses schema `raw_fragment.schema.v1.1.json` and canonical knowledge schema
`knowledge_object.schema.v1.2.json`, adding source-neutral locators without changing
the existing PDF v1.1 contract.

The second real source selected for onboarding is **Continentie bij (kwetsbare) ouderen**.
Its manifest is present at `data/source_manifest.continentie.v1.json`. Publication and
holdout-B creation remain fail-closed until the exact source HTML or official generated
PDF is available locally and can be SHA-256 verified.
