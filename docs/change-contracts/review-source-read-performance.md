# Review source-read performance

Change class: B
Promise: Repeated source validation within one read calculation reuses unchanged source representations without serializing the complete source for each candidate.
Proof: Authenticated HTTP regression, unchanged rendered output and durable input, source/candidate mutation rejection, and before/after timing on the same 1,000-candidate fixture.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing mechanism and bounded change

Base: `4615c5da`. GET requests enter the existing `source_reconstruction_scope`.
Review workboard and source-accountability readers call exact source validators,
which use `knowledge_materialisation_v1._read_source_blocks`. Its content-keyed
cache previously serialized and hashed the complete fragment list on every hit.
The HTTP regression reproduced 160 complete-source hashes for 20 candidates.

Compare the most recently used source with an independent comparison snapshot
before computing another content hash. On changed or alternating input, retain
the existing content-keyed lookup and collision equality check. Both candidate
and full-source views remain separate. Every validation still executes.

The comparison snapshot keeps JSON numeric distinctions: Python otherwise treats
`True`, `1`, and `1.0` as equal, and also equates signed zero. The private numeric
wrapper exists only in the comparison copy, never in reconstructed blocks,
candidate data, JSON persistence, or validation results. Native container equality
avoids a slow Python traversal on every hit. In-place nested changes remain visible.

## State and invariants

Only disposable derived read state changes. Source identities, candidate text,
source mapping, bindings, review decisions, authorization, publication gates,
formation configuration, and all durable writes remain unchanged. Existing
ContextVar entry/exit and nested-scope behavior govern isolation and cleanup.
There is no new global cache, durable authority, migration, or background job.

## Evidence and limits

- Before modification the focused HTTP regression fails: 160 source hashes,
  expected at most two for the document's source views.
- Final focused suite covers HTTP review, source selection and processing
  management, retained-source and candidate fixtures, mutation rejection,
  nested scopes, exception restoration and parallel isolation, plus architecture
  invariants. 35 tests pass.
- Same-process comparison with 1,001 objects (1,000 candidates plus document):
  original reader 29.258 seconds; fixed reader 4.876 and 5.131 seconds.
  Authenticated `/review`, actual production summary/enrichment methods,
  disposable storage adapters, local synthetic source; identical HTML and
  unchanged domain objects. This is not an Azure/PostgreSQL latency measurement.
- An independently generated local HTTP baseline measured 31.007 seconds.
- Instrumented final overview: 8,000 source-block reads, one source
  reconstruction; dynamic hash time 0.316 seconds. Other object-level hashes
  still run. No validation result is cached.
- The proposed five-second target is not consistently proven: the repeat is
  5.131 seconds. Production latency and the reported gateway 502 remain unverified.
- Full local suite: 3,471 passed, 418 skipped, four failed. The failures concern
  transport-worker parent-death detection and three URL/redirect security tests;
  the unchanged base reproduces these failures in this environment. PostgreSQL
  and other prerequisite-dependent skips are not counted as passing proof.
  Tests used Python 3.12 with available runtime dependencies, not a clean
  installation of the CI lockfile. Native CI remains outstanding.
- No production change or deployment has been made.

## Review and rollback

Surface verdict: approve with notes. One existing module is extended locally;
the comparison snapshot is justified by source fidelity and measured hot-path
cost. Repository and architecture preflights pass. Release mapping is evaluated
against the changed paths, not an empty uncommitted Git range.

Engineering readiness: local repair evidence established; production resolution
not established. Use the existing release pipeline and an authorized review of
the patch before deployment. Code rollback restores the old reader; no data
rollback or schema migration is needed. Configuration is unchanged.
