# Prepared batch: independent review and evidence boundaries

Change class A; rewrite risk high. The architecture and change contract remain
`docs/architecture/bounded-review-mutations-729.md` and
`docs/change-contracts/729-bounded-revision-inputs.md`.

The independent runner inspected the actual prepared command, native store,
ledger intent owner, immutable handle, bulk writes and tests. It did not execute
the owner's native measurements or approve deployment. Local execution results
are separate in [batch-results.json](batch-results.json); counts overlap.

## Findings and corrections

- Python binding equality could miss typed metadata1→1.0. Both current-baseline
  comparison and renewal decision now use exact JSON; native typed update and
  stale-baseline negatives cover this.
- Checking only that a transaction was active missed an outer buffer created
  before that transaction. Buffers now record the actual creating connection;
  Review requires that same transaction before mutation. Empty/nonempty,
  wrong-order refusal, correct join commit/abort and ledger-only compatibility
  have separate native proofs.
- Audit set insertion initially checked only part of its relational projection.
  It now returns and compares every indexed event field, payload, hash and
  event-ID order. A real BEFORE trigger changing event_type alone must refuse.
- A frontier hash-only reread could accept NULL/NULL after an AFTER-trigger
  object edit invalidated a newly installed certificate. The final reread now
  checks exact complete certificate/epoch/coverage/hash. Native second-member
  suppression/rewrite/hash corruption and late object mutation must roll back.

The owner also corrected quality-input lookup that still fetched the complete
legacy envelope inside the protected transaction. Actual ordinary POST and
quality projection tests now prohibit that client-side load. Server-side legacy
quality selection still exists until its own input preparation; no global claim
that all legacy envelope work disappeared is made.

The original max20 preparation still held the lock1.776s. Moving the original
kernel and ordered validation outside the lock cut that cost substantially, but
one later hold261.7ms still failed250ms. That failure prompted actual query
profiling and ordered set audit/frontier writes. Budgets and current guards were
not weakened. Final timing and fault outcomes are recorded in the linked JSON.

## Accepted scope and limits

The prepared normal-risk and heading batch path is selected by explicit GEN and
owner-issued prepared032 inputs. Public GEN stays document-wide. m2/None,
legacy/unprepared data and existing native transaction joins preserve serial
compatibility. No durable preparation job, new event format or scoped public
revision token is introduced. Independent audit/document advancement can append
under the ledger owner; changed semantic input still refuses the preparation.

Canonical publication remains authoritative even after workflow projection
failure. Actual canonical-commit/window tests cover that refusal. There is no
retry that silently rebases a user's decision. Current selection recovery is
retained; the separately proposed full conflict UX is outside this slice.

The runtime/source hashes bind these results to inspectable code. Exact-head CI
and real existing-data open/save/reopen/stale/publication-refusal proof remain
separate. No automatic merge, production preparation or deployment is performed.
