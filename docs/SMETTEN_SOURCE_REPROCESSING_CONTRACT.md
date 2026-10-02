# Stored source recovery contract

Change class: A
Promise: An authorized retry of a blocked, unpublished, empty document uses the same immutable source and activates only a fully validated object bundle, or retains a durable specific failure without discarding prior work.
Proof: HTTP retry, duplicate/concurrent commands, interruption/restart and injected commit failure against native PostgreSQL; coordinate-bearing PDF fixtures and exact source round trips.
Touches lifecycle invariants: yes
Rewrite risk: high

## Domain and boundaries

The retry/recovery slice is Class A; its pure source-layout transform is Class B. Raw source bytes/hash and extracted raw text are immutable inputs. A versioned derived text view may omit only geometrically established layout markers, retaining raw offsets, coordinates and exclusion evidence. Recognition requires at least three consecutive markers increasing by five in a separate left margin, with exactly five distinct prose lines between adjacent markers on the same page. Cross-page, right-margin, table-like and uncertain sequences remain content. Hidden-gap validation still applies to all clinical text. Uncertain markers remain in the view with a finding. Labels, dosages, negations, scores and exceptions remain content.

The existing workflow PostgreSQL document envelope is the sole authority for retry attempts; no new database, table, background runner or console-local authority. Existing quality_processing_runs remains passive successful-candidate evidence. Failed attempts use a separate envelope field so latest-successful-run review provenance remains unchanged. Source bytes remain in immutable Blob; canonical publication and serving registry remain unchanged.

## Exact lifecycle slice

- Lifecycle entity: existing unpublished snapshot working bundle plus processing attempt.
- Lifecycle transition: blocked empty work -> reserved attempt -> validated captured work, or terminal failed/interrupted attempt with prior work intact.
- Initial durable state: PRE_REVIEW_BLOCKED; no knowledge objects or review bindings; same stored source hash.
- Trigger: POST /tree/reprocess with snapshot and unique command ID; existing direct reextract calls on a blocked snapshot use the same protected path.
- Authorization: existing researcher/reviewer role, checked at reservation and activation.
- Validation: source hash, publication authority, empty blocked work, expected object revision, attempt owner and unexpired reservation, existing semantics/admission checks.
- Mutable entities: attempt history and, on successful activation only, active envelope/object bundle.
- Immutable entities: source bytes/hash, original extraction records, terminal prior attempt records, published objects/releases, existing reviews.
- Workflow state before: blocked with no reviewable objects.
- Workflow state after: existing CAPTURED/eligible status with validated objects, or existing blocked status with specific terminal attempt outcome.
- Release state before: unchanged existing publication state.
- Release state after: unchanged; this operation cannot publish.
- Serving state before: unchanged existing serving state.
- Serving state after: unchanged; this operation cannot activate serving.
- Expected API result: receipt of succeeded duplicate, explicit already-running/conflict, or safe specific failure/reference.
- Expected UI result: existing retry action; diagnostics show durable attempt outcomes; redirect to review only after committed success.
- Failure result: prior source, objects and reviews remain unchanged; safely bounded error code/reference retained.
- Restart result: stored attempt history and active bundle survive process restart.
- Recovery result: expired reservation becomes interrupted on an explicit retry/recovery request; a new command may reserve another attempt. An expired worker cannot activate.
- Legacy-data result: missing attempt fields mean no attempts; historical missing diagnostics are not invented. Existing nonblocked reextract behavior remains outside this repair.
- Required black-box scenario: blocked stored source -> rejection -> restart -> same-command deduplication -> new successful retry -> review listing -> restart with same active revision.
- Explicit non-goals: publication, migration of WorkingRevision identities, replacement of existing knowledge/review work, provider payload retention, live reprocessing/deployment.

## High-risk mitigation

- Rewrite target: additive retry reservation/activation within existing document transaction boundary.
- Why local patching is insufficient: a UI flag cannot prevent duplicate workers or preserve failure evidence after restart.
- Current authority/writer/reader map: OperationsConsole.reextract_unpublished; /tree/reprocess; workflow document/review mixins and native PostgreSQL row locks; workflow_transaction; processing diagnostics/export; quality_processing_runs readers. Publication/reclassification/review writers keep existing checks and invalidate stale activation through envelope/revision comparison.
- Supported runtime topologies: existing single-instance PostgreSQL document/review runtime with multiple processes. Retry reservation additionally uses a PostgreSQL row lock, demonstrated with independent process-local roots; this does not expand support for other existing writers across multiple App Service instances. Filesystem-only compatibility fails closed for the new durable retry command; its ordinary legacy operations remain available.
- Persisted-state impact: additive processing_attempts and source-view evidence in existing JSON envelopes; no destructive schema change.
- Compatibility/migration plan: expand-only readers accepting absent fields; no startup rewriting; extractor/view versions distinguish new replay inputs. No reinterpretation of saved reviews.
- Rollback/recovery plan: revert command routing; retain additive attempt/evidence fields and existing active bundle; expiration permits explicit non-destructive recovery. Source/store unavailable leaves reservation recoverable, never falsely successful.
- Cutover trigger: tests pass; later authorized deployment of this branch.
- Cleanup/decommission criteria: no dual authority or temporary table introduced; retain diagnostics for snapshot lifetime pending an existing retention-policy change.
- Failure blast radius: one snapshot; never remove another snapshot's envelope or active objects.
- Adversarial proof matrix: missing/changed source, unauthorized/revoked actor, published snapshot, existing review work, same/different command, cross-process reservation, stale revision/envelope, expiry, worker crash, mid-activation database failure, restart, local fallback refusal, successful-response loss.

## Transaction and default policy

Acquire existing process-shared write lock, then native PostgreSQL document row lock in a shared workflow transaction. Reserve/expire an attempt atomically. Release locks before source I/O and provider calls. Activation rechecks current attempt, envelope and object revision inside the same transaction used for objects, envelope, bindings and audit/evidence. On failure, record only the bounded attempt outcome in a separate atomic operation; a dependency outage may postpone this until explicit recovery.

Default reservation lifetime: 30 minutes, explicitly recorded as an absolute expiry. This is an operational recovery bound, not an inferred historical timeout cause. It does not weaken provider or validation timeouts. Old successful candidate runs and reviews are never overwritten by failed retry history.

## Separate adversarial review

The review challenged the HTTP route, direct blocked reextract routing, the internal attempt-ID entry, inherited PostgreSQL document/review writers, immutable source cache recovery, shared transactions and filesystem fallback. An internal attempt ID now checks actor, source hash, original revision, active expiry and empty blocked work before provider work. Activation still checks publication, permissions, complete envelope and object revision under the database row lock. No separate active-attempt authority was added: attempt success and the resulting existing object bundle commit together, and the passive candidate run carries its attempt ID.

Native PostgreSQL tests cover an independent process with a separate runtime root, same/different command contention, preserved existing objects/review-pass evidence, role revocation, concurrent envelope/object/publication changes, corrupt source, timeout, crash/expiry, an expired old worker after successful recovery, and failure injected after actual SQL bundle writes. Restart checks prove the authoritative rollback and safe failure history. Geometry tests retain table-like adjacent numbered rows and unknown margins; transform tests reject forged raw mappings and hidden clinical gaps.

Remaining limits: this branch has fixture-based PDF evidence, not a complete run of the original 46-page Smetten PDF. The historical precise validator subcode/model response is unavailable and is not inferred from these changes. Filesystem-only durable retry is deliberately unsupported. Existing multi-instance App Service support is not expanded. No new interactive browser proof was performed for this branch; retry/diagnostics HTTP behavior is checked with ASGI TestClient and native PostgreSQL.
