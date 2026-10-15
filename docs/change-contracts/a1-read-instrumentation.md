# A1 read instrumentation

Change class: C
Promise: Request diagnostics MOETEN additionally report exclusive time, a bounded parent/child phase tree, source reconstruction/reuse/input-comparison counters and the running commit; responses (except the additive health field), verdicts, hashes, durable state and control flow MAG NIET change.
Proof: Fail-first tests in tests/test_a1_instrumentation.py (red on c7a9959 and, for the inspection and Product API health fields, red on c3666c4; all green after), unchanged existing diagnostics, source-reuse, service and Product API suites, Product API backward-compatibility check, and the full local suite compared with the same base.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18 (Metis `docs/BESLUITEN.md`). Rules below use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG.

## Change

Base: `c7a99596c5ed8a9c705870ae7dfd84a545558360`, merged with main `8db82cb` (#624). Reference investigation:
`ONDERZOEK-HELPER-HERVATTEN.md` (helper cost and resume failure).

1. `src/request_diagnostics_v1.py`, `diagnostic_phase`: every phase MOET report its
   inclusive time and its exclusive time (inclusive minus the inclusive time of
   directly nested phases). `request_finished` adds `exclusive_ms` to each `phases`
   entry and a `phase_tree` keyed by the path of fixed phase names
   (`review_render/objects_read/db_execute`). The tree MAG NIET exceed
   `MAX_TREE_NODES = 64`; when the bound is hit it MOET report
   `phase_tree_truncated: true`. `phase_started` adds `parent_phase`. Existing
   fields MAG NIET change.
2. `diagnostic_count(name)` increments one of a fixed set of request-local counters
   (`COUNTERS`). Unknown names and calls outside a diagnosed request MOETEN be
   no-ops. `request_finished` reports them as `counters`.
3. `src/knowledge_materialisation_v1.py`, `_read_source_blocks`: counts
   `source_reconstruction_built`, `source_reconstruction_reused`,
   `source_reconstruction_unscoped`, `source_input_compared` and
   `source_input_hashed`. A counter MAG NIET select a branch; reconstruction,
   reuse and comparison MOETEN stay identical.
4. `deployed_commit()` reads `config/deployed_commit.txt` (written by
   `src/azure_deploy_package.py`) and MOET return only a full lowercase 40-hex SHA,
   else `None`. The diagnostics/App Insights identity `version` MOET use
   `METIS_BUILD_COMMIT` when set (unchanged), else that file, else `unknown`
   (unchanged default).
5. Health endpoints MOETEN add `deployed_commit` (the file value, `not_recorded`
   when absent or invalid): console `/health` (`src/operations_console_app.py`),
   inspection `/health` (`src/service_app.py`) and Product API `/v1/health`
   (`src/product_api_v1.py`, `HealthResponse.deployed_commit`, not required, so
   the OpenAPI change is additive and passes `product_api_contract.py --check`).
   Existing health fields MAG NIET change.

## State and invariants

Only request-local, disposable diagnostic evidence and the additive health field
change. Logs MAG NOOIT contain source content, document identifiers, SQL, headers
or exception text: tree keys and counter names come from fixed sets. Source
identities, candidate text, verdicts, canonical hashes, publication gate,
authorization and durable writes MAG NIET change. `src/operations_console_v1.py`
and the publication gate are NOT modified. No new dependency, migration,
background job or configuration.

## Limits

Exclusive time is wall time per thread of control; phases that run concurrently
inside one request are attributed to the innermost phase in that context.
Recursive use of the same phase name counts inclusive time per call, as before.
The commit file exists only in deployment packages; locally every health endpoint
reports `not_recorded`. No merge, deployment or live verification.

OPENVRAAG-A1-1: is wall-time attribution for concurrent phases inside one request
acceptable, or MOET a later PR measure per task?
