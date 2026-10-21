# Review render source reuse — #548

Change class: B
Promise: Review overview, task and passage rendering reuses identical reconstructed source within one calculation without changing validation or review decisions.
Proof: Authenticated HTTP parity and reconstruction-count regression for the overview with retained V3 source records, all task views and passage detail; repeated-request freshness; source-mutation, invalid-candidate/context and isolation tests.
Touches lifecycle invariants: no
Rewrite risk: none

The installed `/review` overview calls `review_workboard_items`, including
PostgreSQL summary enrichment, then `review_work_item` and `source_accountability`.
Although #544 scoped this calculation, retained-source checks in
`verify_literal_source` and context checks in `bind_context` bypassed its reader
and reconstructed the entire source each time. Both now use the existing
operation-local derived-block reader. Tasks and passage details call
`_render_review_room`, whose duty, inventory and source checks previously ran
outside that scope. The existing scope now also wraps this shared renderer,
including its preview/correction callers.

One input snapshot owns at most two derived views: candidate-only blocks and
full-source blocks including headings. Heading filtering still precedes
reconstruction in the candidate path; full-source reconstruction keeps headings.
Alternating checks reuse both views. Input changes invalidate both views.
Every candidate, source record and context still passes all validation; no
approval is cached. Exceptions restore the caller's scope, a later request
reconstructs afresh, and callers outside a read scope reconstruct independently.

No durable state, account rule, review binding, publication rule, schema or
processing command changes. The existing bounded scope remains the only reuse
mechanism; there is no new durable cache or authority.
Rollback is a code revert with no data rollback.

The regression follows login through the actual installed HTTP review route
with ingested synthetic source selections. The overview test also retains V3
source records and executes the real PostgreSQL summary/enrichment methods with
disposable storage adapters. Its list-status read uses a fixed projection to
isolate rendering from database I/O. Tests compare complete HTML with uncached
rendering, pin generated interaction identifiers only, and verify that stored
objects remain unchanged. Further checks exercise alternating representations,
heading preservation, invalid source mappings and source/context mutations.
Native storage and Azure latency are not measured by these fixtures.
This repair alone does not establish
the cause or resolution of a particular production timeout, nor does it separate
upload from object formation.
