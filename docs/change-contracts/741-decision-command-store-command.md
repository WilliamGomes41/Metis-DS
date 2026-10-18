# #741 — migrate the decision-review command transaction owner

Change class: B
Promise: A native decision-review command (update or confirm the decision graph) has one Storeopdracht owner, one authoritative reload, atomic workflow writes and no mirror write before the outer commit; a mirror failure after the commit no longer fails the committed command.
Proof: `tests/test_741_decision_command_store_command.py`, red on main `ed17444` (12 failed / 4 passed, local and Azure R+, PostgreSQL 16), green after the change; existing decision-graph, participation, #678/#708/R2 and transaction suites unchanged.
Touches lifecycle invariants: no
Rewrite risk: high

## Existing mechanism and smallest change

Call path: POST `/review/decision-graph` → `OperationsConsole.update_decision_graph` /
`confirm_decision_graph` → `decision_review_commands_v1.execute` → `_execute` →
`_commit_prepared_store`. `execute` owned a raw `workflow_transaction` with its own
row lock and its own recovery block, so the inner commit took the compatibility
path. The native red test shows mirror writes (bindings, objects, envelopes,
ledger) while the outer transaction is open, and a mirror write failure aborting
the whole command.

The change is the one already proven for participation (#748, `845591e`): the raw
wrapper and its recovery are replaced by `console._store_command(snapshot_id,
lock_row=True)`. `_execute` is unchanged. The independent-command guard
(`decision_review_independent_transaction_required`), `bind_workflow_stores` and
the local file path are unchanged.

## Domain-first overlay

```text
Domain entity/aggregate: the existing unpublished WorkingRevision and its decision graph/policy.
Invariant(s): unchanged domain transition (roles, named reviewer, published immutability, command_id/payload-hash idempotency, expected_revision); one command owner; mirrors are non-authoritative and follow the commit.
Durable state before: committed envelope, object history and review events.
Durable state after: object history, envelope (graph/policy) and the decision_review_command event, committed together, or unchanged after rejection/rollback.
Transaction boundary: the existing Storeopdracht holds the store lock, locks the same workflow.documents row, reloads once and commits all workflow writes; mirrors are rebuilt from PostgreSQL afterwards under the same lock.
Failure/recovery result: the Storeopdracht rolls back and rebuilds the mirrors from PG; a failing recovery cannot replace the original error; a mirror failure after the commit logs store_command_remirror_failed and the command stays committed.
Duplicate execution / idempotency result: unchanged; the same command_id and payload return the committed result, a conflicting payload is refused.
Concurrency result: unchanged; same row lock, store lock and expected revision.
Audit/evidence requirement: unchanged; the decision_review_command event is written in the same transaction.
```

## Rewrite-risk mitigation

```text
Rewrite target: the decision-review command's raw transaction wrapper and duplicate recovery only.
Why local patching is insufficient: deferring single mirrors keeps the second owner, repeated reloads and its own recovery; the Storeopdracht already owns all four mirrors.
Current authority/writer/reader map: authority workflow.documents / document_objects / review_events. Writer: _execute through _commit_prepared_store (unchanged). Mirror writers and _remirror_from_pg / rollback recovery stay owned by the review mixin. Readers: decision-graph UI, policy/readiness and command replay read the same authorities.
Supported runtime topologies: local file harness unchanged; complete local and Azure R+ use the shared-store transaction binding.
Persisted-state impact: none; no schema, state format or migration.
Compatibility/migration plan: migrate one caller onto the established owner; other raw owners and the general compatibility branch remain for #741 follow-ups.
Rollback/recovery plan: revert this caller migration; no data conversion.
Cutover trigger: merge after CI, Sherlock/Argos and William's GO.
Cleanup/decommission criteria: this slice removes the decision command's raw owner and recovery block.
Failure blast radius: decision-graph commands refused or stale mirrors if ownership were wrong; domain semantics stay pinned by existing decision-graph tests.
Adversarial proof matrix: update and confirm paths; pre-commit fault, real deferred-FK COMMIT failure, failing recovery; raw and owned enclosing transactions refused; post-commit mirror failure keeps the command committed and replayable; local and Azure R+.
```

## Verification

- Red commit on main `ed17444`: 12 failed / 4 passed (the 4 passes are the unchanged nesting refusal).
- After the change: 16 passed, zero skips.
- Related native suites (decision-graph chain/concurrency/structure/successors, participation, #678, #708, R2, transaction): 121 passed, zero skips.
- Architecture boundaries check and `compileall` pass.
- No merge, deployment or issue closure is authorised by these local results.
