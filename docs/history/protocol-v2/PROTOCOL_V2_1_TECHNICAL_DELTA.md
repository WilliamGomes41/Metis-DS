# V&VN Data Services Protocol v2.1 — Technical delta

Status: implemented in development retrieval path on 2026-08-19.

## Core rule

Retrieval similarity is not evidence of answerability. Candidate retrieval must be followed by a deterministic Answerability / Evidence Gate before results can be exposed as supported V&VN knowledge.

## Runtime path

```text
published retrieval projection
  -> lexical/vector/hybrid candidate retrieval
  -> query understanding
  -> linked evidence clustering
  -> concept coverage
  -> requested-relation coverage
  -> explicit numeric/operator constraint matching
  -> answerability decision
  -> supported results OR abstain
```

## Query specification

The gate derives, where applicable:

- intent
- required relations
- domain/content anchors
- explicit numeric constraints
- patient-specific context flag

Current deterministic relation classes include frequency, duration, dosage, score-points, score-threshold, diagnostic-threshold and recommendation.

## Evidence clustering

Knowledge objects may jointly support a question only when they are canonically linked through `context_object_ids` or `parent_object_id`. Arbitrary unrelated retrieval hits are not pooled into one evidence set.

## False-positive policy

The gate returns `abstain` when candidate retrieval succeeds but evidence is insufficient. Current classifications:

- `relation_mismatch`
- `numeric_confusion`
- `concept_overlap`
- `semantic_neighbor`
- `context_mismatch`
- `below_confidence_threshold`

A patient-specific diagnostic question is not treated as answerable by general guideline knowledge without patient context.

## API contract addition

`POST /v1/retrieve` now adds:

- `answerability`: `supported` or `insufficient_evidence`
- `false_positive_class`: nullable classification
- `reason`: explicit safe-retrieval decision reason

The `/v1` route remains unchanged. No generation/LLM is added.

## Acceptance discipline

The answerability rules were developed and tested only against the development/golden set and synthetic development queries. The locked independent holdout v1.1 was not reused for tuning or re-acceptance. A new independent holdout B, preferably on a second guideline, is required for independent acceptance.
