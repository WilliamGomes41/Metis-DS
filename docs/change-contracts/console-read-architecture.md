# Console read architecture recovery

Change class: B
Promise: Opening console pages and document data uses operation-owned reads with bounded overview payloads, without changing durable workflow decisions.
Proof: Production-composition HTTP cost regressions, PostgreSQL isolation/freshness/authorization tests, existing page and lifecycle scenarios, and same-protocol before/after measurements.
Touches lifecycle invariants: no
Rewrite risk: high

User assignment: the supplied recovery request explicitly authorizes investigation,
local implementation and reviewable PR preparation across the listed slices. This
run follows that scope instead of the default one-assigned-issue start condition.
No merge, deployment, production mutation or lifecycle rule change is authorized.

## Ground and design gate (before implementation)

Base: 60bc697; production comparison: 7152bab. The intervening changes affect the
Bronselectie card and its characterization fixtures, not the storage/read boundary.
`console_asgi.build_app` selects the FastBadge CompleteWorkflow Durable/Azure
console classes, with concurrent document store, PG identity/review/remaining
stores, canonical PG and (Azure) immutable Blob. `build_console_app` replaces the
old publish GET through `install_publish_readiness_ui`. Only one/two workers on
one instance are supported. No file workflow topology is supported.

Existing mechanism: `source_selection_read_scope` owns a ContextVar dictionary;
only list-first reads populate envelopes. Single reads do not populate it and
copy twice into/from the process map. `list_envelopes` outside that scope reloads
all envelopes into `_envelopes`; writers and retrieval have depended on that side
effect. The dispatcher scans all envelopes every second, then reads them again.
Review binding reads also refresh shared process state. Commands use StoreCommand,
process-shared locks, workflow transactions, row locks and optimistic revisions.

Intended behavior: explicit overview operations select only overview inputs;
detail reads own their envelopes and objects from the first read, irrespective of
list order. Reads must not refresh writer maps. Commands continue loading current
working state through their existing transaction and reload boundary. Source,
materialisation, candidate identity/mapping, review/publication decisions and
recovery rights remain unchanged. Any discovered need to change these semantics
requires reclassification before implementation.

### Two alternatives (one model, not independent assessments)

1. Extend list-first context reuse to every route. Small initial diff, but caller
   ordering, full envelope/object loads and process-map side effects survive.
2. Explicit compact operations and operation-owned detail snapshots. Select at
   the database boundary, use existing authorization contracts and transaction
   binding, retain defensive copies only at caller/command boundaries. This
   removes overview dependence on reconstruction and does not add durable state.

Choose 2. Existing reconstruction scopes remain the owner of source validation
reuse. No new generic cache, projection table, migration or observability layer.
Usage: document overview(account, filters/page); notices(account, bounded scan);
detail read operation -> existing authorized domain readers. Errors remain errors;
unmeasured/unavailable values remain explicitly unknown, never readiness.

### Rewrite mitigation

Rewrite target: shared document read boundary and its overview consumers.
Why local patching is insufficient: first-read reuse, payload selection and writer
map dependencies cross source selection, Review, diagnosis, Inzicht and dispatch.
Current authority/writer/reader map: see dependency appendix and owner table below.
Supported runtime topologies: both production FastBadge classes, concurrent PG;
local verified source directory or authoritative immutable Azure Blob.
Persisted-state impact: none; no change to stored JSON, identity, schema or gates.
Compatibility/migration plan: expand compact store reads and operation snapshots;
migrate each consumer with regression proof, then remove replaced read branches.
Rollback/recovery plan: revert application commits; durable state is untouched.
Cutover trigger: each actual production route passes semantic and cost proofs.
Cleanup/decommission criteria: no replaced read implementation remains reachable;
all map-dependent callers are explicit writer reloads or use read results.
Failure blast radius: wrong authorization or stale state could leak titles or
mislead review/publication; no read result may authorize a command.
Adversarial proof matrix: absent/revoked roles; alternate MRO paths; independent
console writes; overlapping reads/writes; failed reads; snapshot isolation;
unchanged revisions/bindings/source; expired deadlines; repeat navigation.

### Owners and consistency

| Dependency | Authority/owner | Freshness and mutation | Replacement and proof |
|---|---|---|---|
| Document envelope/state | workflow.documents, document store | current per operation; commands reload under lock | compact selection / owned detail snapshot; next-request independent-console test |
| Object revisions | workflow.document_objects, concurrent store | current revisions, optimistic write token | narrow diagnostic inputs / detail rows; revision conflict tests |
| Review bindings | workflow review store | snapshot reads; current checks at commands | operation-owned bindings; no GET map refresh; review/revocation tests |
| Source bytes | immutable source store | content/hash verified; Blob outside SQL snapshot | unchanged source reconstruction and retained-only checks |
| Publication/serving | canonical publication registry | canonical read consistency independent unless same bound connection | existing publication gate remains; readiness never authorizes publish |
| Accounts/sessions | workflow identity store | current existing authorization | reuse role/assignment contracts; denied titles absent |
| Dispatch | durable processing attempts | discovery read, expiry/claim write under transaction | targeted discovery; existing claim/expiry tests |
| Checkpoints | durable attempt/replay owner | writes under current command, recovery fence | only demonstrated copy duplication may be removed; checkpoint/restart proofs |
| Telemetry | existing bounded hub | independently observed, potentially partial | existing telemetry partial marker, no atomic cross-store claim |

A read-only repeatable-read SQL transaction is valid only around a proven pure
operation. Quality calculation/history and GETs that record reports are not
blanket read-only operations. Blob and telemetry cannot be made atomically
consistent with PostgreSQL by a ContextVar. No thread/async timeout may leave
read work running; synchronous SQL limits must bound database execution.

## Measurement protocol and acceptance (fixed before implementation)

Local synthetic PG16, real production composition, deterministic HTML source and
existing model fixture. Researcher, assigned reviewer, unassigned reviewer and
publisher roles. Normal fixture and large nested replay evidence (4,000 records;
no source content logged), plus higher document/object cardinality. Smetten and
Azure are measured only if available; absence stays an open release requirement.
Cold means a new operation/connection, not a flushed OS/PG cache. Warm means repeat
requests against the same database; no cross-request application payload cache.
Record store calls, existing connection/query telemetry, wall duration and cProfile
copy cost without reserializing payloads just to measure them. Payload-byte probes
must use sizes already supplied by storage, not duplicate JSON encoding.

Acceptance: overview performs zero full envelope/object payload reads; detail
loads each envelope/object collection at most once per operation; independent
writes visible on the next request; snapshots unchanged during the operation;
no role/assignment leak or durable GET mutation. Notices use one bounded operation
and reuse only an in-flight tab request. Full copies may not scale with unrelated
documents at checkpoints. Local timings are descriptive; 3s/5s p95 remain
provisional, and no Azure latency claim follows from local timings. Release is
NO-GO until all requested routes and the full ingest→formation→review→publication
trajectory have necessary local and Azure proof.

## Dependency inventory and disposition

The base inventory contains **111 AST references across 76 qualified caller
functions** for the five dependency kinds below. Of these, **31 are direct
`_envelopes` attribute references**, not 31 independently identified consumers.
This counts syntax on 60bc697; it does not assert production reachability.
Method resolution and installed routes are checked by the production fixture.
The initial direct inventory preceded implementation. The reverse-call closure
was expanded against the same base during closure review. The machine-readable
[reverse-call closure](console-read-dependencies.json) records
300 conservative direct/indirect caller candidates, rooted in 23 direct map-using
functions, with both production MROs. Static over-approximation and dynamic dispatch
limits are explicit; this is not an assertion that all 300 execute in production.

| Reference kind | Meaning |
|---|---|
| `_envelopes` | explicit command work maps, legacy base bodies, or formerly map-dependent readers |
| `list_envelopes` | full document/receipt reads, previously also refreshing the writer map |
| `refresh_workflow_documents` | explicit authoritative command/startup/rollback reload |
| `_reload_store_locked` | existing command consistency and recovery boundary |
| `source_selection_read_scope` | replaced by the single typed document read operation |

Every base caller is listed below. Categories refer to the owner table above;
they name freshness, allowed mutation and the replacement/proof rather than
counting textual occurrences as runtime calls.

| Base caller | State owner / freshness / mutation | Replacement and regression evidence |
|---|---|---|
| `src/blockage_diagnostics_v1.py:308` · `collect_blockage` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/closed_review_loop_v1.py:78` · `ClosedLoopReviewConsole.waiting_task_counts` | Superseded in both production MROs by FastBadge PostgreSQL navigation | Remove dormant duplicate override; native navigation and hotpath suites |
| `src/console_asgi.py:209` · `build_app` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/decision_review_commands_v1.py:42` · `_execute` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/decision_successor_v1.py:53` · `execute` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/decision_successor_v1.py:73` · `execute.guard` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/document_status_ui_v1.py:121` · `install_document_status_ui.read_status_context` | Workflow/canonical status owners; independent aggregate reads; no writes | Only supported PG aggregate; empty-status/full-read fallback removed; lifecycle/status suites |
| `src/durable_publication_console_v1.py:274` · `DurablePublicationConsole.reconcile_durable_publications` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/durable_publication_console_v1.py:195` · `DurablePublicationConsole.withdraw_document` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/insight_v1.py:59` · `_authorized_documents` | Current account + assignment; repeatable-read overview inputs; no workflow mutation | Bounded metadata/status/admission inputs; `test_console_read_architecture`, `test_insight_v1` |
| `src/insight_v1.py:201` · `install_insight_routes.document_diagnosis` | Current account + assignment; repeatable-read overview inputs; no workflow mutation | Bounded metadata/status/admission inputs; `test_console_read_architecture`, `test_insight_v1` |
| `src/metis_mcp_queries_v1.py:72` · `McpQueries.read` | Existing MCP authorization and current source check; read only | Compact search/document cards; retain change detection on detail; `test_metis_mcp_v1` |
| `src/operations_console_app.py:3736` · `_render_review_room` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_app.py:4969` · `create_console_app.ingest_get` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_app.py:6168` · `create_console_app.publish_get` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_app.py:5471` · `create_console_app.review_get` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_app.py:5244` · `create_console_app.tree` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/operations_console_app.py:5421` · `create_console_app.tree_promote` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:716` · `OperationsConsole.__init__` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/operations_console_v1.py:2428` · `OperationsConsole._delete_unpublished_snapshot_locked` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:863` · `OperationsConsole._envelope` | PG document store owns data; operation owns snapshots; no shared writer mutation | First single read populates reuse; narrow IDs never load envelopes; cost/isolation/key suites. Base bodies are overridden in every supported constructor |
| `src/operations_console_v1.py:2797` · `OperationsConsole._heading_batch_mutation` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:2330` · `OperationsConsole._maybe_remove_unpublished_freeze_bytes` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:3865` · `OperationsConsole._recover_after_failed_correction` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/operations_console_v1.py:1915` · `OperationsConsole._reprocessing_transaction` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:3814` · `OperationsConsole.correct_object` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/operations_console_v1.py:2390` · `OperationsConsole.delete_unpublished_snapshot` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:2646` · `OperationsConsole.family_tree` | Workflow document metadata; fresh per operation; no process-map refresh | Explicit cards; full receipt only when the return contract requires it; tree/ingest/retrieval suites |
| `src/operations_console_v1.py:1338` · `OperationsConsole.ingest` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:4264` · `OperationsConsole.list_envelopes` | PG document store owns data; operation owns snapshots; no shared writer mutation | First single read populates reuse; narrow IDs never load envelopes; cost/isolation/key suites. Base bodies are overridden in every supported constructor |
| `src/operations_console_v1.py:4220` · `OperationsConsole.live_snapshot` | Workflow document metadata; fresh per operation; no process-map refresh | Explicit cards; full receipt only when the return contract requires it; tree/ingest/retrieval suites |
| `src/operations_console_v1.py:2672` · `OperationsConsole.move_family` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/operations_console_v1.py:2745` · `OperationsConsole.promote_class` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:4214` · `OperationsConsole.publish` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:2262` · `OperationsConsole.reextract_unpublished` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:4268` · `OperationsConsole.resolve_document` | Workflow document metadata; fresh per operation; no process-map refresh | Explicit cards; full receipt only when the return contract requires it; tree/ingest/retrieval suites |
| `src/operations_console_v1.py:2630` · `OperationsConsole.resolve_family_label` | Workflow document metadata; fresh per operation; no process-map refresh | Explicit cards; full receipt only when the return contract requires it; tree/ingest/retrieval suites |
| `src/operations_console_v1.py:3382` · `OperationsConsole.review_object` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/operations_console_v1.py:4232` · `OperationsConsole.select_for_question` | Workflow document metadata; fresh per operation; no process-map refresh | Explicit cards; full receipt only when the return contract requires it; tree/ingest/retrieval suites |
| `src/operations_console_v1.py:970` · `OperationsConsole.waiting_task_counts` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/publish_readiness_ui_v1.py:370` · `install_publish_readiness_ui.publish_get` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/quality_metrics_app_v1.py:28` · `capture` | Owned/assigned evidence in a pure SQL snapshot; report recording remains separate | One source capture + fresh metadata-only access check; `test_quality_metrics_v1` |
| `src/review_closure_v1.py:206` · `ReviewClosureConsole.migrate_legacy_revise_to_review` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/review_closure_v1.py:250` · `install_review_recovery_page.review_recovery` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/review_participation_ui_v1.py:107` · `filters` | Current stored assignments/policy; read only | Compact cards/filters; `test_review_participation_management` and characterization |
| `src/review_participation_ui_v1.py:121` · `overview` | Current stored assignments/policy; read only | Compact cards/filters; `test_review_participation_management` and characterization |
| `src/review_participation_v1.py:51` · `_execute` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/review_workboard_v1.py:850` · `install_review_workboard.review_get` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/review_workboard_v1.py:488` · `review_workboard_items` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/route_comparison_app_v1.py:67` · `install_route_comparison_routes.scope` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/source_context_review_v1.py:275` · `_confirm_source_context` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/source_context_review_v1.py:250` · `confirm_source_context` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/source_context_review_v1.py:65` · `confirm_source_exclusions` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/source_processing_dispatch_v1.py:45` · `pending` | Durable attempts; discovery read, expiry/claim writes under the existing command | Targeted dispatched IDs; fresh claim; `test_source_dispatch_hardening`, retry/recovery suites |
| `src/source_selection_ui_v1.py:94` · `document_keys` | Workflow document snapshot and current source authorization; read only | Compact source inputs + one chosen detail; key warmer removed; source cost/parity/browser suites |
| `src/source_selection_ui_v1.py:102` · `install.selection_get` | Workflow document snapshot and current source authorization; read only | Compact source inputs + one chosen detail; key warmer removed; source cost/parity/browser suites |
| `src/view_check.py:272` · `install.restricted_browser` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/workflows/workflow_documents_cutover_v1.py:380` · `_PostgresWorkflowDocumentsMixin.__init__` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/workflows/workflow_documents_cutover_v1.py:570` · `_PostgresWorkflowDocumentsMixin._apply_release_state` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/workflows/workflow_documents_cutover_v1.py:587` · `_PostgresWorkflowDocumentsMixin._commit_prepared_store` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_documents_cutover_v1.py:525` · `_PostgresWorkflowDocumentsMixin._delete_unpublished_snapshot_authority` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_documents_cutover_v1.py:445` · `_PostgresWorkflowDocumentsMixin._envelope` | PG document store owns data; operation owns snapshots; no shared writer mutation | First single read populates reuse; narrow IDs never load envelopes; cost/isolation/key suites. Base bodies are overridden in every supported constructor |
| `src/workflows/workflow_documents_cutover_v1.py:692` · `_PostgresWorkflowDocumentsMixin._heading_batch_mutation` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_documents_cutover_v1.py:556` · `_PostgresWorkflowDocumentsMixin._reload_store_locked` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_documents_cutover_v1.py:666` · `_PostgresWorkflowDocumentsMixin._reprocessing_transaction` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_documents_cutover_v1.py:547` · `_PostgresWorkflowDocumentsMixin._save_envelopes` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_documents_cutover_v1.py:418` · `_PostgresWorkflowDocumentsMixin._scoped_envelopes` | PG document store owns data; operation owns snapshots; no shared writer mutation | First single read populates reuse; narrow IDs never load envelopes; cost/isolation/key suites. Base bodies are overridden in every supported constructor |
| `src/workflows/workflow_documents_cutover_v1.py:411` · `_PostgresWorkflowDocumentsMixin.list_envelopes` | PG document store owns data; operation owns snapshots; no shared writer mutation | First single read populates reuse; narrow IDs never load envelopes; cost/isolation/key suites. Base bodies are overridden in every supported constructor |
| `src/workflows/workflow_documents_cutover_v1.py:429` · `_PostgresWorkflowDocumentsMixin.list_snapshot_ids` | PG document store owns data; operation owns snapshots; no shared writer mutation | First single read populates reuse; narrow IDs never load envelopes; cost/isolation/key suites. Base bodies are overridden in every supported constructor |
| `src/workflows/workflow_documents_cutover_v1.py:400` · `_PostgresWorkflowDocumentsMixin.refresh_workflow_documents` | Explicit command/startup/rollback work map; mutable only at its existing owner | No GET refresh dependency; native transaction, StoreCommand and recovery suites |
| `src/workflows/workflow_review_cutover_v1.py:373` · `_PostgresWorkflowReviewMixin._atomic_snapshot_mutation` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_review_cutover_v1.py:314` · `_PostgresWorkflowReviewMixin._commit_prepared_store` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_review_cutover_v1.py:151` · `_PostgresWorkflowReviewMixin._refresh_after_rollback` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_review_cutover_v1.py:248` · `_PostgresWorkflowReviewMixin._refresh_runtime_in_command` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |
| `src/workflows/workflow_review_cutover_v1.py:121` · `_PostgresWorkflowReviewMixin._reload_store_locked` | Existing command/recovery owner; current reload under locks, revision/transaction rules unchanged | Commands detach read inputs; map-dependent readers replaced; checkpoint copies touch submitted document only; StoreCommand, concurrency and lifecycle suites |
| `src/workflows/workflow_review_cutover_v1.py:211` · `_PostgresWorkflowReviewMixin._store_command` | Existing owning domain operation; follow its PG authority and supported MRO | Read results stay operation-owned; explicit writer reloads retained. Full production suite plus page/diagnosis/review tests |

## Definitive implementation and cutover

- `ConsoleReadSnapshot` is disposable operation state: full detail envelopes,
  object inputs/current revisions, revision tokens, bindings, cards and canonical
  metadata remain separate shapes. No snapshot is persisted or retained between
  requests. First individual reads populate their own reuse; list warming is gone.
- The production composition wraps every installed GET and sets the route class
  for future synchronous/asynchronous GETs. Routes do not choose cache rules.
  Source reconstruction keeps its existing owner and retained-only prohibition.
- `document_overview_operation` selects authorized metadata then only the scanned
  page's stored status/admission fields. It never loads candidate text, replay,
  extraction or full objects. Raad fetches at most 1,001 metadata rows, scans at
  most 1,000, returns at most eight notices and exposes incomplete scans. Inzicht
  retains exact metadata search/paging; large-corpus metadata latency still needs
  representative production proof.
- Bronselectie uses its existing authorization rule (`authorize_account` is the
  pure part of `authorize`). Its overview reads compact stored progress and
  estimates. Only an explicitly chosen document loads full detail and a command
  revision token. Other cards show unchecked counts and an opening link; they
  cannot claim completion or submit an unverified start. Selected-document
  Starten/Hervatten retain the existing current revision/configuration gates.
- Publication cards read existing batched release/registry dimensions. They do
  not fetch/hash canonical object contents. These labels describe stored release
  state, not integrity verification or publication readiness. Selected detail and
  POST publication retain the current domain gate. Failed canonical reads show
  an explicit unknown status with correlated safe error evidence.
- Review details use one full document/object snapshot, while choosers, participation
  overviews, Inleveren, Documenten and MCP metadata queries select compact fields.
  MCP detail keeps its concurrent source/access-change detection. Its registry
  summary explicitly reports canonical content integrity as not checked.
- Quality calculates from one authorized source/object capture. Its second access
  check opens an independent metadata snapshot, preserving revocation protection
  without reconstructing/copying the source a second time. Report/history writes
  remain outside read-only workflow transactions.
- Commands detach inherited read state, reload their own work maps under the
  existing command/row/transaction boundaries, and retain revision checks. Dispatch
  selects pending/expired candidates with a SQL limit and rotating cursor; a bounded
  expiry scan cannot expire an unlimited backlog. It no longer loads every envelope
  each second. Claim/expiry still reloads and writes under its existing owner.
- Checkpoint commits copy only the submitted document, not every unrelated nested
  payload. Command JSON already detached by the store is not cloned again by the
  diagnostic/dispatch preparer. Public return copies and mutation/commit boundaries
  remain. Current revision validation and revision-token construction are reused
  within a read operation; write-side loads always fetch current data.

### Removed mechanisms

Removed the old source-specific scope API and route decorators; source key-list
warming/fallback; single-read process-map refresh and two extra envelope copies;
GET/list binding-map refresh; list-refresh dependence in metadata/retrieval readers;
full envelope reads for the migrated overview/chooser fields; full canonical reads
on publication cards; the duplicate ClosedLoop badge override; full-corpus dispatcher
reads; unrelated-document checkpoint deep copies; eager unused read revision hashing;
repeated pure current-revision validation; duplicate quality source capture; silent
empty lifecycle-status fallback; Raad's two parallel document scans and persisted
protected notice titles. There is no new permanent old/new read alias or dual writer.

Some full reads intentionally remain: selected detail, exact source/review evidence,
public detached exports, command/recovery preparation and canonical integrity gates.
The unsupported base console cannot be instantiated; production MROs always use the
complete PostgreSQL boundary. No file-store compatibility topology was introduced.

### Consistency and error limits

Pure overview/quality/source metadata operations use the existing shared PG
connection mechanism with `REPEATABLE READ READ ONLY`, a five-second statement
limit and idle-in-transaction limit. Current identity authorization that uses
`FOR SHARE` runs before that pure boundary. Nested independent-read attempts are
refused rather than changing a command's isolation. Detail operation ownership
is not a claim of one atomic snapshot across independently queried authorities.
Canonical publication remains a separate authority/connection where not bound;
Blob readback/hash and telemetry's bounded, possibly partial observation remain
independent. No timeout was increased and no detached timeout thread was added.
The cancellation test checks that the timed-out database backend has no active
query; this does not prove Azure gateway cancellation behavior.

The existing telemetry adds `payload_copy` time and `document_snapshot_reused`.
`db_json_bytes` counts bytes already supplied to native JSON/JSONB driver loaders,
keeps their decoder/customization, and never serializes a structure to measure it.
It excludes non-JSON columns and protocol overhead; it is not total network egress.
No SQL, payload, source text or credentials are added to logs.

## Relationship to earlier fixes

- #613 introduced diagnosed phases and contextual reuse. This recovery keeps that
  evidence but removes the list-first requirement and process-map read side effect.
- #622 made publication cards and source status more proportionate. The active
  publication route was already compact at the UI level; this change removes its
  remaining full canonical store reads and separates source overview from detail.
- #632 avoided per-receipt copies with a light key list. The source route no longer
  warms a full envelope list through those keys; metadata and detail are explicit.
  The remaining public key API now selects only IDs even inside a read operation.
- #633's once-per-request comparable estimate observations remain; they now consume
  compact authorized progress records. Estimates remain coarse and may be unknown.
- Review/source fixes (including #611/#612 and the later Review read scope) retain
  source validation/reconstruction reuse and exact hash checks. Read ownership now
  comes from the production operation boundary, and no Review-only opt-in is needed.
- Concurrent main changes #832/#833 were integrated; their Documenten/Review layout
  changes remain. Characterization changes relative to that main consist only of
  the new JS asset hash and the additive notices route.

## Migration, rollback and release

No schema migration, durable projection, backfill, credential or infrastructure
change. Expand compact store operations, migrate outcomes, then contract old read
paths occurred locally. Roll back the application commits to restore the previous
code/JS; no durable data rollback is required because the recovery does not rewrite
source, candidate, review or publication history. A rollout requires the normal
review/authorization and production evidence; this branch performs neither.

The release verdict remains **NO-GO** until representative Azure data/topology,
latency/concurrency, and the complete real ingest→formation→review→publication
trajectory have passed. Local synthetic proof does not lift that blockade. Full
Smetten source/envelope data and Azure credentials are not present in this managed
instance; the checked-in Smetten fixtures are partial forensic/reference evidence,
not a representative production database.

## Final evidence

See `console-read-architecture-evidence.json` for the exact comparison protocol,
measurements, final application revision and executed verification.

### Adversarial closure review

A separate self-review pass challenged map side effects, authorization freshness,
public-output mutation, selected-detail revision tokens, publication integrity,
GET writes, diagnostics, large-payload scaling and bounded background work. It
found and resolved remaining full canonical card reads, source per-card detail
loading, duplicate quality capture, key-list warming and unbounded expiry scans.
The new regression fails on the base for the latter and passes on recovery.
Reviewer independence is not claimed. Required human review remains before merge.

The dependency closure is a conservative code map, combined with active production
MRO/route tests and domain scenarios; it cannot prove arbitrary reflective callers.
Every changed read surface is migrated in the table above; explicit writer maps
remain writer-owned. No lifecycle authority or stored representation was replaced.

### Executed closure results

Application revision: `28af06f254d5791098694af5a71f9b674629c663`.
Full suite: **5723 passed, 29 skipped, 3 xfailed, 6 warnings, 3 subtests passed**
in 1297.57 seconds. Real disposable PostgreSQL 16.15 was mandatory and ran;
optional skips are not accepted as proof. Browser acceptance was additionally
executed with Chromium: five navigation/source/knowledge/view-check cases passed.
The optional section incident browser initially exposed a pre-existing double
middleware test fixture (also failed on unchanged base). Removing that extra test
wrapper, without changing production, yielded all 15 incident tests passing,
including authenticated browser correlation. Earlier two-browser proof also passed.
The local publication/recovery chain and architecture invariants passed all 17 cases.
The focused read/diagnostics/dispatch closure passed all 61 cases.
Repository, release-control, architecture-boundary, compile and JS syntax checks
passed; release-control explicitly reports `live_release_evidence: false`.

Identical local measurement: five profiled Inzicht samples decreased from
1.30–1.50s to 0.019–0.027s; native JSON decode bytes from 3,070,110 to 443;
connections/queries from 13/21 to 4/11. The recovery performs no full envelope or
object reads in that overview. In the unprofiled route comparison, quality,
diagnosis, Review, Publicatie and selected Bronselectie each used one envelope and
one object collection. Two-reader wall time was 1.041s→0.023s; formation with two
readers 2.582s→0.344s. These are descriptive local observations, not p95 or Azure
budgets. Both runs use the same benchmark/fixture; the comparison base predates
concurrent main's cosmetic #832/#833 changes, which are integrated in recovery.
Local warm query plans show processing metadata 1.918ms and diagnostics 0.121ms;
representative TOAST/Azure costs remain open.

**Joint verdict: local implementation ready for review; release NO-GO.**
No merge/deployment is authorized by this proof. Actual Azure topology/data,
latency/cancellation under load and the full real content trajectory remain required.

## Repair after review (2026-10-24)

Class B / Rewrite risk: high remain unchanged. Work continues from PR head
56488c0 through additive commits; no rebase, force push, merge or deployment.
The six user-supplied failures have reproduction tests before production edits:
eight cases fail on that exact head. Quality source/ledger I/O has an additional
transaction-boundary reproduction. Each repair and red/green result is recorded
in the evidence JSON. No new persistence, cache, migration or lifecycle rule.

Read transactions may contain only bounded database capture and the minimal
bounded preparation needed to select it: no file, network, Blob or telemetry I/O
and no unbounded Python computation. Captured inputs belong to the operation;
external evidence is read only after the SQL transaction closes.

### Repair 1

Capture the entire selected SQL scan window before telemetry; quality captures SQL first and reads sources/ledger afterwards. The source-selection caller already closes SQL before authorization/projection. All 3 transaction-boundary probes pass, including both HTTP routes with 6s telemetry. Additional quality I/O probe was red on the base.

Regression proof: `test_slow_telemetry_outside_read_transaction,test_telemetry_has_no_open_read_transaction,test_quality_source_and_ledger_io_outside_read_transaction`. Red on `56488c0`; green after repair.

### Repair 2

Normal not-started and in-progress reasons share one definition beside the receipt/formation writers. Only stored failure reasons or failed/interrupted/expired latest attempts count as processing blocks; compact summaries expose only attempt state/expiry, never processing details. Both new/running probes and the existing stored-block/revocation probe pass (3 cases).

Regression proof: `test_new_and_running_documents_are_not_processing_blocks,test_notices_revocation_and_explicit_unknown_count`. Red on `56488c0`; green after repair.

### Repair 3

Unknown candidate counts cause a notice only for an account with processing access. Publishers receive stored-block/error notices without processing details; missing access alone produces no notice. The new publisher probe and updated revocation/unknown-count probe pass (2 cases).

Regression proof: `test_publisher_missing_processing_access_is_not_a_notice,test_notices_revocation_and_explicit_unknown_count`. Red on `56488c0`; green after repair.

### Repair 4

Raad captures at most 50 documents per SQL batch and stops at 8 notices or its cooperative 4s operation budget. Each batch closes before telemetry/filtering; SQL statement deadlines are lowered to the remaining budget. Failed/timed-out batches log an explicit diagnostic and return earlier rows with complete=false and the first unexamined offset. Four error/timeout/budget/scan-limit probes pass. Synthetic PG storage: 78,864,936 total object bytes; 50/50/1-document batches took 0.033869/0.036487/0.003597 seconds. Not representative Azure evidence.

Regression proof: `test_notices_second_diagnostic_batch_failure_is_explicit_partial,test_notices_statement_timeout_preserves_previous_batch,test_notices_budget_returns_cursor_without_open_transaction,test_bounded_notices_do_not_claim_complete_when_later_documents_are_unchecked`. Red on `56488c0`; green after repair.

### Repair 5

Any visible busy/waiting source document now enables the existing 5s reload and refresh text, including the overview without a document parameter. No overview buttons added. Recorded pending/claimed characterization goldens with --record-characterization; all 45 characterization/source cases pass. Diff audit: 32 existing goldens changed only the Raad asset hash; two new source-overview goldens capture the requested behavior. The asset also hides unavailable candidate-count text for publisher-only notices.

Regression proof: `test_source_overview_refreshes_running_document,test_source_overview_running_golden`. Red on `56488c0`; green after repair.

### Repair 6

Discovery looks ahead through at least 50 documents while pending still limits returned tasks. An expired document no longer hides the following pending task in the same round; expiry work remains bounded to 50 documents for limit=1. Both the supplied expired-then-pending probe and a 51-expired-document bound/progress probe pass.

Regression proof: `test_pending_finds_task_after_expired_document_in_same_round,test_dispatch_expiry_scan_respects_bound`. Red on `56488c0`; green after repair.

### Repair 1 closure: CPU work and captured empty bindings

Quality captures raw envelopes, object rows and bindings under SQL, then validates
revisions, detaches public copies, reconstructs sources and assigns ledger events
after SQL closes. Empty bindings are captured explicitly so no post-transaction
read substitutes fresher bindings into the owned snapshot. The strengthened
quality probe checks object projection as well as file/source/ledger work.
Quality and failed/expired notice tests pass all 11 cases.

Raad notice definition: a true stored processing block (excluding the two normal
progress reasons), blocked candidates, a genuinely unavailable count for an actor
with processing access, or telemetry errors. Missing processing access is never
a notice or a candidate-count explanation. Publisher-only rows expose no retry,
reason or candidate details. Per-batch SQL snapshots are independent: command
checks remain current and never authorize from the notices snapshot. The time
budget is cooperative between captures; external telemetry retains its existing
bounded reader and is never cancelled by leaving detached work running.

### Repair 1 operation-boundary guard

The metadata overview context now closes SQL before yielding to any consumer.
Metadata ownership/authorization selection runs outside SQL; explicit bounded
status captures finish before telemetry and state filtering/pagination. Quality
likewise selects owned metadata outside SQL and captures details in a second
transaction. Metadata and detail batches are independent database snapshots;
within each, native rows are captured consistently and remain operation-owned.
No cross-capture atomicity or cross-authority consistency is claimed.
The final focused Inzicht/quality/read suite passes all 43 tests.
