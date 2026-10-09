# A04 additional HTTP and session acceptance — #583

Change class: C
Promise: prove that real successor extraction/provider waiting leaves health, Entra session status and independent actor HTTP work available on the same ASGI eventloop.
Proof: deterministic extractor/provider barriers on installed routes, separate cookie jars on one portal, native PostgreSQL Entra session observations, expiry/revocation, receipt write, duplicate attempt and negative eventloop execution controls.
Touches lifecycle invariants: no
Rewrite risk: none

User assignment: execute the correction prompt, starting from main `45ac215a4f030066e6010db316ff76ac5adb90c7`. Tests and acceptance evidence only; no merge or deployment. Reclassify before any production/lifecycle change.

## Existing model and ownership

SourceSnapshot/WorkingRevision and ProcessingAttempt are stateful kernel-owned entities. Entra identity/session state is owned by the existing PostgreSQL identity authority. HTTP source/session projections are observational; browser cookies and dispatcher handles are not durable authorities. OperationsConsole is backend orchestration despite its name.

Existing path: POST /review/successor -> create_review_successor(receive_only=True) -> immutable byte verification and durable empty successor registration -> explicit POST /source-selection/start -> reserve_selection -> durable pending dispatch -> claim -> source extraction/provider outside eventloop and write transaction -> existing guarded activation.

No new lifecycle state, writer, persistence format, lease, retry budget, session policy or serving authority is introduced. Existing received/pending/claimed/failed/interrupted/succeeded semantics remain owned by the prior A04/A05/A26 contracts, not by this proof document.

The successor has separate identity, lineage and review obligations. Parent source, objects and review bindings are unchanged. Receipt alone starts no preparation. Duplicate commands retain identity. Preparation holds no outer write transaction. Activation still checks actor/source/revision/configuration/lease/parent guards. Publication registry remains the serving authority.

An accepted ProcessingAttempt stores an actor_id, not a browser token. Existing execution/activation rechecks account authorization, not browser-session liveness. Expiring/revoking the accepting browser therefore denies new browser commands but does not itself cancel accepted kernel work. This proof observes that existing contract; it does not introduce a cancellation or continuation policy. Retirement/role changes remain separate authorization events.

## Session contract and HTTP proof

`/session/status` exists only in Entra mode. Local login availability alone cannot prove that route. Native tests use full synthetic PostgreSQL schema and real Entra identity/session/routes. Only Microsoft exchange and model responses are synthetic; document registration, sessions, claim and activation are real.

Both clients share a single TestClient BlockingPortal/eventloop and separate cookie jars. Starting a second independent app context could mask an eventloop block and is forbidden in this proof. The controlled negative variant replaces dispatcher thread delivery with direct synchronous execution; the same observer must fail specifically with `A04_HTTP_BLOCKED:/health`. Cleanup releases the barrier from the test thread, independently of the blocked loop.

Pause separately at the actual HTML extractor symbol called by OperationsConsole._extract and at the configured provider transport. Delegate extraction to the real HTML implementation after release. During each pause, HTTP health, both session-status reads, actor B's Inleveren read and independent receipt POST must finish within two seconds before release. B's unrelated receipt is durable and starts no extraction. B cannot enter A's named-reviewer policy route. Duplicate Starten creates no second attempt.

Compare persisted created_at/expires_at/revoked_at before and after session-status polling. Navigation retains its existing explicit idle-renewal behavior; passive polling does not renew. Expire A's session and revoke B's session during the pause: status/renew fail with 401, expired A cannot submit a new attempt and revoked B navigation redirects to authentication. Stored invalidity remains unchanged. Accepted work completes under the existing actor-based execution contract after release.

## Transaction, failure and recovery

Registration/reservation/claim/activation reuse existing boundaries without modification. Provider/extraction latency is external preparation, not a transaction. The independent receipt demonstrates an actual HTTP mutation while the predecessor operation waits. Failure of a probe releases barriers and drains delivery handles; no destructive recovery or production data is used.

The preparation probe checks the current thread's existing RLock ownership, not the console-wide lock depth. A concurrent short write or dispatcher scan may legitimately make shared depth nonzero. A deterministic regression holds the lock in a different thread and requires the preparation observation to remain unlocked; its positive control requires ownership to be detected when the observing thread itself holds the lock. HTTP deadlines and negative eventloop controls remain unchanged.

Existing tests reused for stale parent activation, cross-kernel SQL claim/writer concurrency, expiry/restart/resume, unchanged predecessor/release, and full review/publication/serving recovery: test_availability_repair, test_azure_source_processing, test_source_dispatch_hardening, test_source_resume_acceptance and test_lifecycle_withdrawal_recovery_v1. They remain in the mandatory native proof run.

## Evidence scope

Run `python -m pytest -q -s tests/test_a04_session_availability.py` with the existing synthetic test PostgreSQL DSN. The native proof workflow includes this file and its existing XML acceptance gate rejects skips/failures/errors. Local selection `-k local` proves extractor/provider availability plus both negative controls, but cannot complete native session acceptance.

Report exact code SHA and actual command/results separately from merge, deployment and production validation. GitHub/native synthetic proof does not establish Azure production behavior or historical 502 causality. No runtime code changes, migrations, paid provider calls or production resources are required.
