# Navigation source reconstruction reuse — #544

Change class: B
Promise: Review navigation counts reuse identical source reconstruction within one work-item evaluation without changing source validation or review duties.
Proof: Full-source navigation regression, uncached work-item parity, invalid candidate checks, source-change invalidation, nested failure cleanup and concurrent scope isolation.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing path and authority

Authenticated home calls `waiting_task_counts`. The PostgreSQL navigation mixin
loads current objects and bindings, then calls `review_work_item`. Review duties
and source accountability repeatedly call `validate_materialised_candidate`,
which resolves selections against authoritative source fragments.

Source fragments remain authoritative. Canonical publication, review bindings,
account permissions and all admission/source checks keep their existing owners.
This change creates no durable state and changes no lifecycle transition.

## Bounded change

`review_work_item` opens a synchronous reconstruction scope. Within that scope,
`resolve_source_selection` may reuse reconstructed blocks for equal source
fragments. A deep snapshot detects in-place changes. Candidate validation results
are never cached. Only one source representation is retained, and the scope is
discarded in `finally`; nested and concurrent evaluations are isolated.

Direct calls outside this scope retain their previous behavior. There is no
cross-request cache, new storage authority, migration or Azure setting change.
Rollback is an application-code revert with no data rollback.

## Evidence and limits

The regression failed before the fix: 20 real ingested passages caused 160 source
reconstructions in the PostgreSQL navigation calculation. It now requires one
reconstruction per invocation and identical task counts. Complete work-item
outputs are compared against uncached evaluation, also for altered source or
candidate text; input data remains unchanged.

Synthetic local measurements: 80 passages fell from 7.9–8.6 s to 0.196 s;
160 passages fell from 31.51 s to 0.388 s. Timing is diagnostic evidence, not a
hardware-independent acceptance threshold. The regression uses deterministic
reconstruction counts and semantic parity.

The probe uses the production PostgreSQL navigation mixin with disposable batch
stores and actual ingested source selections. It does not measure Azure network,
database latency, Entra login or the complete production homepage. The production
login outage is not claimed resolved. PDF extraction mode is unchanged.
