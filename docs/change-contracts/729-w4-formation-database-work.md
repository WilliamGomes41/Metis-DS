# #729 / MET-36 — W4 formation activation database work

Change class: A
Promise: resuming existing formation tasks produces the same durable result while independent new object rows avoid repeated full-document generation updates during activation.
Proof: actual native 130-task interruption/resume/restart comparison, bounded document-update work, exact SQL result and counter proofs, rollback/stale/concurrency and migration compatibility.
Touches lifecycle invariants: yes
Rewrite risk: high

William assigned W4 on 7 November 2026 under the existing Architect plan,
#729/MET-36 and project parent #959/MET-45. Base is merged W1 main
`e6e008c6`. No merge, deployment, production data conversion or new project.

## Measured cause and chosen boundary

The unchanged `scripts/measure_source_task_reuse.py --counts 130` resumed in
27.715238s on Python 3.13.5/PostgreSQL 17.11. It reused the first committed task
and its exact result hash, with 131 deterministic fixture-provider calls
including the interrupted call and no external model traffic.

A separate instrumented run measured 26.040s. The existing physical object
writer spent 16.140s inserting 261 rows. Server execution took 15.918s;
`advance_object_generation` took 15.617s, including 261 updates of the same
document and its projection/identity guards. Client transport is not the main
cause of this group. The checkpoint insert function took 0.181s across 266
calls. Nested server/function times overlap and must not be summed.

Two designs were assessed by the implementer. Skipping document guards on a
generation-only update broadens the guard bypass surface and still writes the
document once per object. Instead, keep all existing guards and the exact
generation increment per affected row, but aggregate that increment per document
per SQL statement. The full writer groups adjacent new rows in bounded batches;
updates/deletes retain their ordering and existing individual verification.
This changes the physical activation mechanism, not the formation task policy.

## Acceptance fixed before product changes

Five alternating matched baseline/head pairs on the same 130-task fixture:
resume median <=15s, every head run <=18s, and instrumented object insertion
<=2s (baseline 16.140s). The structural regression permits at most four
generation-bearing document updates for 261 independent new object rows,
while requiring the exact +261 generation and the exact ordered object set.
No threshold in the application is raised. A background job may still exceed
five seconds; record that explicitly rather than claim all processing is <5s.
No local result establishes Azure latency or a production SLO.

## Stateful lifecycle slice

Lifecycle entity: existing unpublished WorkingRevision and its durable formation attempt/context.
Lifecycle transition: compatible authorized resume reuses committed tasks, commits remaining results individually and activates the original validated candidate set.
Initial durable state: immutable captured source, an interrupted attempt, exact first task checkpoint/result, remaining planned source ranges and prior working objects.
Trigger: existing `reserve_source_selection` followed by `execute_source_selection` / production source-selection resume ingress.
Authorization: unchanged current actor, role/retirement, source/configuration/revision and lease/claim/deadline checks.
Validation: original task input/result hashes, source accounting, sole deterministic materialisation, aggregate admission, lineage and actual SQL verification.
Mutable entities: authorized attempt/checkpoint/task rows and activated working objects, derived facts/frontiers and existing activation/evidence/audit records.
Immutable entities: committed task meaning, source identity/bytes, retained object meaning, canonical releases and serving registry.
Workflow state before: processing or incomplete unreviewed work.
Workflow state after: the original kernel's in-review/blocked outcome with the same candidates and unresolved work; no approval/readiness escalation.
Release state before: absent or existing historical release.
Release state after: unchanged.
Serving state before: existing registry active set.
Serving state after: unchanged; no unpublished result becomes served.
Expected API result: existing resume result/refusal and existing task-status responses.
Expected UI result: same saved candidates and progress; document-storage explanation describes grouped activation writes.
Failure result: late activation failure rolls back the complete working-object/fact/frontier/generation/evidence change; previously committed task results survive for retry.
Restart result: a fresh production runtime observes the same committed task and object results; no process cache or temporary batch is authoritative.
Recovery result: a compatible retry reuses committed tasks with the existing identity and fencing semantics; no new exactly-once provider guarantee.
Legacy-data result: native0 generation remains unchanged; old single-row writers and layouts retain their contracts, with or without the new migration.
Required black-box scenario: interrupt after the first task commit, restart, resume the same 130-task source, prove reuse and exact final result, then restart and verify it; inject activation/COMMIT failure and retry without losing committed work.
Explicit non-goals: changed candidate semantics, combined task commits, new concurrency/model behavior, envelope-layout cutover, data backfill, provider tuning, deployment or W2/W3/W5/W6.

## Owners, migration and rollback

Rewrite target: existing `object_delta_postgres_v1.write` insertion path and
the database's `advance_object_generation` trigger, installed by the existing
workflow migration runner. Why local patching is insufficient: client batching
alone still runs the expensive document update for every row under migration021.

| Truth / route | Authoritative owner and unchanged enforcement |
|---|---|
| Source and candidate identity | Immutable source owner; existing source validation and `knowledge_materialisation_v1` are the only pre-review creator. |
| Task durability, attempts, budgets | Formation task store/checkpoint owner; each committed task remains independent; actor/source/generation/claim/deadline fences remain current. |
| Working history | Workflow document store and original revision validator; generic processing activation, re-extraction, direct source/review/full-bundle callers use the existing physical writer. |
| SQL integrity | Each returned identity, position and exact JSON must equal its planned row; count/duplicates/missing rows reject. Existing mutation epochs and final physical set seal detect extra trigger writes and hidden history changes. |
| Generation | Database-owned count of actual object DML for task-v1 documents. New statement triggers include old binaries/direct SQL, INSERT/UPDATE/DELETE, multiple documents, empty and suppressed writes. Native0 remains unchanged. |
| Prepared review | Its existing writer already groups some DML and retains intermediate transition checks; only generation maintenance becomes grouped. Its safety/performance regressions are included. |
| Facts/frontiers | Existing per-row triggers and document-owner seal; no new cache or second authority. |
| Publication/recovery | Existing mutable-working guard, canonical publication store/registry and reconstruction owners; no serving or published-state writer is introduced. |

Supported runtime topologies: both complete PostgreSQL production compositions,
with and without optional review cards, task-v1/native0, direct/old single-row
writers, separate connections and restarted processes. File-only adapters do not
use this SQL path and retain their behavior.

Persisted-state impact: one compatible migration replaces the row generation
trigger with three statement triggers over PostgreSQL transition relations.
It adds no durable table/column, content, identity or new authority. The final
generation value is identical for the same actual rows. All original document
guards still execute when its counter is updated. Per-row object epoch/fact
triggers remain installed. Statement-local intermediate generation values are
not exposed to another command because existing document serialization remains.

Compatibility/migration plan: atomically replace the trigger through the
registered, digest-controlled migration runner; migration is repeatable and
performs no data rewrite. New binary works with the old row trigger (correct
but slower); old binaries work with the new statement triggers. No custom GUC
or caller-supplied bypass may suppress generation maintenance. Deploying schema
or binary remains outside this repository implementation.

Rollback/recovery plan: reverting the binary reads identical ordinary rows.
Restoring the original row trigger also preserves existing data/counters and
restores previous performance. Native tests compare pre/post migration data,
idempotent application, legacy writer privileges, migration rollback and failed
transaction behavior. No destructive down-migration or production restore.

Cutover trigger: exact native migration/writer/fencing/restart proofs, stated
performance budgets, separate adversarial review and normal repository/CI checks;
human merge/deploy decisions remain separate. Cleanup/decommission criteria:
only the superseded generation row trigger is replaced; no dual counter or
temporary writer. Failure blast radius: all PostgreSQL object mutations and
formation checkpoint invalidation; shared review and publication guards receive
regression coverage.

Adversarial proof matrix: returned row alteration/suppression/reordering/extra
write, hidden history and epochs, multi-document and native0 generations,
single/multi-row INSERT/UPDATE/DELETE and zero rows, concurrent checkpoint/write,
deferred COMMIT rollback, initial/final task failures, retained-task retry,
schema-before/binary-before upgrade and rollback, restricted old writer,
both production compositions and optional-card absence.

## Executed result

The five matched pairs at the runtime implementation commit
`5df87a987764bbcd60e44b34402ffe52b558118a` reduce median resume from
24.374409s to 9.555206s; the worst head run is 9.783557s. Instrumented object
insertion drops from 16.140029s to 0.304127s. The original acceptance budgets
above remain unchanged. All runs still exceed five seconds; this slice does
not close the broader audit or establish a production SLO.

The [evidence record](../../evidence/729-w4/README.md) contains every sample,
post-timer restart proof, server/driver profile and final verification outcome.
The separate [adversarial self-review](../audit/w4-formation-database-review-2026-11-07.md)
records boundary coverage, the injected-check-removal counterexample and limits.
