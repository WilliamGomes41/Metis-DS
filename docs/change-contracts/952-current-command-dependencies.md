# MET-43 / #952: current command dependencies and atomic integration

Change class: A. Rewrite risk: high (the assigned integration boundary).
Base: `3cc653bc26fd61748bd9f0b402c012b846dc0d27`.

## Promise and ownership

A review decision consumes current authorized working state; failed writes leave
no partial decision. Canonical publication retains its existing independent
commit and deterministic projection recovery. This first slice proves those
contracts at the production entrypoints before changing their storage inputs.
It introduces no new execution framework, token, authority or runtime behavior.
MET-43 remains open until its full source/review/publication matrix is proved.

#729/MET-36 owns bounded mutation/read/fact capabilities and real outer lock
costs. #942/MET-35 owns source-role writer consolidation where needed. #953/MET-44
consumes version-bound evidence for existing-data/live acceptance. None is closed
by the tests in this slice. Publication remains blocked for incomplete formation.

## Lifecycle contract (specified before implementation)

Lifecycle entity: existing WorkingRevision of one immutable SourceSnapshot.
Lifecycle transition: one currently authorized curator decision, or refusal;
publication is the existing closed-WorkingRevision to immutable release transition.
Initial durable state: ingested/materialised native PostgreSQL working objects,
exact ordered histories, participants/policy, bindings and review audit.
Trigger: production `review_object`, source command, or `publish` ingress.
Authorization: current role/retirement and named participation; existing D1
requires refusal of the next command after retirement, not cancellation of every
already-authorized in-flight command.
Validation: existing source verification, revision lineage, exact review binding,
policy, required reviewers, public precondition and published/sealed guards.
Mutable entities: unpublished current governance, permitted successor revisions,
review bindings, review passes, audit/receipts and their derived facts.
Immutable entities: source bytes/identity, retained knowledge history, canonical
releases and their object versions; publication registry remains serving authority.
Workflow state before: processing/in_review/blocked or ready according to existing
rules; an incomplete formation fixture cannot become publication-ready.
Workflow state after: only the existing kernel's valid resulting state; refused
commands add no curator evidence and preserve concurrent committed work.
Release state before: absent, or an existing immutable release in recovery cases.
Release state after: unchanged by review; publication creates/reconciles the one
existing canonical release through its current owner.
Serving state before: existing registry active set (possibly empty).
Serving state after: unchanged by failed review; only existing canonical registry
publication/supersession/withdrawal operations can change it.
Expected API result: existing successful response, variant-specific conflict,
authorization refusal or controlled failure. No universal exactly-once claim.
Expected UI result: existing success/refusal and current data; no UI edits.
Failure result: object/binding/fact/review-audit changes roll back together;
canonical commit followed by projection failure remains a committed release.
Restart result: new production runtime reads the same committed authorities,
without resurrecting a discarded request workspace or local map.
Recovery result: retry canonical projection recovery returns the same release;
it does not invent a curator decision or reactivate withdrawn work.
Legacy-data result: preserve unconditional, whole-objectset m2 and generation
preconditions separately. Native storage version0 does not promise complete
object_generation invalidation; retain the independent current-history guard.
Required black-box scenario: A prepares a real review; independently composed B
commits a participant/actor/policy/review change; A resumes and uses current
authority. Inject a final durable-participant fault and prove full rollback from
a fresh runtime. Refuse review in the canonical-commit/projection-failure window.
Explicit non-goals: raising timeouts, weakening lineage/source/authorization,
new candidate creation, redesigning sessions, registry or policy, bulk restore as
a supported live writer, and declaring performance/publication restored by CI.

GIVEN one native WorkingRevision and two production runtimes with distinct file
lock paths, WHEN B changes an applicable dependency after A's external source
preparation but before A's protected execution, THEN A's existing variant either
refuses without writes or applies its decision to B's current state; a restarted
runtime observes exactly the durable serial result and no release escalation.

## Rewrite-risk mitigation and architecture decision

Rewrite target: the existing scoped Review command's dependency/commit seam.
Why local patching is insufficient: a faster helper or timeout increase does not
prove current dependencies, atomic durable effects or actual outer lock costs.
This slice adds proof instead of substituting unproved runtime machinery.

Current authority/writer/reader map:

| Truth | Existing owner, writers and consumers |
| --- | --- |
| Source | immutable source store; ingest/reprocessing prepares and activates exact extraction/source views; review verifies them, no alternative candidate creator |
| Working histories | workflow document store; review/revision, heading batch, processing activation and existing source/group commands use existing protected writers; Review and readiness consume current revisions |
| Participants/policy | manage_review_participation and existing policy owner; review and publication read current working policy |
| Roles/retirement | workflow identity store and operator retirement transaction; current command authorization reads it |
| Bindings/audit | workflow review store; ordinary/second/batch/source/policy commands use existing protected delta/event APIs |
| Intrinsic facts | existing review_card_inputs owner in the writer transaction; no cached approval/closure/publication decision |
| Publication | canonical publication store commits exact release/registry; workflow envelope/local mirrors are projections, never serving authority |
| Offline recovery | empty-target publication-chain restore with existing exclusive table locking; not a live write bypass |

Supported runtime topologies: production complete native PostgreSQL composition,
including distinct console runtimes/lock files over the same database; existing
Azure composition shares these workflow owners and adds immutable Blob transport.
File/legacy compatibility APIs retain their existing implementations and tests;
they are not evidence for PostgreSQL concurrency. Model/Blob transports are fixture
boundaries; storage, transaction binding and canonical persistence remain real.

Compatibility/migration plan: no schema, persisted identity or public token change
in this proof slice. All workflow participants keep the one bound connection;
canonical persistence intentionally has its independent transaction.
Persisted-state impact: only isolated test databases receive synthetic fixtures.
Rollback/recovery plan: reverting this proof-only slice changes no runtime/data;
existing production container/database rollback protocol is unaffected. Native
fault/restart and canonical projection-retry proofs verify recovery semantics.
Cutover trigger: none in this slice. A later #729 capability may integrate only
after its affected negative proofs and exact-base performance evidence pass.
Cleanup/decommission criteria: no temporary production path introduced; ignored
measurement prototypes are not shipped. Keep proofs as contract regressions.
Failure blast radius: test hangs/failures are contained to owned disposable DBs;
the protected invariants concern lost review work or unauthorized publication.

Candidates compared: (A) deepen current locked owner with immutable history
sharing/current selection; (B) prepare a speculative plan outside locks then
compare/commit. Independent review identified incomplete native0 generation
coverage and effects/precondition gaps for B. A measured 23s→3.779s in the heavy
synthetic HTTP workload, but still traverses history under the outer lock (3.681s
hold; 28,917,363 JSON bytes received). Neither
prototype establishes bounded history/lock acceptance. They are not runtime
changes in this slice. Retain the existing owner, add the missing adversarial
proofs, and give #729 the measured capability requirements. No hotfix is released.

The required #729 capability must avoid decoding/revalidating the retained prefix
on every decision while preserving append-order lineage and the independent
current-write guard. An unchanged native0 object_generation is insufficient.
Use the existing intrinsic-fact/history owner and its explicit invalidation /
validation coverage; do not turn a derived fact into approval or release authority.
Source/provider work and immutable preparation stay outside real outer locks.
Measure the complete command, facts, bindings, audit, login/GET interference and
outer lock hold/wait on the target-document, unrelated-data and concurrency axes.
The unchanged3s POST budget and250/500ms lock/transaction budgets remain separate
red acceptance conditions, not waived by a faster history helper.

## Adversarial proof matrix and completion limits

| Boundary | Required result / evidence |
| --- | --- |
| Actor retired after preparation | existing current-role denial; no review delta; real retirement ingress |
| Participant archived after preparation | unconditional command denied by current roster, not only stale token |
| Policy adds required participant | current policy consumed; first approval cannot satisfy absent person's evidence |
| Same-version governance/binding winner | generation/m2 conflict without writes; unconditional existing serial result |
| Source/closure | preserve source identity check and protected dependency capture; no scalar-only validity shortcut |
| Equivalent source re-preparation | real source preparation returns the same verified pin; an unconditional decision does not invent a conflict |
| Storage fault after staged binding/object work | actual production review rolls back rows, facts, passes, counters and audit; next runtime remains usable |
| Canonical committed, projection failed | ordinary Review refuses sealed work; retry returns same exact release |
| Alternate ingress and overrides | reuse existing second/batch/source/group, participant, lineage and publication suites; do not infer coverage from one Review method |
| Recovery / stale maps | distinct runtimes plus fresh durable readback; no late stale restoration |

Risk verification is based on lost work, stale authorization and false release
authorization, not diff size. Separate adversarial review must challenge this
matrix before merge. Record exact executed nodes/results and remaining gaps with
the PR. A proof-only green run cannot complete #729, MET-43 or live acceptance.

## Executed verification and adversarial review

On2026-11-01, native PostgreSQL16:106 tests passed across command/storage/state,
dependency, quality, repair/response, missing-source, retained-source, retirement,
source/group, participation, immutability, publication and shared transaction
suites. The final source-handoff/binding/legacy hardening was additionally checked
in5 focused native tests, all passing. No PostgreSQL test was skipped. Commands
and exact head are recorded in the PR/CI evidence.

Independent adversarial review found no blocker in this proof-only diff. Its
three requested improvements were applied: prove actual source preparation and
absence of an outer SQL transaction at the pause, prove B added the exact second
approval, and assert the legacy SQL update actually changed one row. The canonical
peer is deliberately composed before publication: startup after the crash may
legitimately reconcile the projection and would miss the intended crash window.

Repository, architecture, release-control and Python compilation checks passed.
The106-test run is targeted verification, not a claim of full CI or production
acceptance. No runtime code, schema, timeout, acceptance budget, publication rule,
canonical state or production resource was changed. The expensive POST and outer
lock budget remain unresolved under #729; #952 stays In Progress.
