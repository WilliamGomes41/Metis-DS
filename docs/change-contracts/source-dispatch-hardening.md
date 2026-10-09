# Bounded source delivery — #580

Change class: A
Promise: existing source-selection commands are delivered through one bounded dispatcher; capacity contention keeps an unclaimed command durable, and shutdown stops admission without inventing completion.
Proof: installed HTTP recovery routes never invoke synchronous recovery; local and native PostgreSQL durable pending recovery, two-process shared Docling lock contention, bounded notify/scan backlog and shutdown with paused threads.
Touches lifecycle invariants: yes
Rewrite risk: high

User assignment: implement the recommendations from the second dispatcher review, 2026-10-09. Extend PR #578 on fix/availability-a26-a04-a05-a02, starting at 27d94b551d97939504ab76df336efcf592896d57.

Lifecycle entity: existing SourceSnapshot/WorkingRevision processing_attempts.
Lifecycle transition: authorized running+dispatch.pending -> existing single claim -> existing preparation/guarded activation; unavailable local/conversion capacity leaves the same attempt pending.
Initial durable state: received or resumable unpublished working source, existing durable authorized pending attempt; no new job authority.
Trigger: explicit source-selection POST; technical recovery POST opens the same source-selection page and requires its existing explicit start command.
Authorization: existing source-selection researcher/named-reviewer rules, repeated at execution and activation; technical links cannot authorize execution.
Validation: current object revision, source identity, mode/model/extractor/deployment, expiry, successor parent and existing review guards.
Mutable entities: existing unpublished workflow envelope/attempt and guarded candidate set only.
Immutable entities: source bytes, reviewed work, predecessors and historical published releases.
Workflow state before: existing processing/review state.
Workflow state after: existing state derived by readiness; pending waiting is presentation only.
Release state before: existing releases.
Release state after: unchanged; no release writer in this change.
Serving state before: publication registry.
Serving state after: unchanged.
Expected API result: technical reprocess/resume POST redirects to Bronselectie without reserving or executing; source-selection POST returns after existing durable reservation.
Expected UI result: pending running attempts show waiting with elapsed acceptance time and explicit existing total deadline/retry-budget semantics; claimed attempts show execution phase.
Failure result: capacity_busy at admission does not claim or fail a dispatcher attempt; other failures remain existing attempt failure/expiry; source/review/published work retained.
Restart result: unclaimed work is discovered until the original expiry; claimed uncertain work is never automatically replayed.
Recovery result: original expires_at and retry counting remain unchanged; explicit recovery after expiry under existing authority. No worker extends a deadline.
Legacy-data result: old attempts remain readable and unchanged; synchronous kernel/CLI API remains available. Single-instance one/two-process support retained.
Required black-box scenario: receive two sources, reserve while shared conversion capacity is occupied, observe pending waiting and no provider call, restart/discover, release capacity, process exactly once; shutdown with an active paused provider accepts no new pending work; restart and stale activation fences remain.
Explicit non-goals: changing deadline/retry-budget semantics, a worker hosting rewrite, forced termination of Python threads, route-comparison dispatch, legacy class conversion, merge/deploy/Azure mutations or paid calls.

Rewrite target: local delivery bounds, existing Docling-lock admission/handoff, pending projection and technical route consolidation.
Why local patching is insufficient: a semaphore alone bounds active tasks but not submitted handles or other web processes; task cancellation does not stop a thread; redirecting sync calls after execution preserves the long request.
Current authority/writer/reader map: PostgreSQL workflow document envelope processing_attempts is sole command authority; reserve_selection/reserve, claim, expire_running, _record_processing_failure, guarded reextract activation write it; SourceProcessingDispatcher scan/notify/start/stop and execute_source_selection consume it; source-selection projection/UI and technical routes read it. Local file single-worker compatibility uses existing envelope commits. Docling extract owns the existing host-shared conversion lock, not a job state.
Supported runtime topologies: file single worker; PostgreSQL on one instance with one/two web processes and shared conversion lock path. No multi-instance global capacity guarantee.
Persisted-state impact: none; no new statuses, tables, lease or retry fields.
Compatibility/migration plan: additive helper for transfer of the existing conversion file descriptor within the executing thread; old direct extractor calls still acquire the same lock. Technical routes become navigation-only, kernel compatibility retained.
Rollback/recovery plan: revert code with original envelopes readable, preserve immutable source/review evidence and claimed expiry fence. No destructive migration. Already running threads retain their own deadlines; shutdown coroutine grace is not process-termination proof.
Cutover trigger: branch code only; technical routes converge to explicit existing Starten/Hervatten. No production activation.
Cleanup/decommission criteria: remove HTTP synchronous recovery calls now; no second queue or transitional durable mirror. Retain direct kernel APIs intentionally.
Failure blast radius: one unpublished source attempt; shared lock failure cannot change serving.
Adversarial proof matrix: HTTP notify floods and scan floods, two processes/different documents, same-attempt duplicate claims, lock descriptor handoff/release before provider, exception/closed descriptor, shutdown versus thread starting/claim, polling recovery after skipped notify, unchanged expiry/budget, stale revision/config/authorization, no serving changes.

Implementation choices preserve the existing total deadline and retry counting. Excluding capacity-only expiry from retry counting is a separate lifecycle decision, not part of this implementation.
