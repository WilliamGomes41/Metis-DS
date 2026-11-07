# W4 adversarial self-review — 7 November 2026

Target: baseline `e6e008c671bfdaa780b1df6cd3b44a661643f7ce` to runtime
`5df87a987764bbcd60e44b34402ffe52b558118a`; later explanation/evidence changes
do not alter the runtime. Decision: QUALITY, scoped to #729/MET-36 W4 and its
[pre-implementation contract](../change-contracts/729-w4-formation-database-work.md).
This is a separate implementer's review pass, not an independent reviewer or
merge/deployment approval.

Required outcome: the original authorized formation resume, task identity and
per-task durability, original deterministic candidates and complete atomic
activation remain intact. Only repeated database work during activation is
reduced. Material failures would corrupt working history, hide object mutations
from checkpoints, lose committed task work or permit unpublished serving.

## Boundary challenges

| Challenge | Inspected enforcement and falsifiable evidence |
|---|---|
| Alternate writers and inheritance | `PostgresWorkflowDocumentRuntimeStore._write_objects_locked` routes to the existing physical writer; both its full bundle writer and `PostgresConcurrentWorkflowDocumentStore.write_bundle` retain original validation/activation checks and sealing. Prepared review uses its existing distinct writer; the SQL generation trigger covers it and old/direct SQL too. Existing full-writer and prepared-review regressions execute these paths. |
| Grouping erases transition validation | Only adjacent new rows are grouped after the original full revision validation. Existing-row updates/deletes retain order; pending additions flush before an existing row. No intermediate prepared-review transition or candidate-creation path changes. |
| SQL returns an altered, suppressed or extra row | Each returned row must have the exact snapshot, unique planned identity, position and exact JSON; count and complete membership must match. Existing sealing compares physical identity/order and mutation epochs. Six later-group fault cases prove rollback after an earlier group has already executed. |
| Sealing trusts an intended payload instead of actual SQL | Removing the new writer's returned-JSON comparison in a disposable worktree permits the injected BEFORE-trigger rewrite; the regression fails `DID NOT RAISE`. Restoring the comparison passes. The check is necessary and the regression detects its removal. |
| Counter drift under bulk SQL | Transition relations count actual affected rows, including BEFORE-trigger refusals and disjoint INSERT/UPDATE portions of UPSERT. Tests cover multiple documents, all three DML operations, zero rows, native0 and transaction rollback. Final values retain migration021 semantics. |
| New visibility window or stale checkpoint | Native per-row frontier invalidation still locks the document, and full application writers already hold that lock. Checkpoint/worker ownership checks lock the same document and compare generation/claim/source/configuration before work. Concurrent disjoint writes retain exact +N; an actual bulk write invalidates a previously captured checkpoint without adding one. Statement-internal generation timing changes, but another command cannot observe an intermediate committed generation. |
| Partial cutover and legacy privileges | Migration033 atomically replaces one row trigger with three statement triggers; no data/table/column rewrite. New binary on old triggers remains correct but slower. Old SQL on new triggers preserves +N. The native test applies migration twice, restores the old trigger, re-upgrades and compares durable data. The same restricted-role grants work before/after; schema DDL is denied. |
| Topology and fallback | Both complete production compositions pass deferred activation failure/restart/retry. Controlled production migrations work without optional027. Existing full-writer fallback tests exercise missing frontier schema and metadata-only writes. File adapters do not call this SQL writer. |
| Task result lost on late failure | A database deferred COMMIT failure rolls back activation but preserves six separately committed tasks in both compositions. Restart/retry uses all six without another provider call. The 130-task paired proof retains every committed task and verifies exact objects/source after a fresh runtime. Existing process-kill and HTTP-resume tests cover real independent runtime recovery and stale/configuration fences. |
| Duplicate authority or publication bypass | No new store, cache, bypass setting or runtime dependency. Existing revision/materialisation, activation, release-history and publication-registry owners remain unchanged. The full writer rejects published object rewrites before SQL. Native recovered work is still unpublishable without its original review requirements. |

## Outcome and limits

**GOOD WITHIN SCOPE** for the reviewed implementation: no actionable runtime
defect remained in this pass. The actual performance observations and all
verification outcomes, including any full-suite failures and reruns, belong to
the single [evidence record](../../evidence/729-w4/README.md). CI and human review
remain separate readiness inputs.

The focused development run found a missing test-role SELECT privilege already
required by the original document trigger; the corrected test proves the old
and new triggers with identical grants. Release preflight also required separate
category markers instead of several category names on one line; only test
metadata changed. Neither issue justified widening runtime privileges or
weakening checks.

Remaining uncertainty: local PostgreSQL17 and deterministic provider latency
do not establish PostgreSQL16 CI status, production contention or Azure/model
latency. The median background action still takes 9.56s; the agreed W4 budgets
pass, but the original >5s inventory is not closed. No application timeout,
claim, lease, task budget or human review boundary was relaxed.
