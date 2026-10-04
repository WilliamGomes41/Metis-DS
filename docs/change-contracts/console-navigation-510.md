# Console navigation — issue #510

Change class: B
Promise: Reduce redundant work on navigation while preserving current authorization and publication decisions.
Proof: One full readiness evaluation per publish card per request; batched explicit-policy review inputs with actor/tuple parity; isolated connection and statement timers; repository regression checks. Live two-second target remains a separate post-deployment measurement.
Touches lifecycle invariants: no
Rewrite risk: none

Read-only presentation change. Workflow PostgreSQL, canonical registry and
immutable source storage retain their authority. No schema, durable state,
mutation, publication eligibility or lifecycle rules change.

Before: document_status_ui evaluated full lifecycle/readiness for every publish
card; publish_readiness_ui repeated the same checks. Explicit-policy Review
summaries called review_work_item per document, loading objects/bindings/account
and potentially full publication readiness repeatedly.

After: Publish derives its heading from the readiness result required for its
action card. Canonical release/serving display still overrides the heading for
withdrawn/superseded/inactive releases. POST publish is unchanged and revalidates.
Review uses existing list lifecycle labels and existing object/binding batch
readers, then invokes the same review duty rules with exact-binding checks.
Inputs are scoped to the projection, never cached across requests or accounts.
Missing lifecycle input and storage failures remain errors. Temporary prefetch
context is restored before returning from the fallback list read.

Existing request telemetry additionally times attempted connection creation and
execute/executemany calls, including failures. The timers do not cover Azure
credential acquisition before connect, later cursor fetching/decoding, implicit
commit/rollback, source downloads or Python processing. Durations may overlap
when calls run concurrently; they are not a complete additive latency breakdown.
No SQL, parameters, credentials, raw URLs or document content are logged.

Start and Documenten already use bounded aggregate/batch paths; no observed
elapsed-time attribution justifies changing their connection lifecycle yet.
New timings apply to those requests too. No connection pool or global data cache
is introduced. Remaining latency, including background-work contention, needs
live measurements with the new timers before a further change is justified.

Rollback: previous application version; no migration or data repair required.
