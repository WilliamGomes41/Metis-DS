# Attempt diagnostics and one-time recovery (#486)

Change class: A
Promise: Rejected preparation has durable attempt-owned evidence and precise validation findings; an authorized single recovery preserves prior work and attempt history.
Proof: tests/test_attempt_diagnostics_v1.py and tests/test_attempt_diagnostics_postgres.py; existing semantic, source-bound, retry, export and architecture regressions. Native PostgreSQL proof runs in CI, not in this local environment.
Touches lifecycle invariants: yes
Rewrite risk: none
Lifecycle entity: Existing unpublished WorkingRevision / workflow document and its processing attempts.
Lifecycle transition: Empty blocked preparation -> authorized one-time reservation -> blocked on failure or in_review on successful activation.
Initial durable state: Immutable source snapshot, blocked_pending_pre_review, empty object set, no bindings/review passes, exhausted four-attempt budget.
Trigger: Publisher submits a reason; researcher/reviewer subsequently submits the existing retry command.
Authorization: Active publisher role AND uploader/named-reviewer membership for grant; existing retry roles for execution; exact source hash/version and object revision at consumption.
Validation: Unpublished, blocked, empty, no existing review work, exhausted budget, no live running attempt, no earlier grant, no structural input/output-limit failure.
Mutable entities: Existing document envelope processing_attempts diagnostics and one processing_recovery grant; object activation only through the unchanged source verification/transaction gates.
Immutable entities: Source bytes/hash/version, previous completed attempts, published canonical objects, releases, registry and review decisions.
Workflow state before: blocked; reservation is processing and cannot publish.
Workflow state after: blocked on rejection; existing in_review behavior on preparation success.
Release state before: N/A: source may never have contributed to publication; published guard must reject grant/activation.
Release state after: N/A: no release decision in this feature.
Serving state before: Existing publication registry remains authoritative.
Serving state after: Unchanged: no serving writer is added.
Expected API result: Named reviewer diagnostics/export includes attempt evidence; read-only diagnostic replay returns rejected/validated/unavailable; grant POST redirects only after durable authorization.
Expected UI result: Blocked document displays candidate/reason; eligible publisher can authorize one recovery with a reason; existing retry button appears when allowed.
Failure result: No rejected objects admitted. Diagnostic checkpoint write failure stops preparation before further provider work. Reservation and authorization consumption share one transaction. Late inactive/expired worker cannot checkpoint or activate.
Restart result: Stored failed proposal, validator input/finding and grant consumption survive restart; no synthesized historical evidence.
Recovery result: One extra attempt consumes the grant atomically. Duplicate command returns its existing attempt; another command cannot reuse the grant.
Legacy-data result: Envelopes without diagnostics remain readable, export/replay says not_recorded/unavailable; no backfill or source re-upload.
Required black-box scenario: Given four failed empty attempts, authorized publisher grants recovery, two runtimes submit different retry commands, exactly one fifth attempt exists; after restart original four remain equal and grant points to fifth. Rejected model evidence replays exactly without provider calls or writes.
Explicit non-goals: No speculative strong/weak regex change, automatic label correction, relaxed validator, deletion/re-upload, automatic retries, review reset, publication changes or Azure deployment.

## Ownership and transaction boundary

The workflow-document payload remains the single authority for processing attempts. File compatibility storage uses the existing lock/reload/commit; PostgreSQL uses the existing advisory-lock/workflow transaction and document payload. No new database, migration, mirror or reconciliation writer.

Checkpoints are bounded diagnostic metadata on the running attempt. Activation compares all original workflow/source/attempt state except this non-authoritative metadata, then merges the latest stored diagnostics before committing success. State, actor, source hash/version, object revision, grant, bindings and publication guards retain their checks. Diagnostics are never inserted into `semantic_replay`, which remains validated-only.

Versioned diagnostic replay fingerprints validator dependencies and verifies both saved input and proposal hashes. It validates the semantic proposal only, without provider/parsing or downstream admission reruns. A provider abstention/invalid JSON/transport error therefore has recorded provider-stage evidence, but cannot claim a matching semantic rejection. Unavailable versions are reported instead of rerunning a historical input under new rules.

## Compatibility and recovery

Additive payload fields `diagnostic` and `processing_recovery`; export becomes v7 with explicit attempt-diagnostics and authorization datasets. Historical fields and canonical hashes unchanged. No SQL migration or destructive action. Old binaries ignore the additional metadata and still enforce the exhausted budget; do not grant while rolling back. Existing granted-but-unconsumed evidence survives, but only the new code understands its consumption. Grant is once per snapshot, bound to source/version/revision; changing revision invalidates execution rather than silently moving permission.

Evidence contains application request payload, designated output text, selected provider status/usage and native transport observation. HTTP headers, API keys, arbitrary response metadata/reasoning and exception prose are excluded. Access uses the existing named-reviewer diagnostics/export boundary. Evidence write failure cannot be made durable by the same failing store; its safe error code is propagated and logged through the existing processing failure path. Storage recovery must precede retry.

## Operator use

After deployment, open the document's technical diagnostics/export. For the historical smetten attempts the missing proposal cannot be recovered. An eligible publisher can grant a single new attempt with a reason. Run it once, then inspect `processing_attempts[-1].diagnostic.finding` and `attempt_diagnostics.csv`. Strength mismatch records proposed strength, observed literal value, exact evidence reference and reconstructed text. Invalid spans record their reference without invented text. A named reviewer may GET `/review/processing-diagnostic-replay?document=<snapshot>&attempt_id=<attempt>`; this has no admission or publication effect.

## Failure evidence matrix

| Scenario | Evidence / behavior |
| --- | --- |
| Strength/direction label mismatch | Candidate index, proposed value, recognized value, evidence offsets and reconstructed literal; exact read-only validator replay |
| Unknown/non-selectable block, bad offsets, duplicate/overlap, hidden-gap mapping | Exact validator subcode and selected reference; candidate input preserved; no invented text for invalid range |
| V2 field/context failure | Field name or context index plus proposed evidence reference; rejected candidate cannot enter Review |
| Invalid JSON / abstention / malformed proposal | Request and designated output saved before JSON/abstention/contract gates; absent semantic proposal is explicit |
| Connection/idle/total timeout, provider HTTP 429/5xx | Existing supervised transport category, HTTP status, limits, cancellation and retry cooldown retained on the failed attempt |
| Missing/changed source, extraction or activation failure | Exact safe exception code or explicit unknown category; last durable checkpoint identifies stage; previous objects remain protected |
| Persistence failure | No further model work after checkpoint failure; safe diagnostic-write error; no false claim of durable evidence |
| Expired/stale/concurrent/duplicate attempt | Existing active-attempt and revision guards; metadata cannot weaken state/hash/actor/publication comparisons |
| Budget exhausted | Ordinary four-attempt limit retained; source/revision-scoped grant consumed with fifth reservation, never reusable |
| Missing historic evidence / changed validator / corrupted diagnostic input | Replay unavailable with specific reason; no fallback to current model or altered validator |
| Excess diagnostic size | 16 MB bounded record; omitted evidence keys and availability `partial_limit`; no fabricated replacement |

Local compatibility adapter tests and unit tests do not substitute for native PostgreSQL restart/concurrency proof. The two native integration tests must pass in the existing Python 3.12/3.13 CI PostgreSQL jobs before merge.
