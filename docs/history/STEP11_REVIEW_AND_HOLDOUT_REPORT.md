# Step 11 - Review completion and independent retrieval holdout

Date: 2026-08-19

## Clinical review completion

- First clinical review: 20/20 clinical objects approved.
- Technical document review: complete.
- Second review: 12/12 high-risk objects approved.
- Second reviewer: recorded in the controlled review audit store.
- Second-review snapshot mismatches: 0.
- Second-review errors: 0.
- Repository regression suite after review processing: 89 tests passed.

## Pre-publication status

Status remains `BLOCKED` for source-integrity reasons, not clinical-review reasons.

Remaining blocker classes:

- `source_checksum_not_in_verified_registry`
- `source_checksum_not_sha256`
- `source_fragment_coordinates_unavailable`
- `source_integrity_not_verified`
- `unresolved_uncertainty` on the document object

No objects are published while these blockers remain.

## Independent retrieval holdout

A new holdout was frozen before valid evaluation. The first file version (v1.0) contained five expectation-schema mismatches. No engine configuration was changed. A corrected v1.1 changed only those expected logic field/unit definitions; all question texts, expected object IDs and behavior labels remained unchanged. v1.1 was then locked before its valid evaluation.

Holdout v1.1 SHA-256:
`11070115f3491de8d040f4615f7b2b1facbcd5fd90c92ca8ee0318a60e0b0990`

### Unchanged-engine results

| Engine | Any expected object in top-5 | Abstention accuracy | Projection integrity |
|---|---:|---:|---:|
| Lexical | 27.78% | 100% | 100% |
| Local vector | 94.44% | 83.33% | 100% |
| Hybrid RRF | 94.44% | 83.33% | 100% |

Hybrid acceptance status: **FAIL**.

Observed failures:

1. False answer: `FP-H-N03` - "Hoe vaak moet een DXA-meting worden herhaald tijdens behandeling?" The vector child passed and hybrid returned results even though this answer is not present in the pilot corpus.
2. Retrieval miss: `FP-H-S02` - "Wat is het puntenaantal dat bij 70 jaar of ouder hoort?" Both child engines abstained even though the correct object is present.

## Engineering decision

Do not tune the current retrieval engine against this locked holdout. It remains an audit artifact. Any safety/retrieval change must be developed using development data and then evaluated on a new independent holdout, preferably from a second guideline/source.

The RAG/chatbot acceptance gate therefore remains closed. Product API and infrastructure work may continue, but the answer-generation layer must not be promoted to acceptance until a new independent retrieval holdout passes the required abstention criterion.
