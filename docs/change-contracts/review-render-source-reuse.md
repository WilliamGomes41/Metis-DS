# Review render source reuse — #548

Change class: B
Promise: Review task and passage rendering reuses identical reconstructed source within one render without changing validation or review decisions.
Proof: Authenticated HTTP parity and reconstruction-count regression for all task views and passage detail, repeated-request freshness, and existing source-mutation, invalid-candidate and isolation tests.
Touches lifecycle invariants: no
Rewrite risk: none

The installed `/review` route calls `_render_review_room` for tasks and passage
details. Its duty, inventory and source checks previously ran outside the
work-item reconstruction scope added by #544. The same existing scope now wraps
the shared renderer, including its preview/correction callers. It retains derived
blocks for equal authoritative fragments only during that synchronous call.
Every candidate still passes validation. Exceptions discard the scope, source
changes invalidate reuse, and a later request reconstructs afresh.

No durable state, account rule, review binding, publication rule, schema or
processing command changes. There is no new cache implementation or authority.
Rollback is a code revert with no data rollback.

The regression follows login through the actual installed HTTP review route
with ingested synthetic source selections. Its list-status read uses a fixed
projection to isolate the renderer from database I/O. It compares the complete
HTML with uncached rendering, with only generated interaction identifiers pinned,
and verifies that stored objects remain unchanged. Native storage and Azure
latency are not measured by this fixture. This repair alone does not establish
the cause or resolution of a particular production timeout, nor does it separate
upload from object formation.
