# T11 implementation evidence

## Contract and cutover

Change class: A
Promise: Every new review-relevant knowledge revision has an exact durable predecessor and fresh exact-current review authority, while legacy and published history stays unchanged.
Proof: Tests-first behavioral regressions on main, A–AC adversarial matrix, PostgreSQL/file concurrency and restart, T4–T10/boom parity, full GitHub CI and separate adversarial audit.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: Divergent object revision writers and current-object readers.
Why local patching is insufficient: Type, semantics, relations, context and repair can independently bump versions or rewrite canonical fields without predecessor evidence.
Current authority/writer/reader map: revision_workflow.create_revision is the existing constructor. OperationsConsole writers: confirm_object_type, confirm_relations/_prepare_relation_confirmation (including peer parent updates), review_object, correct_object, accept_source_continuation, reextract_unpublished/resume, promote_class. source_context_review_v1 changes target context (source dispositions stay source-domain). ClosedLoopReviewConsole restores/clears review metadata, reopens review and resolves support. DeterministicRepairReviewConsole finalizes provenance and merges/repairs. review_workflow_v3 and second_review_workflow_v3 prepare governance only; raw review APIs cannot authorize. admission_gate/semantic_transform/materialisation prepare initial candidates and source validity; they are not revision authorities. File _save_objects/_commit_prepared_store, PostgreSQL runtime write_bundle and concurrent override own writes; workflow_transaction owns atomic object/bindings/audit commit. Current readers: OperationsConsole snapshot_objects/snapshot_objects_and_revision, PostgreSQL runtime snapshot/current batch, downstream review duties, T10 containers, readiness, MCP and exports. Canonical publication and registry remain unchanged.
Supported runtime topologies: File compatibility console; PostgreSQL workflow object/review stores with shared transactions; existing canonical/Azure composition, with no Azure access.
Persisted-state impact: Additive metadata revision evidence on new knowledge revisions only, using existing JSON payload. Existing provenance predecessor/reason/patch fields remain. No historical rewrite, backfill or new database schema.
Compatibility/migration plan: Owner-approved forward-only cutover. Missing historical predecessor means unverified, never a proven root. New strict revision may reference the exact stored legacy-current predecessor. Persist contract marker plus exact predecessor evidence in existing metadata (additionalProperties=true). Expand kernel, route writers, validate at existing locked storage boundaries. No parallel store.
Rollback/recovery plan: Revert new writer/reader integration before deployment. Existing JSON metadata remains readable; never remove or rewrite strict evidence or historical hashes. Restart derives lineage solely from stored evidence; invalid strict evidence fails closed. Published legacy releases remain unaffected.
Cutover trigger: New strict object revisions explicitly carrying the persisted contract; never commit time or software version. Deployment is outside this task.
Cleanup/decommission criteria: Remove duplicated knowledge revision construction after relevant paths use revision_workflow. Retain source/structure/boom contracts and legacy read compatibility.
Failure blast radius: Incorrect current selection, lost historical evidence or invalid review inheritance; exact bindings, published immutability and atomic rollback remain independent gates.
Adversarial proof matrix: Original assigned T11 A–AC plus legacy-to-strict transition, missing/forged marker or predecessor, unchanged legacy published read, source/WorkingRevision mismatch and immutable predecessor after restart.
Lifecycle entity: Knowledge object revision within one existing WorkingRevision.
Lifecycle transition: Exact current predecessor -> new version/hash with explicit lineage and fresh review state.
Initial durable state: Open WorkingRevision, exact stored current object, historical rows and optional current approvals.
Trigger: Authorized correction, review semantic change, context/relations change, deterministic repair or same-source preparation mutation.
Authorization: Existing actor roles, named-reviewer, original-source and review-route checks.
Validation: Existing T7–T10 gates, predecessor exact identity/hash and source/WorkingRevision scope, canonical meaning, stale command and published guard.
Mutable entities: New object row/current governance, exact-current authorizations and existing atomic audit/envelope revisions.
Immutable entities: Predecessor canonical content/provenance/hash, historical review evidence, source bytes and all published history.
Workflow state before: Open processing/in_review/blocked/ready state as permitted by existing command.
Workflow state after: Changed revision requires fresh review; a review-induced mutation binds that command only to its resulting tuple. No predecessor approval contributes.
Release state before: Existing none/published/superseded/withdrawn.
Release state after: Unchanged; closed published work rejects mutation.
Serving state before: Existing publication registry serving set.
Serving state after: Unchanged.
Expected API result: Explicit current revision and exact approvals, or atomic conflict/fail-closed.
Expected UI result: Existing review cards reflect new review obligations; no invented user-facing framework.
Failure result: No partial successor, approval invalidation or revision audit on failed commit.
Restart result: Same current revision, predecessor evidence and exact review authority.
Recovery result: Existing technical rollback/replay only; no invented predecessor or inherited review.
Legacy-data result: All existing rows/hashes/reviews/releases unchanged. Unproven history remains unverified. New successor proves only its exact edge to the stored legacy predecessor. Legacy uncertainty never reopens immutable publications.
Required black-box scenario: GIVEN approved legacy/current K, WHEN an authorized change commits, THEN predecessor remains exact, successor has a durable verified edge and no inherited approval, stale retry fails, and restart returns identical lineage and review state with unchanged serving.
Explicit non-goals: T7/T8/T9/T10 redesign; T12 total readiness; cross-source identity/fuzzy matching; source/structure/boom revision redesign; schema migrations, historical backfill, Azure, deployment, ZIP or merge.

Assigned by the repository owner to this coding session, including explicit forward-only legacy cutover authorization on 2026-10-07. Work only through GitHub, branch t11-knowledge-revision-lineage, one draft PR, no merge.
Baseline and T10 merge: 97b87a34268a6e0121a5b09285c0bc8c9528fba6.
Migration: NOT REQUIRED. Stop before a new PostgreSQL column/index/table or historical backfill.


## Implementation map

| Writer | T11 authority |
|---|---|
| Correction | `create_revision(..., snapshot_id=...)` delegates to `revise_object` |
| Type, recommendation semantics and relations (including parent updates) | Prepare successor in `revision_workflow`, then bind review to resulting exact tuple |
| Source-context target mutation | Prepare successor and relation endpoint IDs before Admission |
| Source-context disposition on previously selected knowledge | Same successor kernel; source disposition remains source-domain evidence |
| Continuation and deterministic repair | Existing correction path plus kernel for canonical provenance/metadata finalization |
| Closed-loop review repair | Canonical changes use `_commit_knowledge_change` |
| Same-source re-extraction/recovery | `reprocessed_history` retains prior rows; changed/reappearing candidates create strict successors; missing candidates gain explicit terminal revisions |
| Class promotion from knowledge | Reject destructive cross-model replacement; no invented successor authority |
| Initial materialisation | Existing T8 construction and Admission; no fabricated predecessor |

| Reader / persistence boundary | Authority |
|---|---|
| File snapshot/current/revision | `current_revisions`, append-order projection with strict-edge validation |
| PostgreSQL current/batch | Same projection, supplied WorkingRevision scope |
| Review duty, readiness, T10, exports | Consume existing current readers; no independent highest-semver selection |
| File object write | Existing store/object locks, exact prior rows, lineage validation before atomic bytes |
| Native workflow write | Existing transaction and row lock; validate submission before merge, then merged result before SQL writes |
| Publication | Existing durable envelope/registry guard after authoritative rebase, before any mutation |

## Persisted semantics

Identity is the existing object ID and object version inside one WorkingRevision. The exact review tuple additionally includes the canonical object hash. Source and document identity cannot change across a lineage edge. No text matching, source matching, policy-successor or relation-`supersedes` inference establishes identity.

New successors carry `metadata.revision_lineage.contract = knowledge-revision-lineage-v1` with WorkingRevision, object ID, predecessor version/hash, actor, reason and predecessor-contract status. Existing provenance fields retain previous version, reason and a hash of this evidence. The new canonical hash binds the evidence and new content. Existing metadata permits additive JSON fields: no schema file, PostgreSQL column, index, table or startup migration is needed.

`previous_lineage=legacy_unverified` means the predecessor lacks this strict contract. It does not declare that predecessor a root, or erase any older evidence. The immediate new edge is verified against the actual stored predecessor; older unproven history remains unproven. Readers never rewrite legacy rows to mark them.

A canonical change resets first/second review state; old exact bindings do not satisfy the successor. A review command that also changes semantics authorizes only its resulting exact tuple. Governance-only unchanged review does not manufacture a successor. Historical rows are immutable, including review evidence once a successor exists.

Append order remains the legacy current-selection contract. T11 does not reinterpret old versions using semver sorting. Strict chains reject missing predecessor, forged scope/hash/evidence, cycles/regression, stale forks, marker downgrade, reordered per-object history and in-place canonical rewrites.

## Tests-first and audit evidence

The production-free RED commit was `b29e2f8103a24a5fd706a0c18777473fb452eea6`. [Run 37681435357](https://github.com/WilliamGomes41/Metis-DS/actions/runs/37681435357) produced **4 failed, 3144 passed, 14 skipped**: type review and context changes omitted predecessor evidence, and correction allowed equal/decreasing versions. Retry and stale-command checks were green guards, not claimed RED tests.

A separate adversarial auditor reviewed the implementation and requested stronger immutable ancestor checks, retention of nonknowledge ancestors, relation endpoint rebinding, real publication guarding and authoritative map rebasing. Those findings were repaired with regression coverage. Bounded re-audit at `6fe2fe0a8b31c8c0987ce7afaf8afe09775ebf01` found no remaining concrete code blocker; acceptance remained conditional on final-head CI.

Some legacy tests intentionally create malformed or historical data. Their setup now uses an explicit test-only fixture installer instead of invoking a production mutation command to rewrite existing history. Existing behavioral assertions remain, except the synthetic published-during-processing race now requires the entire sealed envelope to remain unchanged: even a failure checkpoint cannot rewrite published work. Other stale-processing cases still require a failed attempt. The stale-write UI fixture commits its real competing writer after form read and before the review transaction: calling a second synchronous writer from inside the held store lock would deadlock and does not model a legal concurrent commit. Continuation assertions now check both real transitions rather than skipping an intermediate review-context revision. This helper is not imported into production.

## A–AC proof map

| Requirement | Behavioral proof |
|---|---|
| A Initial revision | Existing ingest/materialisation suites plus unchanged legacy initial read |
| B Correction lineage | Integrity sprint, continuation repair; shared scoped constructor |
| C No inherited approval | T11 forward-cutover chain and T9 exact tuple tests |
| D Multiple revisions | T11 forward-cutover chain; continuation compound chain |
| E Missing predecessor | T11 strict corruption `missing` |
| F Cycles | T11 strict corruption `cycle`; correction version regression |
| G No in-place rewrite | T11 locked-storage attacks on file and PostgreSQL |
| H Type review | T11 real type confirmation preserves predecessor |
| I Recommendation semantics | D3.3 human recommendation semantics and exact resulting review |
| J Relations | D4.3 confirmation plus T11 exact endpoint rebinding |
| K Second review | Existing T9 high-risk and integrity review reset tests |
| L Context | T11 source-context predecessor and valid proposed-relation readmission |
| M Continuation | Source-bound continuation repair, including intermediate review-context revision |
| N Deterministic repair | Closed-loop and deterministic repair compatibility suites |
| O Stale/concurrent writers | T11 native stale fork; workflow transaction concurrency |
| P Failed commit | T11 deferred PostgreSQL commit failure rolls back rows, bindings and audit |
| Q Retry | T11 unchanged retry and native idempotence |
| R Restart | T11 file/native restart and strict evidence preservation |
| S Reader parity | T11 native current/batch versus file projection |
| T Policy successor separate | Existing explicit review-policy/lifecycle suites; no policy inheritance path added |
| U Source version separate | Existing live-v1/working-v2 and T10 suites; strict source equality |
| V Same ID across WorkingRevisions | Strict scope corruption plus existing snapshot-scoped storage/review tests |
| W Same text does not establish lineage | No matching path in constructor; T7 source/duplicate identity regressions |
| X Immutable publication | T11 real legacy publication/restart forbidden mutations; existing local/PostgreSQL publication tests |
| Y Relation supersedes separate | T11 relation-supersedes test |
| Z Release supersession separate | Existing successor-release cutover suite; publication registry untouched |
| AA T9 parity | Dedicated T9 CI gate |
| AB T10 parity | Dedicated T10/source-container/source-context CI gate |
| AC Boom separation | Existing architecture/boom regression suite; kernel scope excludes boom |

## Completion report (30 requested items)

1. Baseline main: `97b87a34268a6e0121a5b09285c0bc8c9528fba6`.
2. T10: PR #535 merged at that baseline; Azure acceptance remains a separate owner exception.
3. Writer map: above.
4. Reader map: above.
5. Existing contracts: exact-current T9 review, T10 source accountability, T8 Admission, immutable publication and existing atomic workflow transaction.
6. Original gaps: direct version bumps, canonical in-place repair, divergent current projections and history-destructive reprocessing.
7. RED proof: linked production-free run above.
8. Green guards: unchanged retry and stale command; not relabeled as RED.
9. Identity: object/version in WorkingRevision; exact hash for review.
10. Predecessor: exact durable earlier row of same object/source/WorkingRevision.
11. Current authority: shared append-order validated projection.
12. Review-induced revisions: kernel before final exact review binding.
13. No silent carry: reset governance/second review, retain old bindings only on historical tuple.
14. Transaction: existing file rollback and PostgreSQL transaction; no new transaction store.
15. Concurrency: locked validation of authoritative prior rows and optimistic merge.
16. Retry: unchanged command does not append artificial version.
17. Restart: marker and exact predecessor are persisted in object JSON.
18. Cross-source: rejected; no inferred identity.
19. Published history: untouched; durable publication guard rejects all mutations, including no-op review commands.
20. T9: unchanged authorization authority, dedicated gate.
21. T10: unchanged source evidence authority, dedicated gate.
22. Boom: excluded from knowledge lineage redesign.
23. Migration: **NOT REQUIRED**.
24. Migration blocker: none encountered; no PostgreSQL schema change or historical backfill performed.
25. Production files: revision_workflow, operations_console_v1, source_context_review_v1, closed_review_loop_v1, deterministic_review_repair_v1, review_closure_v1, workflow_documents_cutover_v1 and workflow_document_concurrency_v1.
26. Tests: new T11 behavioral suite, adapted historical-data fixtures, existing full regression suite.
27. CI: final exact-head run and totals are recorded in the draft PR; earlier run results are not a substitute.
28. Head: exact final SHA recorded in the draft PR and delivery response.
29. PR: one draft PR for #536; no merge.
30. T12: total readiness consolidation remains outside T11.

No Azure action, deployment, production migration, merge or backfill is part of this change. Merge remains **NO-GO** until the owner's separate approval and release gates.
