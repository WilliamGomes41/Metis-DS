Change class: A
Promise: New decision PDF processing presents source-bound complete decision units for review and retains ambiguous fragments as repair work.
Proof: Fragmented questions, branch labels, columns, neighboring units, source fidelity, graph updates and restart are exercised through real ingest/review commands.
Touches lifecycle invariants: yes
Rewrite risk: high

## Domain-first assessment

Established: `decision_graph_v1.pdf_fragments` assigns every PDF block `node`;
`boom_spec_from_fragments` creates one object per block. Graphic route proposals,
version-bound graph review, source verification and graph publication validation
already exist. The boom Admission shortcut and boom review-duty shortcuts admit
fragments without construction evidence. Bullet bundles are an existing exception.

The kernel's existing WorkingRevision owns objects, evidence, graph and review.
Grouping, role proposals and validation are stateless computations. Persisting
their output during ingest or graph update is stateful work. No new
authority, schema, lifecycle or console-owned state is introduced.

Reclassified during the surface review: new branch labels close as source context
through exact graph interpretation, rather than receiving a false node approval.
That touches review closure required for publication and therefore is Class A,
even though it reuses existing lifecycle states and transaction boundaries.

## Exact lifecycle slice

Lifecycle entity: Existing WorkingRevision and its exact source-bound graph/object set.
Lifecycle transition: Prepare decision units in_review; a source-grounded graph edit admits complete units and binds labels as graph context; exact passage and graph confirmation complete the existing review contract.
Initial durable state: Immutable source snapshot and open WorkingRevision; no newly constructed units or graph approvals.
Trigger: New decision-PDF ingest (or existing explicit unreviewed retry/successor); subsequent named-reviewer graph command.
Authorization: Existing researcher ingest authorization, named reviewer graph/review authorization, explicit review policy and optimistic expected_revision.
Validation: Exact source reconstruction, unit admission, graph endpoints/labels/graphics/reachability, source re-verification and current tuple review evidence.
Mutable entities: Open WorkingRevision objects, derived admission/register, graph, graph-review evidence and current tuple bindings.
Immutable entities: Source bytes/checksum, published object history/releases, existing reviewer events and publication registry history.
Workflow state before: Processing during preparation, then in_review with construction/route repair pending.
Workflow state after: In_review until exact passage and graph review are complete; readiness remains derived by existing curation/technical gates. No new workflow state.
Release state before: Any existing release remains published/superseded/withdrawn under its original authority.
Release state after: Unchanged by this slice; publication uses the existing canonical release command.
Serving state before: Existing publication registry active set, if any.
Serving state after: Unchanged; construction or graph repair never activates a release.
Expected API result: Existing ingest receipt and graph-command receipt; no Product API schema change or graph serving before existing release authorization.
Expected UI result: Complete units become ordinary review work only after structural validation; unresolved units remain repair; labels are branch evidence and not node proposals.
Failure result: Invalid/uncertain source remains open repair; failed preparation/commit leaves prior objects, graph, review and release untouched.
Restart result: Same objects, ordered spans, graph, source-context register and tuple approvals; re-verify source against the correct old/new extraction adapter.
Recovery result: Existing idempotent ingest/review commands and explicit successor; reviewed/published work is never reset or re-extracted silently.
Legacy-data result: Markerless snapshots retain their adapter/admission contract and published hashes; no SQL migration or startup backfill.
Required black-box scenario: Ingest a fragmented question with Ja/Nee and two outcomes; graph repair admits three complete units, labels remain evidence; review exact units, refresh endpoints, confirm graph, restart and verify source/review. Concurrent/stale graph commands and failed commit preserve prior work.
Explicit non-goals: No serving/cutover change, publication-registry replacement, model service, free generated source text, destructive migration, automatic clinical validation or inferred cross-version object lineage.

The publication/withdrawal/successor kernel is reused unchanged. Existing decision
chain and successor tests cover release/restart isolation; native PostgreSQL
variants require their configured test database and must remain reported as
NOT TESTED locally when that database is absent.

A decision unit represents one complete source function. Questions, actions and
outcomes remain node/outcome proposals; role evidence is metadata. Branch labels
remain source passages for coverage/repair and graph evidence, never active nodes.
Atomicity is not one sentence, block or line. Partial or unknown meaning remains
explicit. A source box is evidence of grouping, not proof of semantic correctness.

Hard invariants: exact ordered source spans with original locators; no generated
words; no cross-page or cross-container merge; no branch label as active graph
node; incomplete units cannot enter ordinary review; graph labels must remain
literal; no inferred edge solely from reading order. Human interpretation remains
required for routes. No claim of clinical or semantic equivalence is automated.

Policy defaults: conservative enclosure/alignment plus continuation grouping;
uncertain geometry or grammar remains repair work. Recognized Boolean labels are
proposals, not an exhaustive enumeration of all possible answers.

Durable state before: existing snapshot, object history, bindings and graph.
Durable state after: complete prepared object set and graph/evidence in the same
existing snapshot commit. Graph edits version affected objects and invalidate
only affected tuple reviews through existing commands.
Transaction boundary: `_commit_prepared_store` and the existing native workflow
transaction/CAS commit envelope, objects, bindings and audit together. Source
extraction/validation happens before commit. Failure preserves prior work.
Failure/recovery result: invalid construction fails closed; retry uses existing
source and command identity. Reviewed work requires the existing successor command;
never delete/re-upload or backfill existing snapshots.
Duplicate execution / idempotency result: deterministic grouping identity from
ordered spans; graph command ledger rejects changed payload under same command ID.
Concurrency result: existing expected object revision, store lock and PostgreSQL
transaction serialize graph/review changes; stale writes fail.
Audit/evidence requirement: retained original fragment IDs/locators, ordered spans,
grouping signals, literal hash, source checksum and construction reason codes;
existing graph command audit records actor and old/new graph hash.

## Rewrite mitigation

Rewrite target: additive construction semantics on new decision PDF units.
Why local patching is insufficient: skipping fragment admission lets layout blocks masquerade as knowledge units.
Current authority/writer/reader map: WorkingRevision owns truth; ingest/reextract prepare, graph commands version; admission, passage register, review duties and graph checks read evidence; publication registry stays serving authority.
Supported runtime topologies: local snapshot store and native PostgreSQL workflow stores through unchanged commit/transaction boundaries.
Persisted-state impact: additive versioned metadata only on newly constructed PDF objects; no migration or retrospective interpretation.
Compatibility/migration plan: existing freeze adapter and legacy snapshots retain their contracts. New PDFs use a versioned construction marker; existing snapshots require explicit successor work to gain it.
Rollback/recovery plan: disable new construction by reverting the PDF spec adapter while retaining the marker-aware readers for existing new objects; old binary rollback is not asserted. No data removal.
Cutover trigger: new PDF extraction/spec generation, after regression checks.
Cleanup/decommission criteria: no temporary authority or dual writes; legacy snapshot readers stay until retained snapshots expire under existing policy.
Failure blast radius: new decision PDF candidate admission; published source, reviewed history and serving registry remain unchanged.
Adversarial proof matrix: invented text/spans, reversed extraction order, cross-column adjacency, label-as-node, missing labels/routes, stale source evidence, interrupted ingest, duplicate graph command, stale revision and restarted store.

## Acceptance matrix and slices

| Scenario | Required observation |
|---|---|
| Two/five aligned continuations in a source box | One exact ordered unit, all source refs |
| Nearby complete questions / separate columns | Separate units |
| Ambiguous overlap or missing geometry | No guessed merge |
| Ja/Nee | Coverage/evidence retained, excluded from ordinary node review |
| Complete short question/action | No arbitrary word-count rejection |
| Dangling question/action | Blocked with construction diagnostics |
| Invented text or modified spans | Source fidelity error |
| Unresolved route | Existing graph repair/confirmation remains required |
| Graph edit / retry / restart | Existing identity, CAS and audit semantics preserved |

Slices: construct source units in the PDF-to-spec adapter; enforce construction
admission through kernel review routing; validate graph role usage and keep the
existing graph review/recovery commands. No new persistence type or model service.

Remaining uncertainty: conservative rules cannot recover every linguistic unit or
complex drawing. Ambiguous sources remain explicit repair work. The CSV supplies
text/boxes but no original connectors, so complete source graph equivalence cannot
be proven from that export. Model grouping is not required to fabricate missing
evidence; a future provider may propose exact groups under the same contract.

## Adversarial surface review and verification

Separate review after integration challenged transform metadata, type confirmation,
ordinary/secondary/structure review routing, graph drafts/confirmation, object
correction, source verification, successor extraction and markerless restart.
Findings fixed: ordinary boom admission bypass; legacy snapshots accidentally
inheriting new admission; composite PDF blocks spanning separate boxes; graph
admission remaining blocked after repair; source-context mode hiding stale text
or provenance. Source-parent offsets/checksums survive line splitting, and source
hashes are checked even for labels. Ambiguous geometric routes stay proposals.
Grouping scans use page/vertical indexing rather than an all-fragment pair scan.

Latest targeted verification: 39 passed, 6 skipped, including 15 new construction
regressions plus graph chain, bundles, successors, review UI and architecture.
Full suite on the final implementation rebased onto main a2ad53c: 2488 passed,
158 skipped, one failing transport-worker cleanup test. The same test fails on
unchanged main a2ad53c in this environment. Network mock tests pass without the
environment proxy. No unrelated transport/security production code was changed.
Repository preflight, compileall, release-control mapping, change contract and
Product API compatibility pass. The advertised architecture script is absent;
the CI architecture tests were run instead. Native PostgreSQL proof remains
NOT TESTED locally because no test database is configured. This is a draft,
not a claim of completed production acceptance or equivalence of the actual PDF.

Existing immutable source and publication authorities are unchanged. No production
deployment, SQL migration, backfill, destructive operation or second state owner.
