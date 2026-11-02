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

## First-head CI findings and correction

The first head's topology run passed464 cases and failed an obsolete assertion
requiring exactly one global envelope reload. The retarget now requires **zero**
global reloads, exactly one actual command-window capture at both k1/k2 inside
the native transaction, durable selected approvals and unchanged unselected
objects. All12 original command-owner cases pass, including native authority,
no-mirror, nested failure and recovery contracts.

Full CI also found a real legacy-source GET regression: current-only heading
rendering unnecessarily prepared three source views. The structure caller now
opts out of content-view materialisation while retaining verified raw fragments,
current objects/bindings/GEN and the original eligibility owner. Every other
caller retains the original default. The existing zero-reconstruction and exact
HTML assertions are unchanged. Complete source-render/reuse and final batch
measurement36 pass; max20 HTTP1.596s/hold171.996ms/TX171.965ms, heading1500
181.329ms/hold76.236ms. No budget changed.

The heading UI test still expected its old full capture/m2 token. It now asserts
one actual current-window capture, no old full reader, and GEN resolving to the
same captured legacy revision. Original selected membership, stale refusal,
outsider denial, immutable publication presentation/command simulation, submit,
refresh and independent process-restart assertions remain. The publication UI
simulation supplies both cached presentation and the current canonical-owner
read; real canonical-commit/projection-failure refusal is proved separately by
the native prepared-batch test. This UI test passes. No production publication
claim follows from its simulation. Final CI is tied to the follow-up head.

The remaining first-head full-suite logs exposed two more old test seams. The
hotpath test now counts one real current-window read for only the selected
snapshot and explicitly zero full API/object reads, preserving the same read
ceiling. The direct-workspace test double explicitly accepts current_only and
checks False for contextual / True for batch, retaining exact document, input,
render and backlink assertions. Both full modules21 pass. Independent inspection
found no weakened behavior. This final adapter repair changes no runtime code;
the20 final runtime hashes and measured batch budgets remain unchanged. New
exact-head CI still owns the full-suite outcome.
