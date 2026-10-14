# A1 read instrumentation

Change class: C
Promise: Request diagnostics additionally report exclusive time and a bounded parent/child phase tree, source reconstruction/reuse/input-comparison counters, and the running commit; no response, verdict, hash, durable state or control flow changes.
Proof: Fail-first tests in tests/test_a1_instrumentation.py (13 failing/erroring on c7a9959, passing after), unchanged existing diagnostics and source-reuse suites, and the full local suite compared with the same base.
Touches lifecycle invariants: no
Rewrite risk: none

## Change

Base: `c7a99596c5ed8a9c705870ae7dfd84a545558360`. Reference investigation:
`ONDERZOEK-HELPER-HERVATTEN.md` (helper cost and resume failure).

1. `src/request_diagnostics_v1.py`, `diagnostic_phase`: every phase keeps its
   inclusive time and now also its exclusive time (inclusive minus the
   inclusive time of directly nested phases). `request_finished` adds
   `exclusive_ms` to each `phases` entry, a `phase_tree` keyed by the path of
   fixed phase names (`review_render/objects_read/db_execute`), bounded by
   `MAX_TREE_NODES = 64` with `phase_tree_truncated: true` when the bound is
   hit. `phase_started` adds `parent_phase`. Existing fields are unchanged.
2. `diagnostic_count(name)` increments one of a fixed set of request-local
   counters (`COUNTERS`); unknown names and calls outside a diagnosed request
   are no-ops. `request_finished` reports them as `counters`.
3. `src/knowledge_materialisation_v1.py`, `_read_source_blocks`: counts
   `source_reconstruction_built`, `source_reconstruction_reused`,
   `source_reconstruction_unscoped`, `source_input_compared` and
   `source_input_hashed`. The counters are placed beside the existing branches
   and never select a branch; reconstruction, reuse and comparison are as before.
4. `deployed_commit()` reads `config/deployed_commit.txt` (written by
   `src/azure_deploy_package.py`) and returns only a full lowercase 40-hex SHA,
   else `None`. The diagnostics/App Insights identity `version` uses
   `METIS_BUILD_COMMIT` when set (unchanged), else that file, else `unknown`
   (unchanged default). Console `/health` adds `deployed_commit`
   (`not_recorded` when absent or invalid); all existing fields are unchanged.

## State and invariants

Only request-local, disposable diagnostic evidence changes. No source content,
identifiers of documents, SQL, headers or exception text are added to logs: tree
keys and counter names come from fixed sets. Source identities, candidate text,
verdicts, canonical hashes, publication gate, authorization and durable writes
are untouched. `src/operations_console_v1.py` and the publication gate are not
modified. No new dependency, migration, background job or configuration.

## Limits

Exclusive time is wall time per thread of control; phases that run concurrently
inside one request are attributed to whichever phase is innermost in that
context. Recursive use of the same phase name counts inclusive time per call,
as before. The commit file is only present in deployment packages; locally
`/health` reports `not_recorded`. No merge, deployment or live verification.
