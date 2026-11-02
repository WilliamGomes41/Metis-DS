# MET-36: bounded revision inputs under the document owner

Change class: A
Rewrite risk: high
Promise: ordinary review/source decisions validate the current transition without
reloading a retained historical prefix on every decision; atomicity, lineage,
current dependencies and existing precondition variants remain effective.
Base: `3cc653bc26fd61748bd9f0b402c012b846dc0d27`. This implements the first bounded
ordinary/single-source mutation slice of #729 under #959, consuming #952's
dependency/atomicity proof. It does not
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
  detects an extra same-connection mutation before resealing. Each intended SQL
  write must return exactly one row with the planned physical identity, position
  and exact JSON; BEFORE-trigger alteration/suppression cannot seal a wrong prefix.
- The certificate retains the original lineage owner's hidden-prefix knowledge
  and publication inputs, excluding the current boundary head. The current head
  and each new edge still undergo the existing strict self-hash/transition rules.
- Source admission includes actual ordered neighbours, including unlinked
  conditions and heading sentinels. Indexed order is derived from validated heads;
  absent/unprepared indexing selects the explicit complete legacy adapter.
- Every object-write trigger shares the existing document row serialization,
  including native0. Unselected source order cannot commit during a protected
  command. Supported runtime ingress retains document-before-object locking;
  arbitrary direct SQL with inverted order may safely deadlock/rollback, as with
  the existing native1 generation writer. No deadlock-free arbitrary SQL claim.
- Migration032 seeds identifier coverage only (NULL certificates), uses a deferred
  FK preventing index deletion from hiding existing objects, and a fail-closed
  JSON/hash/epoch CHECK. Existing object-writer SELECT/INSERT/UPDATE grantees receive
  exactly those index grants atomically with migration; no DELETE/ALL/PUBLIC.
- Source-context preflight opens original source outside the protected lock;
  exact captured head/source identity pins the result at commit. The original
  source representation owner supplies retained accepted fragments. No model,
  extraction or second source-role writer runs on the prepared single-command path.
- D1 explicitly uses account KEY SHARE only in the bounded Review command and
  sign-in NO KEY UPDATE. Processing/admission and other current callers retain
  their original FOR SHARE fence through commit. Retirement still refuses
  the next command; this introduces no stronger in-flight cancellation promise.

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
identifier-only coverage seed and deferred physical-coverage FK; no content,
identity, release or source backfill. Table triggers serialize legacy writers too.
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


## Scope and retained work

This slice changes actual production ingress for ordinary Review and individual
`confirm_source_context`. The source bulk/group adapter remains explicit legacy
behavior; D2 supersession, V3 removal policy, complete route inventory, independent
cross-document concurrency and production existing-data acceptance remain open in
#729/#959/#953. Do not close MET-36, MET-43 or MET-44 from this PR. MET-35's source
writer consolidation is not absorbed. Old m2 callers intentionally retain full
objectset equality; generation and None contracts are unchanged. Receipt-first
old-m2 duplicate handling and generation-form stale409 remain distinct contracts.

The component diagram is [bounded-review-mutations-729](../architecture/bounded-review-mutations-729.md),
linked from the existing Alles over Metis document-storage model.

## Executed local evidence and limits

Red-test/design commit `877e0bbde65780e0f8fa88901e26876ce8918c93`, based on main
`3cc653bc26fd61748bd9f0b402c012b846dc0d27`, reproduced the retained-history HTTP
save at **22.654s**, above the unchanged 3s budget. A separate negative test
refused any full-prefix read on the prepared ordinary command path.

The first implementation run saved in **0.362s**; the subsequent full-chain run
saved in **0.325s**, opened in1.256s, redirected in3.125s, reopened in1.243s and
rejected the stale form in0.065s. The full-chain test also preserves another
reviewer's decision and refuses incomplete publication. The latter run recorded
outer hold **250.537ms** and transaction250.506ms: ordinary250ms lock acceptance
is explicitly **not proven** by that measurement. Subsequent exact final-tip
measurements and suite results are recorded in the PR/evidence summary, not
inferred from this earlier run.

The real single-source HTTP operation measured small/1500-retained-history/
1500-history+24-independent-documents+1000-events+1000-bindings at0.126/0.121/
0.162s with outerholds74/77/106ms in the initial focused run. It forbids global
object/event/binding readers, re-extraction, full writers and source I/O inside
the protected lock. These are local synthetic measurements, not productionlatency.

The eight current-dependency/atomicity tests from MET-43 proof commit
`36112a6f1559601e77d96ab098a682e20f3727dd` passed against this implementation,
using this checkout's actual source modules. Existing source-context publication,
successor, withdrawal and restart regression tests also passed. Dedicated native
negatives cover direct/native0 historical edits, truncation, stale/wrong-store
carriers, physical/payload identity mismatch, invalid strict self-hash, hidden
historical protection, preparation CAS races, raw numeric equality and ordered
transition substitution. Exact rows/counters/index state are compared at refusal.

Independent adversarial review found strict-head self-hash, source-neighbour,
physical-identity, SQLNULL CHECK, Python-numeric equality and actual written-row
holes. All require concrete negative proof before PR review; no green-suite-only
safety conclusion. Existing-data preparation and live original failing-URL proof
remain MET-44 after authorized merge/deployment; no production action here.

The full6804-node local suite executed:6754 passed,43 expected optional-profile
skips (zero PostgreSQL skips), seven failures. Five were old migration-schema
mocks missing the new required constraints; two exposed an overbroad D1 lock
change that weakened the existing processing/admission revocation fence. The
implementation was narrowed to an explicit Review-only KEY SHARE option; default
current account reads retain FOR SHARE. After repair, all84 processing, Entra,
retirement and migration tests passed. The independently reviewed narrowing
preserves the different existing authorization contracts. Full-suite exact final
CI remains required; this earlier full run is not reported as all-green.

## Adjustment after system-wide verification (user GO: adjust PR965)

Ground: the same six-head/1500-history source batch takes main11.10s versus
PR13.11s; seal_complete itself adds2.00s. Targeted ordinary Review remains fast,
but the legacy batch still reloads global maps/source/history under its lock.

Usage: callers retain write_bundle and source exclusion/group operations. The
existing store captures PhysicalObjectHistory from its actual locked SQL rows,
validates the original transition once, verifies every intended SQL delta row,
and receives a WrittenObjectDelta usable only on that store/connection/snapshot.
After fact maintenance the receipt independently compares all document epochs and
physical identities/positions, then seals final heads/counts/prefix facts already
validated by the original revision owner. No second full-payload or lineage pass.

Candidate A (selected, also independently proposed): deepen the shared actual-SQL
owner with a detached physical baseline and verified write receipt. Every full
writer uses the same operation; new and legacy/prepared writes keep valid derived
frontiers. Generic full-list compatibility retains its original necessary check.
Candidate B (rejected): stop generic resealing or let callers supply proof and
prepare later. This either loses physical SQL validation or invalidates inputs
and restores the22s ordinary Review fallback after another operation. Dirty-ID
special cases alone leave the same duplicate work when the changed head has a
long prefix. Correctness, shared ownership, unchanged caller API and no repeated
prefix read favor A; no new persisted authority/schema is needed.

The existing source-role writer remains the only rule owner. Exclusion/group
commands capture selected/shown members and actual graph/context dependencies,
prepare source outside the outer lock, check the original precondition variant
and current role/roster/seal under protection, and stage object/binding/audit
changes through execute_review_command. Legacy m2 keeps whole-objectset equality
and receipt-first retry semantics; generation forms keep stale409 before replay.
One invalid member or late write/audit failure rolls back the entire group.

Proof before deployment: red native no-second-full-seal test; exact physical
BEFORE rewrite/suppression/position and extra AFTER/same-connection mutations;
prepared/unprepared generic write parity and positive frontiers after success;
real1500-history source HTTP with scoped bindings/events and no original-source
I/O under lock; unchanged source/group/idempotency/precondition/role/canonical
and archive recovery tests. Preserve3s total,250ms outer hold and500ms transaction
claims separately; legacy m2 cost is explicitly not a bounded generation claim.

Formation/diagnostic GETs, provider scheduling, D2/V3 and live existing-data
acceptance remain explicit remaining scope. No blanket performance or deployment
GO follows from this adjustment. No timeout increase or guard removal.


### Authorized implementation and verification

The user explicitly authorized resolving the Review failures and slowness,
including the shared storage and source transaction scope above. The earlier
automatic-review rejections preceded that authorization; they are not an active
implementation blocker. No merge, production migration or deployment follows
from this code authorization.

Implemented: store/connection/snapshot-bound physical baseline, exact SQL
RETURNING checks, native epoch-map and final identity/order verification,
detached final plan and original validator's current-head result. Generic writers
keep a positive frontier after success without a second full history seal.
Source exclusion/group/reset reuse execute_review_command and the existing
source-role writer, scoped bindings/receipts, exact retained predecessor reads
for reset and one atomic commit. Legacy m2 keeps receipt-first whole-objectset
semantics; generation forms refuse stale submission before receipt replay.

Group eligibility includes incoming automatic block/span context via the existing
031 generated lookup, in addition to OID/manual context and adjacency. The
original partition owner still checks exact interval coverage. Reset refuses any
captured source/fragment failure before staging. These were independent review
findings, both corrected with native regression tests.

Current-only pure reads use the existing validated frontier within a consistent
read transaction and retain the full legacy adapter when unprepared. Source
accountability forms capture current objects, generation and bindings in one
snapshot. Full-history processing tokens are generated only for an actual
start/resume form, with its rows; the processing command CAS is unchanged.

Measured same1500-history/six-current-head source HTTP: original12.007s, adjusted
legacy-m2 adapter1.034s (0.894s outer hold); compact generation0.243s (0.203s outer
hold). The old m2 equality is intentionally expensive; it is not the token emitted
by the updated source accountability form. Formation detail GET median falls
from about2s to0.079s in this fixture. Other-document/event/binding noise remains
within the3s total budget without global reads. No timeout or lock budget changed.

Native proofs include actual BEFORE rewrite/suppression/position errors,
unexpected AFTER/same-connection history/new-ID writes, late deferred audit
failure, wrong connection, legacy schema, metadata-only writes, distant automatic
context, missing source fragments on reset, stale generation and preserved
frontiers. Original1100-history/25MB partial-formation HTTP and actual archive
restore/preparation are re-run. Per-run results and limitations are recorded in
evidence/bounded-review-729/adjustment-results.json. Exact-head CI and production
acceptance remain separate; no current production improvement is claimed.
