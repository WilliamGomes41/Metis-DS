# Diagnostics slice 4 — #620

Change class: B
Promise: one read-only dossier links publication access, exact reviewed tuples,
canonical commit, active registry, Product HTTP readback and a later process read.
Proof: existing durable publish/retry/failure contracts plus observation, identity,
access, export and complete/missing-route controls. Actual Azure proof is separate.
Touches lifecycle invariants: no
Rewrite risk: none

Behavior is stateless. Canonical publication store owns release history and the
publication registry owns serving eligibility. No new gate, lifecycle state,
transaction, audit writer, schema or repair executor is introduced.

Existing path: Publish room -> consider_publish/publish ->
DurablePublicationConsole._publish_locked -> canonical persist_published_release ->
registry -> ProductState._reload_real_records -> source readback -> Product HTTP.
Diagnostics reuse release_for_snapshot and active_publication_rows under current
publisher authorization. One selected snapshot/revision is bracketed by reads.
The ordinary fast observation never reconstructs source or evaluates readiness.
Existing role/readiness/commit/serving boundaries remain unchanged.

GET /source-selection/publication-evidence downloads bounded compact identifiers,
exact hashes, read timestamps and runtime identity. It cannot publish or repair.
The report distinguishes a historical release from exact active release membership.
Failed follow-up after commit must not be diagnosed as no commit. Native read
errors become unavailable, with exception text omitted. Independent equal reads
are not an atomic database snapshot. A different runtime_id and later observation
are necessary for a process-restart claim; a new console in one process is not.

The offline export accepts observations and optional explicit route evidence.
Supplied input is operator evidence, not cryptographically authenticated by the
report. Input hashes preserve provenance. Unknown readiness/review bindings,
browser usability, Product HTTP and restart are retained as missing evidence.
HTTP 200 alone never proves complete publication. Canonical tuples, source and
release must agree before the route can be reported as proven.

Critical dependency chain (elapsed durations unknown): authority trace -> bounded
observation -> incident integration -> exact route controls -> regression proof.
Deployment and representative production source publication are not authorized
by this repository implementation ticket.

The production registry read is extended with active_release_items: parameterized,
read-only exact release membership with LIMIT 2049, no canonical content projection.
The existing locked durable publisher emits compact best-effort observations at
its already computed readiness, submitted exact itemset, commit readback and return.
No extra readiness call or transaction write is added. Missing/failed telemetry
cannot reverse a valid release. POST /publish joins the existing request observer.
