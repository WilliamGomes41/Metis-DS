# #708 B1 — project the ledger mirror from PostgreSQL after the commit

Change class: B
Promise: After a successful Storeopdracht commit in R+, the ledger mirror receives the committed review events as read from `workflow.review_events`, through one bounded read, never the process-local buffer copies and never a full ledger scan; a mirror that does not end at the command's chain anchor is rebuilt from PostgreSQL.
Proof: `tests/test_708_b1_ledger_from_pg_postgres.py`, red on main `dacbd7d` (6 failed, local and Azure R+), green after the change; existing #678/#708/R2/#741 suites unchanged.
Touches lifecycle invariants: no
Rewrite risk: high

Taalregel: MOET / MAG NIET / NOOIT. Source: decision B1 (William, 17-10 14:04) and the #708 ordering of 18-10: "Ledgerprojectie conform B1 uit PostgreSQL lezen; kleinste gerichte read; volgorde/hashketen behouden; niet standaard alle events scannen".

## Existing mechanism and smallest change

`_PostgresWorkflowReviewMixin._remirror_from_pg` already rebuilt bindings,
objects and envelopes from PostgreSQL, but appended `command.events`: the deep
copies taken by `defer_mirror_events` when the buffer flushed. Those copies are
not the authority. The change replaces only that line.

- `PostgresWorkflowReviewStore.read_events_after(previous_event_hash, limit)`:
  one SELECT of at most `limit` rows with `event_id` after the anchor row
  (`event_hash` is UNIQUE, `event_id` is the primary key: both indexed; no
  schema change). It verifies `previous_event_hash` links and each
  `event_hash` against the payload; a broken chain raises
  `workflow_review_chain_conflict`.
- `_project_committed_events`: the anchor is the `previous_event_hash` of the
  command's first event (the PG head the flush verified under the ledger
  advisory lock). Rows are appended only when the mirror's last line ends at
  that anchor and the read rows carry exactly the command's hashes. Otherwise
  it logs `store_command_ledger_divergence events=<n>` (counts only) and runs
  the existing full `_remirror_review_runtime()`.
- Rows that fail the chain check are NOOIT copied: the conflict propagates as
  a post-commit mirror failure (`store_command_remirror_failed`, U4) and no
  full rebuild runs, because `read_events()` would copy the same corruption.
- The mirror tail is read backwards from the end of the file; no full mirror
  read. A tail line whose recomputed hash differs from its `event_hash` is no
  anchor, so a tampered tail is rebuilt instead of extended.

## Domain-first overlay

```text
Domain entity/aggregate: Storeopdracht over workflow.review_events and its disposable ledger mirror.
Invariant(s): U3 unchanged; new U5: after the commit the ledger mirror is a prefix-consistent projection of PostgreSQL rows, appended in event_id order with an unbroken hash chain.
Durable state before: committed review_events rows.
Durable state after: unchanged; this change writes no PostgreSQL state.
Transaction boundary: unchanged; the projection runs after the commit, under the store lock, outside any transaction.
Failure/recovery result: a read failure is a post-commit mirror failure (U4): store_command_remirror_failed, the command stays committed. Divergence triggers the full rebuild. Rollback path unchanged.
Duplicate execution / idempotency result: unchanged; rows are appended once per command; a stale tail triggers rebuild, not a second append.
Concurrency result: the ledger advisory lock serialises inserts until the owner's commit, so the command's rows are contiguous after the anchor. Rows committed later by another runtime are not appended by this command (LIMIT n).
Audit/evidence requirement: none new; PostgreSQL stays the only ledger authority.
```

## Rewrite-risk mitigation

```text
Rewrite target: the ledger part of the single post-commit mirror writer (_remirror_from_pg).
Why local patching is insufficient: B1 names PostgreSQL as the source of the rebuild; the buffer copy is a second, process-local source.
Current authority/writer/reader map: authority workflow.review_events. Writers: append_event / _flush_buffer (unchanged). Mirror writers: _mirror_events (now fed with PG rows after commit), _remirror_review_runtime (full, failure-only and divergence). Readers: read_events (full, unchanged callers), read_events_after (new, post-commit only).
Supported runtime topologies: complete local and Azure R+. File topology and refused tiers unchanged.
Persisted-state impact: none (no schema, no data migration). The mirror stays disposable.
Compatibility/migration plan: in place; the compatibility path (raw owners, #741) is untouched because it has no command.
Rollback/recovery plan: revert; a restart rebuilds the mirror from PostgreSQL.
Cutover trigger: merge after CI, Sherlock/Argos and William's GO.
Cleanup/decommission criteria: none; command.events remains the set of row hashes to project.
Failure blast radius: a stale or fully rebuilt ledger mirror; no PostgreSQL impact.
Adversarial proof matrix: buffer copy altered after flush (projection must not contain it); unbuffered reprocessing events; stale mirror tail and tampered tail with its old hash (rebuild + warning); committed rows failing the chain check (no copy, no full read); no full read_events on the success path; no mirror write in an open transaction; existing rollback, COMMIT-failure, caught participant and post-commit failure cases.
```

## Limits

- `command.events` still decides which rows are expected; it no longer decides their content.
- Bindings, objects and envelopes were already read from PostgreSQL; unchanged.
- General mirror cleanup is #709; delete recovery is #706; other raw owners are #741.
- No merge, deployment or issue closure is authorised by these local results.
