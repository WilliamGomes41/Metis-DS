# Step 9 - Hybrid retrieval and embedding-provider boundary

## Scope

This step adds two derived retrieval capabilities only. It does not modify canonical knowledge, validation state, publication state, or clinical content.

1. Hybrid retrieval using equal-weight Reciprocal Rank Fusion (RRF) over the existing lexical BM25 and local character TF-IDF vector engines.
2. A provider-neutral embedding contract plus a local deterministic adapter that exactly reproduces the step-8 vector baseline.

## Safety boundary

- Only published retrieval projections may be indexed.
- Child retrieval engines retain their own abstention gates.
- Hybrid abstains when all child engines abstain.
- Embedding/provider configuration contains no credentials.
- Unknown providers fail closed until a concrete audited adapter exists.
- The canonical knowledge store remains the source of truth; all indexes are disposable derivatives.

## Preliminary golden-set results

The same golden v0.1 set is used for direct comparison. Because child thresholds were previously calibrated on this set, the result is preliminary and is not an independent generalization estimate.

- lexical hit@5: 68.75%
- local vector hit@5: 93.75%
- hybrid RRF hit@5: 100.00%
- hybrid micro expected-object recall@5: 100.00%
- abstention accuracy: 100.00% (6/6 no-answer questions)
- content/logic preservation: 100.00% (24/24 checks)

No per-question fusion rules or golden-specific weights were introduced; RRF uses equal weights.

## Provider boundary

`EmbeddingProvider` defines fit, document embedding, query embedding and auditable provider metadata. The first implementation is `local-char-tfidf-v1`, used only as a deterministic adapter/test double. It is not a pretrained semantic model.

A future hosted embedding provider can be added behind this contract without changing canonical storage, publication gates, retrieval projections, or the hybrid fusion contract.

## Repository gate

`pytest.ini` now fixes the project root as the test import path. Full repository suite: 53 tests passed.

## Production status

The real corpus still contains zero published retrieval records. Both hybrid and provider-vector indexes therefore abstain on the real corpus and no production embeddings are generated.
