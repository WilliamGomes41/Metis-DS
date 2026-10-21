# Console navigation performance — issue #490

Change class: B
Promise: Correct authorized task counts without repeated review/publication evaluation or per-passage database reads.
Proof: Semantic parity scenarios, bounded batched reads, isolated request telemetry, reproducible synthetic benchmark; final page timing after deployment.
Touches lifecycle invariants: no
Rewrite risk: none

This is a stateless read optimization. Workflow PostgreSQL remains document,
identity and review authority; canonical PostgreSQL remains release/serving
authority; Blob remains source authority. No migrations, state transitions,
authorization policy, publication gates, recovery or durable schema change.

Existing path: routes call `waiting_task_counts`; explicit-policy documents
invoke workboard summaries, enriched policy work items, then work items again.
Each item can call lifecycle/readiness/publication gates and repeatedly load and
copy object payloads. Summary enrichment and item reconstruction duplicate work.

The navigation projection needs actionable review/disposition/repair work and
whether publication history closed the revision. It does not need to distinguish
publication-blocked from complete when neither contributes to the review badge.
Canonical release rows close revisions even with stale pending objects; envelope
publication flags must not manufacture canonical history. The existing pure
review duty, follow-up, exact-binding, participant and decision-graph functions
remain shared with detailed Review. Full lifecycle/readiness stays on existing
detail and publication paths. Normal workboard items reuse summary enrichment.

Inputs are allocated per call: one assigned-summary query, one canonical release
batch, one current-object batch and one scoped binding batch. Only explicit,
unclosed assigned documents require object/binding materialization. There is no
cross-request cache, TTL, retained payload or new authoritative projection.
Existing defensive copies at command/store boundaries remain unchanged. Current
object versions preserve the prior position-based latest-version/order rule.

The participant projections never write durable state. Existing independent-read
transaction semantics remain unchanged; this is not an atomic multi-authority
snapshot. Failures must remain failures, never fictional zero work. SQL binding
payload verification is retained; absent/stale tuple approvals remain invalid.

Metrics are disposable operation counters, not domain audit or evidence. Their
scope is reset in `finally`; copied thread contexts share only the owning request
counter. Logs contain matched route templates, status, elapsed/badge milliseconds
and attempted application connections/statement calls. `executemany` counts one
statement call, not individual batch rows. Implicit transaction/protocol messages
are not counted. No SQL/parameters, raw URLs, account identifiers, payloads or
credentials are logged. Diagnostic logging failures do not change HTTP results.

Regression proof covers exact first/second reviews and waiting, disposition,
repair, failed pre-review, canonical closure states, changed approvals between
calls, account separation, constant input reads as passages grow, object version
order, operational error privacy and overlapping async/thread metric contexts.
Native PostgreSQL integration and full repository checks remain required.

Rollback: deploy the previous application version. No durable migration or
state repair is involved. Keep the Azure monitoring agent disabled; no dependency
or infrastructure workaround belongs to this change.
