# #729 / MET-36 — W1 complete source resolution

Change class: A. Rewrite risk: high.
Base: `c4db3bd84bfe722ab235eff67d2ccf69b60a785b`.
William authorized W1 implementation on 7 November 2026. Existing project and
issue remain owners; merge and deployment remain separate decisions.

Promise: `/review/resolve` source-units correction prepares the complete repair
outside the outer write lock and transaction, then commits the successor,
binding invalidation, derived facts, discrepancy evidence and repair audit as
one native operation. The current audit recorded 20/20 correction POSTs above
5 seconds (median 6.075s), 1,087 queries and about 260 MB decoded JSON per POST.
Budget: POST 3s, outer lock 250ms, transaction 500ms; measure the whole user
action separately against 5s. Local timings do not establish production latency.

## Lifecycle transition and proof

Lifecycle entity: existing unpublished WorkingRevision of one SourceSnapshot.
Initial durable state: native objects and retained history, bindings, source
extraction, participant/policy configuration and review ledger.
Trigger: named reviewer submits selected source units with an exact object-set
revision. Authorization: current reviewer role, identity, retirement and roster.
Validation: original repair selection, immutable-source verification,
materialisation, admission and revision kernels; exact submitted revision.
Mutable entities: permitted successor of the target, invalidated target bindings,
derived facts and audit/evidence for the original and resulting versions.
Immutable entities: source bytes/identity, retained versions, canonical releases.
Workflow before: existing in-review/blocked working state. Workflow after: target
`needs_review`; repair grants neither approval nor publication readiness.
Release and serving before/after: unchanged; canonical publication registry
remains the sole serving authority. Live v1 may coexist with working v2; this
operation cannot supersede, withdraw, republish or reopen a sealed revision.
API/UI result: existing 303 on success, existing conflict/refusal on invalid or
stale input, with unchanged target and destination. No UI change.
Failure result: all workflow participants roll back, including late SQL COMMIT
failure. Concurrent committed state is preserved. Duplicate submitted revision
is stale after successful repair; no new idempotency claim.
Restart/recovery result: fresh production composition reads the same committed
successor and evidence or unchanged state; discarded preparation is not durable.
Legacy-data result: unprepared histories and nested commands retain the existing
serial path. Exact m2 object-set semantics are not replaced by a generation token.
Required black-box scenario: real HTTP repair, independent restarted readback,
stale replay, competing current-input change before commit and final-participant
failure; neither partial evidence nor publication escalation may survive.

## Rewrite mitigation and existing mechanism

Rewrite target: outer source-resolution integration with the existing prepared
Review executor. Why local patching is insufficient: accelerating only inner
`correct_object` leaves the outer transaction and subsequent evidence writes.
Call path: HTTP -> ReviewClosure -> DeterministicRepairReviewConsole ->
`OperationsConsole.correct_object` -> existing workflow document/review owners.
Reuse `review_command_v1`, its request-local immutable inputs and current guard,
and the original repair kernel; no second candidate creator or commit framework.

Current authority/writer/reader map:

| Truth | Owner, writers and readers |
|---|---|
| Source | Immutable source store; ingest/reprocessing activation writes; original source reader validates repair units and extraction identity |
| Objects/history | Workflow document store; existing processing, review, correction and structure commands write; original materialisation/admission/revision kernels consume selected current dependencies |
| Actor/policy/roster | Existing identity and document owners; account and participant commands write; capture and locked commit guard read current authority |
| Bindings/evidence | Review store and ledger; original repair/review commands write in the existing native transaction; closure/readiness reads committed data |
| Derived facts/frontiers | Document owner maintains these with object writes; no independent decision or candidate authority |
| Release/serving | Canonical publication store and registry; existing publication/recovery/withdrawal writers only; repair retains mutable-working guard |

Supported runtime topologies: both production PostgreSQL console compositions,
independent processes and file-lock paths, fresh runtime and retained legacy
histories. No filesystem substitute for PostgreSQL.
Persisted-state impact: none; same rows, schema, event types and source identity.
Compatibility/migration plan: additive prepared ingress with explicit existing
serial fallback; one authoritative kernel, no dual writes or data migration.
Rollback/recovery plan: revert binary; ordinary committed state remains readable.
Cutover trigger: native red/green, current-dependency, rollback/restart and
performance evidence, followed by human merge/deploy decision.
Cleanup/decommission criteria: no duplicated kernel or new compatibility layer;
legacy fallback remains until its existing preparation contract is met.
Failure blast radius: source-units repair and shared prepared executor; direct
researcher correction, other repair kinds, ordinary review and batches retain
their contracts and receive relevant regression coverage.
Adversarial proof matrix: stale whole-set token including unrelated objects;
actor/roster/policy/source/binding changes; uncaptured admission dependencies;
legacy/unprepared and nested execution; sealed working revision; final audit and
late commit faults; independently reconstructed durable state; shared review and
batch regressions. Separate adversarial review before PR.

Non-goals: timeout increases, new schema/token/authority, weaker source or
publication gates, provider/model changes, UI redesign or W2–W6 implementation.

## Verification record

Before implementation: existing native HTTP/restart test passed (2 tests) on
Python 3.13.5/PostgreSQL 17.11. This environment has PG17, not the PG16 launcher
default; `scripts/test_postgres.sh` verified the supplied local test server.
The new regression must fail before production edits and be committed separately.
