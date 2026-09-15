# Metis lifecycle VSA contract

This file is normative for every issue that changes ingest, document/version identity, review, repair, readiness, publication, serving, migration, reconciliation, recovery, supersession, withdrawal, or any UI/API that presents those states.

`MUST` means required. `MUST NOT` means forbidden. `SHOULD` may be violated only by an explicit ADR. An agent must not reinterpret these words.

## 1. Lifecycle entities

### LogicalDocument

A `LogicalDocument` is the stable identity of one content publication across source versions.

Required identity: `logical_document_id`.

Rules:
- `logical_document_id` MUST remain stable across all source versions of the same publication.
- Source version, source date, source hash, snapshot id, release id, and object id MUST NOT define LogicalDocument identity.
- One LogicalDocument MAY have one active published release and, at the same time, one open successor WorkingRevision.
- One LogicalDocument MUST have at most one active serving release.

### SourceSnapshot

A `SourceSnapshot` is an immutable capture of exactly one received source version.

Required identity: `snapshot_id`.

Required links: `logical_document_id`, `source_version`, `source_date`, `source_sha256`, `source_locator`, and immutable source storage locator.

Rules:
- Source bytes and `source_sha256` MUST NOT change after ingest.
- One SourceSnapshot MUST belong to exactly one LogicalDocument.
- Different received source versions MUST have different snapshot ids.
- A SourceSnapshot that has contributed to a published release MUST NOT be re-extracted or mutated in place.

### WorkingRevision

A `WorkingRevision` is the mutable curation state derived from exactly one SourceSnapshot under one review/policy context.

Required identity: `working_revision_id`.

Required links: `snapshot_id`, `logical_document_id`, and the policy/review contract used to create it.

A WorkingRevision owns the mutable extracted object set, review state, repair state, review evidence, and publication-readiness state.

Rules:
- Only a WorkingRevision may accept curation mutations.
- A published release MUST NOT be used as a WorkingRevision.
- A SourceSnapshot MAY have a later WorkingRevision when a policy upgrade requires re-evaluation.
- A policy upgrade MUST NOT reopen or mutate a previously published WorkingRevision in place.
- There MUST be at most one open WorkingRevision for the same SourceSnapshot and policy context.

### PublicationRelease

A `PublicationRelease` is an immutable publication decision over exactly one closed WorkingRevision.

Required identity: `release_id`.

Required links/evidence: `logical_document_id`, `snapshot_id`, `working_revision_id`, release version, release owner, published timestamp, exact object-version set, and exact content hashes.

Rules:
- A PublicationRelease MUST be immutable.
- Its object set and content hashes MUST never be changed after publication.
- New review evidence MUST NOT be appended as if it had been part of the original release decision.
- A release MUST remain reproducible after restart and software upgrade.

## 2. Workflow state

A WorkingRevision MUST have exactly one of these workflow states:

- `processing`: object preparation is incomplete; publication is forbidden.
- `in_review`: at least one required curator decision is not final.
- `blocked`: curator work may be complete, but a technical, integrity, authorization, or durability condition blocks publication.
- `ready_for_publication`: curation and all technical publication gates are complete and passing.
- `closed`: no further curation mutation is allowed for this WorkingRevision.

The following rules are absolute:
- Any required `needs_review`, `revise`, deferred decision, unresolved source-passage disposition, or missing required second review means the WorkingRevision is not ready.
- `blocked` MUST NOT be used merely to hide open curator work.
- `ready_for_publication` requires `curation_ready == true`, `technical_ready == true`, and `publication_ready == true`.
- A successful publication MUST close the WorkingRevision used for that release.

## 3. Release state and serving state

A PublicationRelease MUST have exactly one release state:

- `published`: valid published historical release.
- `superseded`: valid historical release replaced by a newer release of the same LogicalDocument.
- `withdrawn`: explicitly withdrawn historical release.

Serving is a separate state:

- `active`: this release contributes the current serving set.
- `inactive`: this release must not contribute the current serving set.

Rules:
- One LogicalDocument MUST have at most one `active` release.
- `superseded` and `withdrawn` releases MUST be `inactive`.
- A withdrawn release MUST NOT become active automatically after restart, reconciliation, or recovery.
- Historical release existence MUST NOT be confused with current serving eligibility.

## 4. Single authorities

Each truth has one authority only:

- Source bytes: immutable source store.
- Working/review state: durable workflow PostgreSQL state.
- Historically published canonical object versions/releases: canonical publication store.
- Current serving eligibility: publication registry.

Rules:
- UI/envelope state MUST NOT become a second serving authority.
- Release metadata MUST NOT become a second serving authority.
- Review/readiness state MUST NOT become a second serving authority.
- Reconciliation MUST restore projections from an authority; it MUST NOT invent new domain decisions.

## 5. Published immutability

If a SourceSnapshot has contributed to a PublicationRelease, the published work represented by that release is immutable.

The following operations MUST NOT mutate that published work in place:

- review;
- correction;
- repair;
- re-extraction;
- reclassification;
- review reopening;
- migration of review state;
- overwrite of canonical/workflow objects representing the published revision;
- change of prior reviewer decisions or canonical hashes.

If new work is required, the system MUST create either:

- a new WorkingRevision from the same SourceSnapshot for an explicit new policy/review context; or
- a new SourceSnapshot and WorkingRevision for a new source version.

## 6. Policy upgrade

Given a published active release produced under policy A, installing policy B MUST NOT change that release or reopen its historical WorkingRevision.

If policy B requires additional curation:

- the existing release remains immutable;
- the existing release remains active unless explicitly superseded or withdrawn;
- a new WorkingRevision is created under policy B;
- the new WorkingRevision may be reviewed and later published as a successor release.

Startup migrations MUST NOT silently turn a published revision back into current review work.

## 7. Successor source version

When a new source version for the same LogicalDocument is ingested:

- a new SourceSnapshot MUST be created;
- a new WorkingRevision MUST be created;
- both MUST retain the same `logical_document_id` as the current document lineage;
- the existing active release MUST remain active and immutable while the successor is processed or reviewed.

The valid state `published v1 + working v2 in review` MUST be supported.

## 8. Successor publication

Given release R1 is active and successor WorkingRevision W2 is `ready_for_publication`, publication of W2 MUST be one atomic lifecycle transition.

Successful post-state:

- W2 = `closed`;
- new release R2 = `published`;
- R2 serving state = `active`;
- R1 release state = `superseded`;
- R1 serving state = `inactive`;
- current API/serving output contains the R2 serving set and not the R1 serving set.

There MUST be no observable successful intermediate state with both R1 and R2 active, or with R1 inactive while R2 is not active.

On failure the transition MUST fail closed: R1 remains active and R2 does not become active.

Restart immediately after the operation MUST preserve the same post-state.

## 9. Withdrawal

Given an active release, an authorized withdrawal MUST require an explicit reason and MUST atomically produce:

- release state = `withdrawn`;
- serving state = `inactive`;
- withdrawal actor, timestamp, and reason in durable audit evidence;
- no serving/API result from the withdrawn release.

Canonical historical data and release evidence MUST remain intact.

Restart/recovery MUST NOT reactivate the release.

## 10. Object identity and document lineage

`object_id` identifies a concrete canonical knowledge object. It MUST NOT be used as the sole identity of a LogicalDocument or as the sole proof that an object in source version N is the same semantic object in source version N+1.

Document-level supersession MUST be based on `logical_document_id` plus release lineage, not solely on `old_object_id == new_object_id`.

If cross-version semantic object continuity is needed, use a separate explicit `object_lineage_id` contract. Such a link MUST NOT be inferred by fuzzy text matching or an unconstrained LLM decision.

## 11. UI state

Metis MUST NOT present one ambiguous scalar `document status` when a LogicalDocument can simultaneously have an active release and an open successor WorkingRevision.

The UI MUST distinguish at least:

- serving/publication status: for example `not published`, `live version 1.0`, `withdrawn`;
- workflow status: for example `no working revision`, `version 2.0 processing`, `in review`, `blocked`, or `ready for publication`.

A card that says only `published` while also showing open review work for the same apparent version is forbidden.

## 12. Legacy published data

A legacy snapshot is `LEGACY_PUBLISHED` only when durable publication authority proves a valid historical release.

A `LEGACY_PUBLISHED` snapshot:

- MUST remain immutable;
- MUST NOT be automatically migrated into open review work;
- MUST NOT be rewritten by a new policy;
- MAY be the source for a new explicit WorkingRevision;
- remains active until explicitly superseded or withdrawn.

A legacy snapshot without durable publication proof MUST NOT be assumed published.

## 13. Restart and recovery

For every completed lifecycle transition, durable state immediately before restart MUST equal durable state after restart.

Recovery MAY deterministically complete an already-authorized incomplete technical transaction.

Recovery MUST NOT:

- make a new curator decision;
- reopen review;
- create a publication decision that was never authorized;
- reactivate a withdrawn release;
- reactivate a superseded release;
- alter immutable published content.

## 14. Definition of a lifecycle vertical slice

A lifecycle vertical slice is one user/system event that realizes and proves one valid lifecycle transition across every layer needed by that promise.

Every lifecycle implementation issue MUST state, before code changes:

```text
Lifecycle entity:
Lifecycle transition:
Initial durable state:
Trigger:
Authorization:
Validation:
Mutable entities:
Immutable entities:
Workflow state before:
Workflow state after:
Release state before:
Release state after:
Serving state before:
Serving state after:
Expected API result:
Expected UI result:
Failure result:
Restart result:
Recovery result:
Legacy-data result:
Required black-box scenario:
Explicit non-goals:
```

No field may be omitted. `N/A` requires a written reason.

A slice MUST be specified as:

```text
GIVEN <exact durable begin state>
WHEN <one trigger>
THEN <exact durable end state + serving result + observable result + restart result>
```

The following are implementation steps and MUST NOT be treated as lifecycle slices by themselves:

- add a status;
- add a UI page;
- add a database column;
- add a button;
- add readiness;
- add a migration;
- add a supersede helper.

## 15. Definition of Done

A lifecycle slice is DONE only when every relevant item is proven:

- trigger;
- authorization;
- validation;
- domain transition;
- durable workflow write;
- durable canonical write when relevant;
- serving transition when relevant;
- concurrency behavior;
- restart behavior;
- recovery behavior;
- fail-closed/rollback behavior;
- legacy-data behavior when relevant;
- UI observable result when relevant;
- Product API result when relevant;
- audit evidence;
- at least one black-box lifecycle scenario;
- full required repository verification.

A relevant item with `FAIL`, `UNKNOWN`, or `NOT TESTED` means the slice is NOT DONE.

## 16. Mandatory stop conditions

The agent MUST stop without implementation and surface the missing decision when any of these is true:

- the lifecycle transition is not exact;
- authority is ambiguous or duplicated;
- implementation would mutate published work in place;
- stable LogicalDocument lineage is required but not defined;
- object lineage is required but not defined;
- a migration would reopen published review work;
- serving behavior after supersession or withdrawal is unspecified;
- restart/recovery behavior is unspecified;
- the required black-box lifecycle scenario cannot be stated before implementation;
- the user promise crosses layers but only a local/component proof is available.

The agent MUST NOT fill these gaps with a reasonable assumption.

## 17. Rescue-program transition contracts

The current rescue program is limited to these lifecycle capabilities. They are planning contracts, not permission to combine multiple implementation issues into one run.

### Rescue 1 — Published immutability

```text
GIVEN R1 published and active
WHEN restart, policy upgrade, legacy migration, or publication reconciliation runs
THEN R1 remains immutable, no review work is reopened on R1, and serving is unchanged
```

### Rescue 2 — Successor working version

```text
GIVEN R1 active
WHEN a new source version S2 of the same LogicalDocument is ingested
THEN S2 and W2 use the same logical_document_id, W2 is current workflow work, and R1 remains active and immutable
```

### Rescue 3 — Atomic successor publication

```text
GIVEN R1 active and W2 ready_for_publication
WHEN W2 is published
THEN W2 closes, R2 becomes published+active, R1 becomes superseded+inactive, API serves only R2, and restart preserves that state
```

### Rescue 4 — Withdrawal

```text
GIVEN R2 active
WHEN an authorized publisher withdraws R2 with a reason
THEN R2 becomes withdrawn+inactive, API does not serve it, audit history remains intact, and restart does not reactivate it
```

After Rescue 4, the program is not complete until one black-box lifecycle closure scenario passes across ingest v1 -> review -> publish -> restart -> policy upgrade -> successor v2 -> review -> atomic successor publication -> restart -> withdrawal -> restart.
