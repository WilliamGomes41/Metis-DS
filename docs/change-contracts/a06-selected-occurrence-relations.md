Change class: A
Promise: Independently selected occurrences with distinct spans retain their materialised IDs and exact incoming/outgoing relation endpoints through V3 ingest, commit and restart.
Proof: Red-before-green V3 ingest regression, reversed proposal order/section ranks, evidence isolation, replay/retry/resume compatibility, invalid endpoints, failed preparation/commit; file and native PostgreSQL workflow evidence and repository checks.
Touches lifecycle invariants: yes
Rewrite risk: high

Explicit assignment: User assigned A06 repair on 2026-10-11 to the Metis Engineer profile. This is the sole implementation ticket; #556 is progress/production acceptance only. Scope: implementation and reviewable PR; no merge/deployment.

Rewrite target: source_occurrence_authority_v1 shared post-materialisation selector.
Why local patching is insufficient: Merely linking relations earlier leaves later deletion possible. Extend the existing selector locally; explicitly reopen T7's one-candidate rule for independent selected spans, retain binding isolation.
Current authority/writer/reader map: knowledge_materialisation_v1 alone creates semantic IDs/spans/mapping; semantic_passage_v1 validates selections and attaches exact relations. pre_review_semantic_v1 and context_aware_split_v1 call the selector. semantic_transform_generic_v1 and admission consume intact rows. OperationsConsole ingest/reextract/retry/resume and source_selection own authorized preparation/activation; source_preparation_context pins source/attempt/revision. Existing workflow_transaction/_commit_prepared_store/PostgresConcurrentWorkflowDocumentStore commit bundle. Review bindings/readiness/publication readers consume existing stored objects; publication registry remains serving authority. Runtime bindings in ASGI/CLI share the kernel. Replay identity/exact_replay_lookup controls reuse.
Supported runtime topologies: File workflow and native PostgreSQL workflow documents/reviews/identity, existing immutable source and canonical/publication adapters. Synthetic provider; no live-provider or Azure-production acceptance claimed.
Persisted-state impact: Future open WorkingRevision bundles can contain several selected identical texts. No ID formula/schema/backfill/release rewrite.
Compatibility/migration plan: Tests-only red stage then local selector extension; version the occurrence rule in semantic replay identity. Old checkpoints cannot silently replay/resume under the new rule. Existing stored objects remain readable and unchanged; new authorized work uses the current contract. No dual authority.
Rollback/recovery plan: Revert code before deployment if proof fails. After cutover retain complete stored bundles/reviews; do not run an older producer on new work without compatibility proof. Suspend new formation and use current reader or forward repair. Existing authorized open-revision/successor route only.
Cutover trigger: Separately reviewed merge and authorized deployment, neither part of this run.
Cleanup/decommission criteria: One selector, one materialiser and one workflow authority remain; remove temporary probes. Source-only/deterministic folding remains.
Failure blast radius: Newly prepared working candidate set; existing source/review/publication controls remain.
Adversarial proof matrix: outgoing/incoming endpoints; different blocks/spans and same text; section ranks/order; isolated field/context evidence; same-span conflict/ambiguity; invalid blocks/bounds/type/unselected endpoints; legacy replay/resume; retry; stale source/revision/actor/attempt; rollback/commit failure; file/PostgreSQL and restart.

Lifecycle entity: WorkingRevision derived from immutable SourceSnapshot.
Lifecycle transition: Existing authorized ingest/reprocessing prepares then atomically commits the complete working object bundle with proposed relations.
Initial durable state: Immutable received source plus reserved attempt; new or open unreviewed working revision, optionally an existing immutable release.
Trigger: Existing ingest or authorized reprocessing command.
Authorization: Existing researcher/source-selection authorization; named review and publisher commands unchanged.
Validation: Source/hash/version/revision/attempt ownership, V3 span/field/context checks, exact relation resolution and admission. Same-span ambiguity/conflicts remain rejected.
Mutable entities: Prepared working candidates/proposed relations and existing attempt/envelope, through existing workflow transaction.
Immutable entities: Source bytes, prior review evidence, published objects/releases.
Workflow state before: Processing or open WorkingRevision.
Workflow state after: Existing review obligations/readiness derived from all selected occurrences; no new state.
Release state before: Existing release or none.
Release state after: Unchanged.
Serving state before: Existing registry-selected release or none.
Serving state after: Unchanged; formation cannot publish.
Expected API result: Both selected occurrences and correct exact relations in the snapshot object bundle.
Expected UI result: Each independent selected occurrence is its own review target; no transferred approval.
Failure result: Invalid preparation/failed commit leaves prior durable work intact.
Restart result: Same IDs, spans, mapping, context/field proof, relations and bindings reload from durable workflow.
Recovery result: Idempotent duplicate command or explicit conflict; old incompatible checkpoint cannot silently resume.
Legacy-data result: Read existing objects unchanged; no automatic backfill, approval inheritance or published mutation.
Required black-box scenario: GIVEN HTML with three selected occurrences, two identical at distinct source positions, WHEN actual V3 ingest with incoming/outgoing relations commits, THEN three independent IDs and exact endpoints survive transformation/admission/storage/restart; same authorized command adds no objects/relations. Failed replacement preserves earlier durable bundle.
Explicit non-goals: Production causality, live model content quality, automatic backfill, old approval adoption, new alias/materialiser/workflow authority, adjacent audits, merge/deploy.

Context contract:
| Datum | Producer | Consumer | Owner/storage | Lifetime | Validity | Missing/stale |
|---|---|---|---|---|---|---|
| snapshot/document/source hash/version | ingest/source store | producer/replay/activation | existing envelope/source preparation context | frozen source | exact source match | reject |
| attempt/actor/expected revision | reserve | checkpoint/activate | existing processing_attempts/workflow | one authorized attempt | current authority and CAS | reject stale activation |
| candidate ID/ordered spans | materialiser | selector/transform/review | existing semantic metadata/object bundle | working object | intact same occurrence | validation rejection |
| fragment refs/source mapping | source reconstruction/materialiser | transform/source readers | same candidate provenance | source-bound | exact own source span | reject, no transfer |
| field/context evidence | V3 validator | admission/review | same candidate metadata | source-bound/review tuple | exact own evidence | reject/retain unresolved per current contract |
| relation proof | validated proposal/exact resolver | transform/review/storage | proposed relations + relation evidence in same bundle | working review tuple | both exact selected endpoints | reject |
| replay identity | producer | retry/resume | existing semantic_replay | contract version | exact source/config/occurrence rule | reject incompatible resume; authorized fresh inference only |

#556 stays open pending separately evidenced deployment and production acceptance.

## A06 verification and separate adversarial review (2026-10-11)

Reviewed production revision: `6056b4373c2077e80ed00e6d99c46b218373fd34`;
base `09bedd447b0b4dead980a078360a26002b054c5c`. The subsequent CI-only
commit exposes the existing A06 tests as a named native PostgreSQL step.

Confirmed cause: the original shared selector folds selected equal-text rows
before exact relation attachment and deletes a valid source or target. The same
V3 ingest regression failed in all 12 direction/order/section combinations on
the unmodified base. Bypassing only that selector on the base made all 12 pass,
without changing materialisation or relation resolution. On the repair they pass
with the selector enabled. The different-text control also passes.

Executed evidence:

| Boundary | Evidence | Result |
|---|---|---|
| File V3 ingest and reload | 12 outgoing/incoming/both × reversed-order/section variants | Three admitted candidates; exact IDs, own spans, source lineage and endpoints retained |
| Field/context isolation | Different literal field evidence and adult/child context on identical candidate text | Own evidence and fragment mappings retained; no semantic or approval transfer |
| Retry/replay | Authorized retry and reextract after reload | No extra objects/relations or provider call for compatible replay |
| Old replay/checkpoint | Existing replay identity changed to the earlier occurrence contract | Fresh authorized inference; incompatible resume rejected without overwriting stored work |
| Invalid endpoints | Unknown block, invalid bounds/type, unselected endpoint, ambiguity, same-block distinct offsets | Existing exact validation rejects invalid/ambiguous proposals; distinct selected offsets survive |
| Failure and stale activation | Preparation failure, injected bundle-write failure, another runtime changing revision or authority | Durable winning object bundle retained; no successful stale attempt |
| Fresh process | File and native PostgreSQL object/binding projection read in a new Python subprocess | Identical stored IDs, spans, mapping, fields/context, relations and review bindings |
| Native backend and concurrency | Existing full suite with PostgreSQL 16.15 workflow authority | PostgreSQL A06 tests and existing transaction/concurrency/commit-failure regressions pass |

Native evidence: [CI run 38144693203](https://github.com/WilliamGomes41/Metis-DS/actions/runs/38144693203),
jobs `114485517667` (Python 3.13) and `114485518076` (Python 3.12), each
**3575 passed, 15 skipped**. Both complete jobs succeeded; 3.12 browser checks
also passed. A06 backend tests require the CI-provided native DSN and are not
among the local backend skips. Local focused execution: **74 passed, 4 skipped**
(the four native PostgreSQL cases). Repository/release preflight, compilation,
architecture-boundary check and architecture invariants (6 tests) pass.

Separate adversarial review: both selector callers were traced. The semantic
caller supplies materialised proposal-selected rows, then exact relation
attachment; the deterministic splitter supplies unstamped rows and retains its
existing folding. Heading/source-only behavior has no new authority. Selection
and relation validators retain same-span conflict/ambiguity rejection. The
selector copies complete rows and alternate occurrence metadata only; no donor
fields, ID aliases, review transfers or second materialiser are introduced.
Source preparation and activation still enforce current source/version/hash,
revision, actor authority and active-attempt ownership in the existing kernel.
Replay mismatch prevents a partial old checkpoint from being silently promoted.
Published objects and serving authority are untouched. Rollback retains durable
work and suspends incompatible formation; it does not rerun an older selector on
new selected endpoints.

Minimal-code-surface review: **surface verdict APPROVE**. Before the named CI step,
9 files changed, 541 additions/77 deletions; only two production files change
(48 additions/50 deletions). The selector measures 140 nonblank LOC, maximum
cyclomatic signal 11 with the bundled AST metric. Its two-phase grouping and
complete-row output remain local; no new abstraction is warranted. Highest-risk
branches distinguish proposal-selected rows from source-only rows and exact
alternate provenance. No duplicate validation or text-based fallback was found.

Engineering readiness: **READY WITHIN STATED LIMITS** for repository review of
the synthetic-provider V3 kernel slice. The restart boundary is a fresh
application process against the same durable storage, not a database-server
restart or Azure instance failover. The A06 rollback case injects a failure
after the native bundle write inside the transaction; actual deferred PostgreSQL
COMMIT failures are covered by unchanged transaction regressions in the full
suite. Live-provider quality, production causality and production deployment
acceptance remain unproved. No backfill or historical release change occurred.

Local implementation and remote branch are available. Merge and deployment
are not performed. Progress issue #556 remains open.
