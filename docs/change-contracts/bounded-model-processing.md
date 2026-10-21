# Bounded, recoverable source model processing

Reference: PR #485 head 46ebe41f5bf88ef2a633c48b08133358036879eb.
Change class: A
Promise: An unavailable/stalled model cannot hold local processing indefinitely; only the current, unexpired attempt can atomically activate its complete source-bound result.
Proof: Controlled transport server (no response/drip/late response/success), killed worker/restart, native PostgreSQL duplicate/concurrent/stale/rollback tests and shared CLI/console projection.
Touches lifecycle invariants: yes
Rewrite risk: high

## Inspection before implementation
Established: `_provider_proposal` checks elapsed monotonic time only after synchronous `_post_json` returns. urllib `urlopen(timeout=180)` bounds individual socket operations; `read` can keep receiving bytes indefinitely. There is no provider cancellation operation or SDK retry. `processing_retry_v1` already owns command/attempt IDs, running/failed/interrupted/succeeded, a 30-minute UTC lease and activation guard in the document envelope. PostgreSQL row lock + existing shared store lock serialize reserve/activate against other writers. First ingest persists only after preparation, so process death before that loses the durable processing intent. Direct unreviewed reextract has CAS but no attempt reservation. Model work is already outside write transactions. Existing source/review/publication boundaries must stay.
Risk: trickle responses evade a post-call check; initial model preparation is not recoverable after process death; a thread wait timeout would orphan an unbounded request; failure projection currently uses initial blocker rather than latest attempt. Local compatibility deliberately refuses retry today.
Inference: No measured latency distribution or provider-specific SLA is recorded. OpenAI's official Python client documents a 10-minute default request timeout (https://github.com/openai/openai-python#timeouts); this is a comparison point, not a provider SLA. Non-streaming Responses can legitimately be silent while generating. A short idle bound would penalize large documents.
Required change: keep urllib but supervise its blocking DNS/connect/read in one disposable transport subprocess, with phase/byte observations and actual termination/reaping; reuse attempts for initial semantic preparation and explicit reextract; revalidate lease/monotonic deadline/source/revision/owner immediately before activation. No thread executor or second job authority.
Do not change yet: source layout, chunking, extraction route, prompt/object/review semantics, provider background API/cancellation, publication identities, Azure settings/deployment.

## Statefulness and ownership -> semantics -> invariants
The existing kernel application service owns the durable source snapshot, working object bundle and processing_attempts; PostgreSQL remains production authority. Console/CLI only request commands/read a shared projection. Transport process/anonymous descriptors are disposable observations, never durable workflow truth.
Document/source and previously valid knowledge/reviews/publications remain immutable inputs. A processing command is identified by its existing command ID. Each reserved attempt identifies actor, source/version and expected object revision. One external model call occurs per attempt at most; exact replay may need none. A prepared result is inactive until the existing commit activates it with terminal success. No new state machine/store/jobmanager.
Hard invariants: at most one running attempt per source; expired/replaced/cancelled attempts cannot activate; duplicate command cannot activate twice; timeout/failure preserves prior objects/reviews/publications; no automatic extraction fallback or truncation; model call outside DB transaction; successful result + evidence + attempt state commit together; transport activity is never semantic progress; external cancellation/cost cessation is never claimed without confirmation.
Policy: explicit manual retries only, maximum four reserved attempts under the new policy (initial plus up to three retries). Old records remain readable and count conservatively. No automatic provider retries/backoff. Input/output bounds from #485 remain 2MB/4MB, with explicit errors. Raising time limits does not make >2MB requests supported.

## Lifecycle and transaction boundary
Lifecycle entity: existing WorkingRevision/source processing attempt.
Lifecycle transition: source captured/blocked or explicitly reextractable unreviewed work -> durable running reservation -> succeeded with new complete active bundle, or failed/interrupted retaining prior work.
Initial durable state: immutable source and prior bundle; first semantic ingest records the source envelope and running attempt before calling the provider.
Trigger: authorized ingest, existing explicit reextract or retry command.
Authorization: researcher/reviewer guards at reservation and activation; curated/reviewed/published work cannot be replaced by retry.
Validation: source checksum/version, expected object revision, same running attempt/actor, no replacement/cancellation, UTC lease and same-process monotonic deadline.
Mutable entities: additive attempt records, new prepared result on successful commit only.
Immutable entities: source bytes; prior object versions/reviews/publications and hashes.
Workflow state before: preparation incomplete or existing unreviewed work.
Workflow state after: existing review eligibility on success; original active work retained and specific failure on failure.
Release state before: existing publication registry.
Release state after: unchanged.
Serving state before: existing serving registry.
Serving state after: unchanged.
Expected API result: same receipt or safe classified error; durable status projection shared by CLI and console.
Expected UI result: running/expired/failed/succeeded from stored attempts, actual failure category and whether/when manual retry is possible.
Failure result: bounded local termination; only safe metadata retained; no active partial bundle.
Restart result: terminal attempt/result unchanged; orphan running reservation visible as expired when lease passes.
Recovery result: explicit existing reserve marks expired attempts interrupted and reserves a new bounded attempt; no destructive reset.
Legacy-data result: absent limits/attempts mean not recorded, no backfill; v1 attempt records remain readable.
Required black-box scenario: persisted running source -> stalled transport -> failed/no objects -> restart -> duplicate returns previous failure -> cooldown/new command -> source-bound success; concurrent reviewer change or lease expiry prevents activation.
Explicit non-goals: merge/deploy, layout, chunking, clinical validation, pilot, new provider/job API.

Reservation and activation use existing transaction/store lock boundaries, released throughout model work. Failure updates only its still-running attempt under that boundary and cannot overwrite a newer success. Local single-worker compatibility can use its existing durable file lock/rollback boundary for the same retry command; this intentionally supersedes only the former local-refusal clause in SMETTEN_SOURCE_REPROCESSING_CONTRACT. Production multi-process PostgreSQL still uses its row-locked override. No new supported hosting topology.

## Failure/recovery -> duplicate/concurrent behavior -> audit/evidence
Success is accepted only at the activation check under the existing lock. Lease expiry racing a response is resolved there: expired loses, even if response was already received. Monotonic attempt budget includes reservation wait, extraction, model call, validation and activation lock wait; its linearization point is the last check before commit. The attempt budget is an activation lease for local extraction/validation, not a new supervisor for every existing local parser or database commit; actual transport waiting is forcibly bounded by the remaining budget. Durable UTC expiry survives restart; monotonic values are not persisted across processes.
Transport supervisor total duration starts immediately before starting the worker and includes startup, DNS/TCP/TLS/proxy, upload, response headers/body, JSON decoding and result transfer. Connect budget covers worker startup + DNS/TCP/TLS/proxy until connection established. Idle budget is maximum silence after that; byte receipt resets it, an open socket/local heartbeat does not. No claim of model progress. Total does not reset on bytes and includes all waiting; there are zero automatic retries. The call uses the remaining attempt budget (minus cleanup), never a fresh full budget after local preparation. Each worker is terminated then killed if necessary and reaped within a two-second cleanup allowance. Linux parent-death signal prevents a crashed parent leaving the transport process behind. Supported production host is Linux.
Private request/result data uses anonymous file descriptors that the OS closes on process death, not named files. Parent SIGKILL may leave a small non-sensitive status directory for host temporary-file cleanup, but no credentials/prose or live worker.
Provider failures/timeouts record only attempt/call IDs, limits, UTC start/end, monotonic elapsed, safe error category, retry linkage, bytes received, and cancellation=unknown (or not_requested before connection). No credentials/document content in error logs. Successful existing provider evidence retains its established proposal provenance.
Unknown external completion has a conservative retry-not-before of that call's original total deadline. It does not guarantee provider cancellation, but avoids immediate overlapping retries; max attempts bounds exposure. Structural input/output limits are not retried as transient connectivity failures. Provider validation errors remain explicit and never use another extraction method.

## Defaults and operational limits
METIS_LLM_CONNECT_TIMEOUT_SECONDS=10 (assumption: healthy DNS/TLS should finish quickly; adjustable).
METIS_LLM_IDLE_TIMEOUT_SECONDS=600 (non-streaming model can be silent; matches the documented SDK default timeout as a conservative starting policy, not measured latency).
METIS_LLM_TOTAL_TIMEOUT_SECONDS=900 (15 minutes: extra headroom beyond 10-minute silence while capping trickle responses).
METIS_PROCESSING_ATTEMPT_TIMEOUT_SECONDS=1800 (existing 30-minute reservation; includes local preparation/validation/lock waiting).
METIS_PROCESSING_MAX_ATTEMPTS=4. Bounds must be finite/positive, connect <= idle <= total < attempt; maximum attempt policy 3600s, leaving at least 60s between call and attempt budget. Cleanup allowance=2s.
No recorded benchmark justifies 180s. Defaults remain assumptions to measure after deployment. App Service/client/proxy may disconnect earlier; a browser disconnect does not cancel the kernel command. The existing async host heartbeat differs from request execution. No infrastructure timeout/settings are changed.

## Rewrite mitigation and slices
Rewrite target: additive bounded execution and existing attempt reservation/activation, not knowledge/lifecycle/publication authority.
Why local patching is insufficient: socket timeout and an after-return check cannot bound trickling/DNS or retain initial intent across crash.
Current authority/writer/reader map: semantic binder -> pre_review -> native transport; ingest/reextract/retry -> processing_retry -> existing local store / PostgreSQL workflow_document/review mixins; console and CLI -> shared kernel status; diagnostics/export read attempts. Startup reads unchanged; explicit reserve recovers expiry. Other document/review/publication writers retain their existing CAS/immutable guards.
Supported runtime topologies: existing Linux single instance, one local compatibility worker or production PostgreSQL one/two workers; transient transport child is not a workflow worker.
Persisted-state impact: additive versioned attempt limits/transport metadata and source version; no SQL changes.
Compatibility/migration plan: readers accept absent/v1 data before new v2 writes; no rewrite/backfill. Export new columns advertise a new contract version.
Rollback/recovery plan: disable new processing with compatible reader, retain attempts/objects and forward-fix; old unbounded binary is not a safe operational rollback. Existing interrupted lease permits manual recovery.
Cutover trigger: controlled transport and native lifecycle proofs, repository checks and adversarial review; later authorized deployment only.
Cleanup/decommission criteria: each transient worker/files removed in finally; no temporary durable authority/dual-write to remove.
Failure blast radius: one attempt, never historical work or another snapshot.
Adversarial proof matrix: no-connect, no-headers, trickle, timely/late JSON, parent kill, same/different commands, stale revision/actor/source, lease expiry, failed state persistence/activation, local/PG and CLI/console, giant input rejection with no truncation.
Slices: (1) bounded call with classified observations; (2) reserved attempt safely activates or fails/restarts; (3) one durable status/recovery projection for clients. Tests at transport/domain/persistence/client boundaries, then full regressions.


## Separate adversarial review pass
- Initial reservation across separate runtime file locks: reuse the existing empty-revision create-if-absent CAS and PostgreSQL advisory transaction lock. One command creates one reservation and one provider request. Refresh the authoritative stored envelope after reservation, including existing DB-managed lineage fields, before pinning activation.
- Activation checks after expensive validation/source access: recheck both UTC lease and monotonic deadline immediately before terminal success/commit. A native response after expiry, changed source bytes or a real concurrent review decision cannot activate; retained review objects/events remain exact.
- Partial storage failure: existing native retry tests inject an error after bundle writes. The original bundle remains blocked, no succeeded attempt/result survives rollback, and explicit retry uses the same source.
- Recovery without a terminal write: initial intent survives KeyboardInterrupt/restart; expired running projects expired, and the existing reservation transition records interrupted before recovery. A real parent SIGKILL kills the transport child; private anonymous descriptors are released.
- Replay provenance: exact replay retains original provider evidence and records replayed_call_id rather than presenting the old call as a new attempt's transport execution. Frozen attempt policy and effective remaining call budget remain distinguishable.
- Alternate entry points: production binder uses supervised urllib; CLI status/retry enter the exact configured ASGI kernel, with no separate extraction or state logic. The existing explicitly injected synchronous post_json test/instrumentation seam remains caller-responsible for transport bounds; it is not a configurable production provider route. Its elapsed guard still rejects late results.
- Local compatibility remains single-worker only; PostgreSQL row locks serialize retry/activation against review/publication writers. No new topology, table, job authority or background thread executor.

## Verification and remaining limits
Controlled transport tests cover stalled TLS connection, connected silence, byte-by-byte trickle exceeding total, timely JSON, late JSON, real parent process death and worker reaping. Native PostgreSQL tests cover initial durable reservation, same-command initial races across runtime locks, duplicate/concurrent retry, timeout/cooldown, source/revision/permission/review changes, UTC/monotonic expiry, failed activation and interrupted initial processing. CLI/HTTP read the same durable status and CLI retries the existing kernel command.
The defaults are adjustable policy assumptions, not measured provider latency or proof of document-size support. No chunking is introduced. Existing 2MB serialized-input/4MB-response limits fail explicitly. External cancellation and stopped billing remain unconfirmed. Local parsing/database operations retain their existing bounds; the attempt lease prevents late activation, while the supervised model wait has a hard execution deadline. Non-Linux execution fails explicitly.
Contract changes: additive source-reprocessing-v2 and bounded-model-call-v1 records; processing CSV v6 / projector v5. Existing v1/absent fields remain readable. No SQL schema migration, backfill, source-layout changes, review replay, merge or deployment.


## Final local verification (2026-10-02)
- Full repository suite: **2,596 passed**, zero failures/skips, Python 3.12, native PostgreSQL 17 (UTC), Chromium desktop/mobile and real dependency ZIP construction. Five existing dependency warnings remain. This rerun includes the final production code, initial cross-runtime CAS fix, replay provenance and shared CLI/HTTP status.
- Targeted transport/kernel/source-context/review regression set: **90 passed**. Packaging separately: **14 passed**. Architecture invariants: **6 passed**.
- Repository preflight, compileall, both change contracts, changed-path release-control mapping and Product API generation/backward compatibility against e9141ae9: PASS.
- Six Chromium scenarios passed (first/second review and independent decision paths, desktop/mobile); representative mobile prose, desktop second review and mobile paths were visually inspected. Existing knowledge-object/layout work stays intact.
- Original unrelated unstaged layout-test deletion remains excluded. No database schema migration or publication hash/identity rewrite. Native lifecycle regression tests include retained reviews, publication successor/withdrawal/restart and commit failure.
- Reproduce with repository development dependencies, an isolated METIS_TEST_POSTGRES_DSN, optional METIS_BROWSER_EXECUTABLE/METIS_PLAYWRIGHT_MODULE for Chromium, then python -m pytest -q. Transport tests use synthetic local servers, no real model calls or clinical validation.
