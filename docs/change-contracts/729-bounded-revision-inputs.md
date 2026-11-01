# MET-36: bounded revision inputs under the document owner

Change class: A
Rewrite risk: high
Promise: ordinary review/source decisions validate the current transition without
reloading a retained historical prefix on every decision; atomicity, lineage,
current dependencies and existing precondition variants remain effective.
Base: `3cc653bc26fd61748bd9f0b402c012b846dc0d27`. This implements the remaining
#729 scope under #959, consuming #952's dependency/atomicity proof. It does not
claim #729 or production acceptance complete from a partial technical increment.

## Usage before implementation

Existing callers keep `review_object(...)`, source commands and `publish(...)`.
The command adapter asks its existing document store for selected current raw
objects with validated revision inputs. The kernel stages the same governance
edits/successors and the store applies the existing ordered delta atomically.
Direct raw-list callers retain full independent history validation. Public m2
tokens retain whole-objectset semantics; generation and None keep their existing
contracts. The workspace token remains private to the captured selected inputs.

An explicit preparation operation validates an existing retained history once,
then installs its derived execution index with CAS. It does not run a model,
reconstruct candidates, change identities or add review/publication evidence.
GET/startup never secretly prepares history. New validated writers maintain the
index in their own transaction. Unprepared legacy commands retain the original
guard until controlled preparation/cutover; this compatibility path is explicitly
unbounded and is not accepted as the normal prepared-path performance proof.

## Shape and access patterns

- `RevisionWindow`: a bounded list of actual current raw objects plus this
  command's appended revisions; an immutable reference to the already validated
  prefix accompanies it. Detached mutable copies remain available to the existing
  kernel. First-object order is kept separately from physical head append order.
- `workflow.object_revision_frontiers`: a disposable derived execution index
  owned by the existing document store. Per object it stores a mutation epoch and
  certificate (producer/version, unique issuance identity, historical count,
  first/head positions, exact head identity and raw/canonical hashes).
- `revision_workflow` remains the only lineage/transition rule owner. A certified
  first head supplies the validated prefix boundary; new edges and every ordered
  intermediate governance/successor transition still pass its original rules.
- The storage boundary independently checks its issued reference against current
  indexed raw head and frontier. Every actual row change invalidates the derived
  certificate and advances its epoch, including nativeNULL/0, identity moves,
  historical live-field changes and TRUNCATE. Epoch plus own affected-row counts
  detects an extra same-connection mutation before resealing.

This is validation metadata over `document_objects`, not a second history,
KnowledgeObject, source-fact, approval, closure or publication authority. Optional
027 review cards stay optional: their lossy DTO is never command input. Where
027 exists, bounded fact maintenance must use the validated window, without a
hidden full-history count/validation. No new command framework or cache service.

## Alternatives and rationale

Candidate A: operation-owned repeatable-read full-history capture, validation
outside locks, then epoch CAS. This shortens protected work but leaves total
request cost linear in retained history. The rejected sharing prototype measured
POST3.779s, outer lock3.681s and28,917,363 JSON bytes, still above the budgets.

Candidate B: validated prefix frontier under the existing document owner, raw
current heads and ordered deltas. A separate real agent independently proposed
this shape. Select B because bytes, copying and hashing on the prepared command
path depend on selected current objects/changes, not retained prefix length.
Accept additive derived metadata and explicit preparation in exchange for bounded
normal commands. Do not force optional UI-card migration to introduce it.

Ground/Sketch: current code and both candidates inspected. Agree: user explicitly
authorized implementation, without a further approval checkpoint. Implement:
red native user-path test first, then schema/value/store/command integration.
Scrap: reject any implementation that silently restores full-history work inside
the prepared path, trusts object_generation for native0, or changes public rules.

## Lifecycle transition

Lifecycle entity: one existing WorkingRevision and its immutable SourceSnapshot.
Lifecycle transition: currently authorized curator decision, or unchanged refusal.
Initial durable state: native workflow objects/histories, bindings, source/policy,
participants and audit; derived revision index may need explicit preparation.
Trigger: existing review/source command production ingress.
Authorization: existing current role, retirement D1 and named participant checks.
Validation: existing exact source/proof, policy, lineage, precondition and seal
checks; the index certifies only historical integrity and the predecessor boundary.
Mutable entities: current unpublished governance, permitted successors, bindings,
facts, review passes, counters and audit/receipt in their existing transaction.
Immutable entities: source bytes, retained knowledge revisions, canonical releases.
Workflow state before: current existing processing/review/blocked/ready state.
Workflow state after: only the original kernel's valid result; no relaxation of
unresolved source, formation, required reviewers or technical publication gates.
Release state before: absent or existing immutable release.
Release state after: unchanged by review; existing publication owner only.
Serving state before: current publication registry active set.
Serving state after: unchanged by review/refusal; registry remains sole authority.
Expected API result: existing success, semantic duplicate, conflict or refusal.
Expected UI result: current existing response/navigation; faster prepared command.
Failure result: rollback objects, bindings, facts, counters, index and audit together.
Restart result: a new runtime derives the same durable outcome; no process cache
or discarded workspace becomes authority.
Recovery result: existing canonical-first projection recovery returns the same
release; workflow rollback never claims to retract canonical publication.
Legacy-data result: preserve raw-list/m2/None paths and exact historical data;
explicit preparation before existing-data bounded acceptance, no re-ingest.
Required black-box scenario: the existing native1100-row partial-formation HTTP
probe opens, saves, redirects, reopens and rejects stale submission, preserves the
other reviewer decision and still blocks incomplete publication. POST<=3s, reads
<=5s; record actual outer lock/transaction separately. Three growth/concurrency
axes and one complete local source command are additional acceptance requirements.
Explicit non-goals: timeout/budget increases, new candidate creator, new policy,
session redesign, blanket exactly-once, publication bypass or automatic deployment.

GIVEN a prepared native WorkingRevision with long retained history, WHEN a current
authorized reviewer decides one object/source passage, THEN only the current
transition and necessary delta/facts/bindings/audit are processed, retained history
and unrelated work remain identical, and restart observes the same atomic outcome.

## Rewrite-risk mitigation

Rewrite target: selected mutation inputs and historical validation work in the
existing document/command owner; no replacement of authoritative storage.
Why local patching is insufficient: faster deepcopy/hashing leaves per-command
historical work and long locks; a timeout increase leaves the scaling failure.
Current authority/writer/reader map: objects in workflow.document_objects; writers
are write_bundle/processing activation, apply_review_changes and existing source,
batch, second-review, repair, participation and graph ingress. revision_workflow
owns lineage; identity owns actor/D1; review store owns bindings/audit; source
store/extraction own immutable evidence. Canonical store owns releases/registry;
workflow envelopes and local mirrors are projections. Offline restore requires
its existing empty-target/exclusive contract and re-prepares derived metadata.
Supported runtime topologies: complete native PostgreSQL local/Azure compositions,
independent runtimes/lock files over one DB; legacy raw-list/file adapters retain
their original contracts. Process locks do not substitute for native concurrency.
Persisted-state impact: additive derived execution index/trigger migration only;
no object identity/content/history, release or source mutation/backfill by DDL.
Compatibility/migration plan: expand schema, seal new validated writers, explicitly
prepare old retained state with consistent capture/CAS, prove parity and bounded
route, controlled cutover then legacy cleanup. Optional review cards stay optional.
Rollback/recovery plan: old binary reads ordinary objects unchanged; the derived
index invalidates on old/direct writes, so new commands cannot reuse stale proof.
No destructive down-migration; preparation may be repeated without curator effects.
Cutover trigger: exact-head native negative/parity/cost proofs, separate adversarial
review and human merge/deploy authorization. Existing-data acceptance is MET-44.
Cleanup/decommission criteria: no hidden full-prefix reload on the prepared path;
old adapter removal only after explicit parity/cutover and all callers covered.
Failure blast radius: lost review work or stale authorization if wrong; preserve
independent current-head/storage checks and atomic rollback at every changed seam.
Adversarial proof matrix: native0/direct/history edits, forged/wrong-store/stale
references, invalid/reordered/removed predecessors, same-version raw JSON changes,
all precondition variants, policy/binding/actor/source races, failed intermediate
transition/audit/commit, missing certificates, TRUNCATE/restore, sealed canonical
crash window, restart, unrelated-data growth, concurrent GET/signin and actual lock
hold/wait. Consume MET-43's exact proof source/head; no scope closure from CI alone.
