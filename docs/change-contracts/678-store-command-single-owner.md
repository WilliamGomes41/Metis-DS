# #678: Storeopdracht (store command) — one owner per durable command

Change class: B
Promise: A durable review/document command in the PostgreSQL review topology (R+) MOET have exactly one owner: only the outermost level reloads, opens and commits the PostgreSQL transaction and rebuilds the disk mirrors, and that only after the commit or rollback. Nested levels join the command.
Proof: tests/test_678_store_command_postgres.py is red on main e228aa9 and green after the change: one reload per approve and per batch (constant in k), no disk-mirror write while the command's transaction is open, a caught nested fault leaves no phantom ledger line, the original error survives a failing recovery, a foreign console cannot join, and disk mirrors equal PostgreSQL after every commit and rollback. The existing R2/#665/closed-loop suites stay green.
Touches lifecycle invariants: no
Rewrite risk: high

Taalregel: rules use MOET / MAG NIET / NOOIT only. Sources: #678 (X1, Forge inventory comment 6233693095), #730, decision B1 (William, 17-10 14:04).

## Domain model

Ubiquitous term: **Storeopdracht** (store command). One command per durable user/system action, for example one approve, one batch of approvals, one correction, one reprocessing step.

| Role | Who | Allowed | Not allowed |
| --- | --- | --- | --- |
| Owner | the outermost store boundary of a console in the current execution context | store lock, one authoritative reload, open/commit/rollback the PostgreSQL transaction, after the commit or rollback the single mirror rebuild (`_remirror_from_pg` / `_remirror_after_rollback`) | — |
| Participant | every nested boundary of the same console inside an open command | a savepoint and an event-buffer level (so a caught nested fault rolls back only its own work, I2) | reload, disk-mirror write, remirror, commit |
| Foreign | a boundary of another console inside an open command | — | joining the command (refused: `store_command_foreign_owner`) |

Invariants:

- U1 (one owner): exactly one owner per command. It reloads once; participants MAG NIET reload.
- U2 (participants join): a participant opens a savepoint and an event-buffer level. On a participant fault the in-process maps are refreshed from the transaction's own view (reads only) and the fault is re-raised. Its deferred ledger lines are discarded.
- U3 (B1, mirrors after commit): while a command is open, every disk-mirror write (ledger, bindings, envelopes, objects) is deferred to the command. After a successful commit the owner rebuilds exactly the deferred mirrors from PostgreSQL as one writer, under the store lock. After a rollback the owner runs the existing full remirror. Mirrors MAG NOOIT be written inside the command's open transaction.
- U4 (original error wins): a failing refresh or remirror after a fault MAG NIET replace the original exception. A failing mirror rebuild after a successful commit MAG NIET report the committed command as failed; it logs `store_command_remirror_failed` with codes only.

Domain-first overlay (stateful Class B):

```text
Domain entity/aggregate: Storeopdracht over one console's PostgreSQL review/document stores (workflow.documents, workflow.document_objects, workflow.review_events, workflow.review_bindings).
Invariant(s): U1-U4 above; PostgreSQL stays the only authority; disk files are disposable mirrors.
Durable state before: PostgreSQL rows as committed by the previous command.
Durable state after: PostgreSQL rows of this command, committed atomically, or unchanged after rollback.
Transaction boundary: the owner's single PostgreSQL transaction; participants are savepoints inside it.
Failure/recovery result: rollback of the owner transaction, then one full remirror from PostgreSQL; the original error is raised.
Duplicate execution / idempotency result: unchanged; existing revision pins (expected_revision) and hash-chained ledger checks still decide.
Concurrency result: unchanged serialisation; the process-shared store lock is held from reload until after the mirror rebuild.
Audit/evidence requirement: ledger events are written to PostgreSQL inside the transaction exactly as before; only the ledger mirror line is written after the commit.
```

## Scope of this change (expand + migrate step 1)

Owners/participants through `_PostgresWorkflowReviewMixin._store_command`:

- `_atomic_snapshot_mutation` (owner or participant, event buffer)
- `_commit_prepared_store` (owner or participant, event buffer)
- `_reprocessing_transaction` (owner or participant, `FOR UPDATE` on the document row, no event buffer, as before)
- `OperationsConsole.correct_object` failure path: the command owns recovery (U4)

Deferred mirror writers: `_mirror_bindings`, `_mirror_envelopes`, `_mirror_objects`, `PostgresWorkflowReviewStore._mirror_events`.

Compatibility path (unchanged behavior): a boundary entered inside a raw `workflow_transaction` that no command owns (publish, heading batch, decision successor, participation/decision/source-context commands, quality metrics) keeps the pre-#678 nested behavior. These owners are migrated in later steps; see below.

## Rewrite-risk mitigation

```text
Rewrite target: the nested-level semantics of the R+ review/document mutation boundary (_atomic_snapshot_mutation, _commit_prepared_store, _reprocessing_transaction).
Why local patching is insufficient: every level re-implements owner duties (reload, mirror write, remirror). Removing one call per level moves the problem (Option C, #667) instead of naming the owner; B1 requires a single writer after the commit, which needs an explicit command owner.
Current authority/writer/reader map: authority = PostgreSQL workflow.* (unchanged). Writers = PostgresConcurrentWorkflowDocumentStore.write_bundle, PostgresWorkflowReviewStore append_event/_flush_buffer/replace_snapshot_bindings (unchanged). Mirror writers = _mirror_bindings, _mirror_envelopes, _mirror_objects, _mirror_events, _remirror_review_runtime (now deferred/owner-only inside a command). Readers inside a command read PostgreSQL (_envelope, _load_objects, objects_revision, read_bindings, read_events); no reader inside a command reads a disk mirror.
Supported runtime topologies: R+ local and production (PostgresReviewWorkflow* and PostgresCompleteWorkflow* consoles) use the command. File topology (OperationsConsole without PostgreSQL) is unchanged. Tier D/I refusal (#665/#718) is unchanged.
Persisted-state impact: none in PostgreSQL (no schema, no data migration). Disk mirrors are disposable and rebuilt from PostgreSQL at startup.
Compatibility/migration plan: strangler. Step 1 (this change): kernel + the #678 chain. Step 2: migrate the raw-transaction owners (review_participation_v1, decision_review_commands_v1, source_context_review_v1, publish, heading batch, decision_successor_v1, quality_metrics_app_v1) to the command and remove the compatibility path. Step 3 (contract): mirror writes outside a command become an error.
Rollback/recovery plan: revert the commit. No persisted state depends on it; a restart rebuilds all mirrors from PostgreSQL.
Cutover trigger: merge after green CI and William's GO; no runtime flag.
Cleanup/decommission criteria: the compatibility path is removed when step 2 leaves no raw workflow_transaction owner in src/ outside the command module.
Failure blast radius: R+ review/document commands. Worst case of a defect: a stale disk mirror (disposable; no PostgreSQL impact) or a refused nested call (fail closed). PostgreSQL atomicity is unchanged or stronger.
Adversarial proof matrix: see "Adversarial review" below.
```

## Adversarial review

| Attack | Result |
| --- | --- |
| Inner fault caught by the caller, outer continues (I2) | Savepoint + buffer level discard the inner work; deferred ledger lines of the participant are dropped; test `caught_nested_fault_*`. |
| Unbuffered `append_event` inside a participant that later fails | Its mirror line is deferred and dropped with the participant; no phantom ledger line; test `unbuffered_event_in_failed_participant_*`. |
| Mirror read inside a command | No R+ reader inside a command reads a disk mirror (traced: `_envelope`, `_load_objects`, `objects_revision`, `object_review_bindings`, `read_events` all read PostgreSQL). |
| Another console nests inside an open command | Refused with `store_command_foreign_owner` before any write. |
| Raw `workflow_transaction` owner (publish, heading batch, ...) enters a review boundary | Compatibility path: pre-#678 behavior, no command is created, so no deferred mirror is lost. |
| Remirror fails after a successful commit | Commit stays successful; warning `store_command_remirror_failed`; next command or restart rebuilds. |
| Remirror fails after a rollback | Original exception is raised; one warning (existing dedupe). |
| Two threads on one console | The ContextVar is per thread/context; the store lock serialises owners; a second thread is never a participant of the first thread's command. |
| Generator/async exit (GeneratorExit, KeyboardInterrupt) | Treated as a fault: rollback, remirror, re-raise. |
| Inheritance: ReviewClosure/closed-loop overrides | They call super() into the review mixin; the review mixin owns the boundary in every R+ MRO (pinned by test_r2_mro_boundary_methods_are_pinned). |
| Restart | Startup remirror from PostgreSQL is unchanged. |

## Contract change versus #667 (Option C)

#667 Option C required every nesting level to remirror. Decision B1 (later the same day) replaced it: only the outermost level remirrors after the commit. The tests `test_optc_ordinary_fault_through_commit_prepared_store_logs_one_warning` and `test_optc_caught_nested_fault_mirrors_equal_pg` are updated to B1: exactly one remirror per command fault, by the owner, and mirrors equal PostgreSQL afterwards.

## Limits

- The compatibility path keeps the old nested behavior for the raw-transaction owners until step 2. S9/#705 (heading batch copy restore) and S13/#707 (`_apply_local_release_copy`) are not changed here.
- The single mirror rebuild after a commit appends the committed ledger lines and re-reads bindings, the touched envelopes and the touched objects. It does not re-read the full ledger (the existing O(E) full remirror stays failure-only).
