# Step 12A — Retrieval Safety / Answerability Gate

Date: 2026-08-19
Status: DEVELOPMENT PASS; INDEPENDENT ACCEPTANCE PENDING

## Goal

Implement Protocol v2.1 so that semantic/lexical similarity can no longer by itself cause V&VN knowledge to be presented as answering a query.

## Implemented

- `src/answerability_gate_v1.py`
  - deterministic query understanding
  - relation requirements
  - domain/content anchor coverage
  - explicit numeric/operator constraint matching
  - patient-specific context abstention
  - false-positive classification
  - evidence clustering only across canonically linked objects
- `src/safe_retrieval_v1.py`
  - wraps existing hybrid retrieval
  - candidate retrieval remains unchanged
  - answerability gate determines supported vs abstain
- `src/evaluate_safe_retrieval.py`
  - development-only evaluator
  - explicitly not an independent acceptance evaluator
- `config/answerability_gate_v1.json`
- Product API v1 upgraded internally to safe retrieval (`product-api-v1.1.0`)
- Product API response now exposes `answerability` and `false_positive_class`
- `tests/test_answerability_gate_v1.py`

## Development evaluation

Dataset: existing 19-record synthetic published fixture used by the Product API.
Golden set: `fractuurpreventie-page15-golden-v0.1`.

Results:

- retrieve questions: 16
- expected-object hit@5: 100%
- no-answer questions: 6
- abstention accuracy: 100%
- False Answer Rate: 0%

These are development metrics and may not be presented as independent validation.

## API smoke tests

Supported development query:

- status: `retrieve`
- answerability: `supported`
- one exact score-rule object returned

Unsupported relation query:

- candidate retrieval found semantically relevant material
- answerability gate returned `abstain`
- reason: `required_relation_not_present`
- false-positive class: `relation_mismatch`
- zero objects exposed as supported evidence

## Regression

Full repository suite: 100/100 tests passed.

Targeted safety/API coverage: 87% overall (Answerability Gate 85%, Product API 90%).

## Important acceptance status

The locked independent holdout v1.1 remains historical `FAIL`. It was not used to tune this implementation and was not rerun to claim success. Independent retrieval acceptance requires a new holdout B, preferably after adding a second guideline/source.

## Remaining blockers

1. Source integrity for Fractuurpreventie remains blocked until the official canonical source binary is locally verified and raw source coordinates are regenerated.
2. Independent retrieval acceptance remains pending until holdout B.
3. RAG / Answer API acceptance remains blocked until source integrity and independent retrieval/answerability acceptance pass.
