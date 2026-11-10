# Open an annotation source through the existing durable dispatcher

Change class: A
Rewrite risk: high
Touches lifecycle invariants: yes
Promise: the first annotation-source click reserves durable preparation and returns a progress page promptly, even when the PDF converter is blocked for minutes; reload/restart resumes the same pinned work without creating knowledge objects.
Proof: held-extractor native HTTP test; native duplicate, concurrent, denied/stale, lease recovery, checkpoint reuse/rollback, both-layout and desktop/mobile progress tests.

## Grounded cause and ownership

Deployed commit ea0360ee (1.1.558) awaits `annotations.prepare` in POST /annotations/source. Production's retained extraction reports 337.838s of Docling worker time for46pages, with306.129s inside conversion. Moving the call to a thread did not release the HTTP request. A local real-PostgreSQL HTTP timing probe shows prepare builds a discarded overview before the redirected GET builds it again. Source preparation does not call GPT or create knowledge candidates.

Reuse the existing SourceProcessingDispatcher, processing_attempts, checkpoints, claims/heartbeats, source bytes/extraction and annotation_sets. The console owns only disposable forms and a progress projection. No second job table, in-memory task authority, queue or candidate creator.

## Context and lifecycle contract

Lifecycle entity: existing received WorkingRevision/SourceSnapshot and its initial annotation input.
Lifecycle transition: received -> durable pending/claimed source preparation -> pinned annotation input; existing source and publication lineage remain unchanged.
Initial durable state: received source and review policy, no knowledge objects, no annotation set, no competing running attempt.
Trigger: existing explicit researcher/reviewer source-open POST, carrying document, expected object revision and command ID.
Authorization: current source-selection rule at reservation, claim, extraction checkpoint and pin; publication immutability stays enforced.
Validation: source identity/hash/version, logical/working revision, expected object revision, extractor contract/configuration, current claim token/deadline, source bytes and extraction integrity.
Mutable entities: existing attempt/checkpoints/summary; immutable prepared extraction; initial annotation_set pinned once.
Immutable entities: source bytes/lineage, prior annotations, candidates/objects, review approvals, releases and serving registry.
Workflow state before: received/unformed with original review policy.
Workflow state after: source prepared for human annotation, with no knowledge object or review/publication grant.
Release state before: any predecessor's existing release.
Release state after: unchanged.
Serving state before: registry-determined.
Serving state after: unchanged.
Expected API result: short reservation POST303; read-only progress while pending/claimed; prepared source on subsequent GET; errors have an explicit retry action, not an automatic new command.
Expected UI result: real pending/extracting/checking/saving phases and elapsed time, automatic bounded refresh, ability to leave/return, explicit failure/retry; no fabricated percentage or duration promise.
Failure result: no partial annotation pin; attempt retains a bounded error; immutable source/checkpoint remains available; stale/unauthorized workers cannot finish.
Restart result: durable pending work is rediscovered; expired claim is reclaimed under existing leases; committed extraction checkpoint is reused; pre-checkpoint crash may repeat extraction.
Recovery result: existing workflow export/import already owns attempts, checkpoints and prepared extraction. No archive version/table addition; restore uses the current schema guards.
Legacy-data result: both native PostgreSQL input layouts; existing prepared sources open without a new job or extraction; synchronous kernel prepare remains available to existing non-HTTP callers.
Required black-box scenario: hold a real extractor at a barrier, receive HTTP303/progress and responsive other navigation, reload without another extraction, release converter, observe pinned source and no candidates; recreate kernel/dispatcher with lost lease after extraction checkpoint and finish from that same extraction.
Explicit non-goals: changing PDF recognition fidelity, claiming shorter conversion time, automatic semantic formation, approval/publication, source erasure, new infrastructure or deployment.

| Context | Producer/owner | Consumer | Lifetime and validity |
|---|---|---|---|
| Snapshot/source/hash/version and logical/working revision | existing document | reservation, worker, pin | exact match at every protected write |
| Command, expected revision, extractor contract | explicit source-open reservation in existing attempt | dispatcher/worker | immutable accepted input, same command reuses existing result |
| Claim/token/deadline | existing native handover | checkpoint and pin | current running owner only; no expiry extension on restart |
| Prepared extraction reference | existing immutable extraction + staged_extraction_hash checkpoint | resumed worker and annotation_set | integrity/source/extractor match before reuse |
| Roles and publication | existing current accounts/review/release authorities | every mutation | caches/progress pages never grant authority |
| Progress and elapsed time | projection of existing attempt | console | reconstructable, read-only, no fabricated page percentage |

Rewrite target: bounded source preparation delivery and the existing source-pin transaction.
Why local patching is insufficient: changing labels or HTTP timeouts leaves a337s operation inside the web request; a disposable thread lacks restart ownership and cannot safely pin after losing its claim.
Current authority/writer/reader map: existing received document -> explicit attempt -> SourceProcessingDispatcher/native claim -> extraction checkpoint -> existing annotation pin -> annotation readers; registry remains serving authority.
Supported runtime topologies: native workflow/canonical PostgreSQL, both document-input layouts, local-cache or Blob source bytes, multiworker/restart; no file-backed substitute for job state.
Persisted-state impact: additive source-preparation kind in existing attempts, with pinned non-semantic configuration and existing staged_extraction_hash; schema guards updated explicitly for this bounded human-source operation, no new tables/grants.
Compatibility/migration plan: install registered migration041 before enabling the short source-open path; reservation checks the native source-attempt guard; old semantic writers remain fenced and prepared annotation readers remain compatible.
Rollback/recovery plan: old application still reads pinned annotation input; its configuration comparison rejects the source-preparation configuration before semantic processing. It may mark a new source-preparation job failed, so an old application is not a compatible preparation worker. Keep durable attempts/checkpoints; resume with a compatible worker and an explicit retry, never clear/delete for recovery.
Cutover trigger: reviewed exact-main deployment after registered migration/rights verification; no production action in this local repair.
Cleanup/decommission criteria: same dispatcher and durable authorities; no temporary dual status, fallback queue or new infrastructure.
Failure blast radius: one unformed source's preparation; transaction/claim fences preserve unrelated documents and all review/publication state.
Adversarial proof matrix: blocked converter vs promptPOST; duplicate/concurrent reservation; roles/source/revision changed midflight; stale token; loss after committed extraction; lease/expiry; migration absent; busy Docling slot; error/retry; prepared sources; normal annotation building, prose-retirement and publication guards.

## Separate adversarial review

Reviewed alternate writers and readers after implementing the slice:

- The retained synchronous `prepare` entry still uses the same source-record and native pin operation. A running source job prevents a competing synchronous pin; prepared sources remain authoritative and need no new reservation. No source worker calls materialisation, semantic providers or publication.
- Both legacy and compact document layouts were exercised. This found a missing compatible-writer setting at completion; the source operation now uses the existing setting within its native transaction. Runtime-role tests use the existing workflow grants and separately provisioned canonical SELECT grants, with no new grant profile.
- Duplicate commands and simultaneous kernels share one running attempt. Expired work is not reused for a new command; this was corrected and tested. Old claim tokens cannot change a recovered terminal result.
- A real subprocess exits after committing extraction and before pinning. A restarted kernel reclaims the same attempt and completes without invoking the extractor. A pin failure rolls back completion and the annotation set together, retaining the independent extraction checkpoint. Missing checkpoint references fail closed instead of silently re-extracting.
- The new source configuration is pinned to the source and extractor contract, without model configuration. Revoked permissions and a changed extractor contract prevent pinning after conversion. Native guards reject changed accepted inputs. Migration absence refuses admission; losing the enabled native guard after admission also refuses worker execution, checkpoint and completion.
- Prose retirement originally had two SQL forms of the build-only exception. Both now allow the bounded human source variant; tests cover preparing after retirement in both layouts, while old AI reservation remains refused. Annotation ownership still refuses AI after the pin.
- A busy PDF conversion slot leaves the exact durable command pending. The browser shows waiting rather than a failed attempt or automatic retry.
- Rollback retains extraction, attempts and existing prepared-source readers. Old workers reject the new configuration before calling semantic processing; they cannot resume this new kind. Compatible-worker recovery is required. No schema removal, state deletion or production action is part of this repair.

Local evidence before the complete regression suite: 19 native acceptance/recovery tests passed; Chromium desktop 1440px and mobile 390px passed with no horizontal overflow or page errors. The held converter remained blocked while the browser received progress in445ms, another document view worked, reload retained progress, and completion automatically opened the source. This is a local responsiveness measurement, not a promise about production conversion duration. The Impeccable context launcher could not download its engine; existing design context and vendored hardening/craft guidance were applied, and rendered screenshots were inspected manually. No engine audit result is claimed.

Composition reference: [annotation-source-preparation](../architecture/annotation-source-preparation.md), linked from Alles over Metis. No new deployment component, queue or storage authority.
