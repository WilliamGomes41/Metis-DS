# Review source input reuse — #887

Change class: B
Promise: An incomplete-formation check for a Review passage uses the complete verified source without repeating full-source comparisons for each candidate.
Proof: Red-to-green authenticated PostgreSQL route, unchanged full status and persisted state, partial-window and integrity controls, fixed-source candidate scaling, and matched local measurements.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing authority and read path

`read_review_passage` captures the authorized passage context using the existing
PostgreSQL read transaction, then prepares its source window after the
transaction. `_review_formation_notice` deliberately obtains the complete
envelope for the separate deep `processing_status` check. `stored_extraction`
validates the extraction record hash, fragment hash and source identity;
`incomplete` and the existing replay and source-accountability owners still
determine whether formation is open. A bounded passage view cannot establish
complete formation.

The change passes a prepared **complete** extraction to the existing status
function within the same owned read operation. It reuses the passage carrier
only if it is the full view and the captured and complete source identities,
verified extraction hash and Docling context match exactly. Otherwise it
prepares the verified full extraction. If there is no owned read, no usable
passage source, no stored extraction, or the optional carrier cannot be built, the existing full-source
status path remains in use; replay and closure validation still run. A new
request captures fresh inputs. No approval, review result, completion flag,
durable state, schema, source identity or authorization is cached or changed.

The mutable request envelope, object and binding inputs remain owned by the
existing `ConsoleReadSnapshot`. `SourceFragments` retains its existing immutable
payload and source indexes. No prepared value crosses a request boundary or
replaces PostgreSQL, Blob, replay or review authority. Code revert needs no
data migration. Tests exercise a changed full extraction and changed captured
source identity, as well as missing source bytes, missing/corrupt extraction and corrupt replay.
An independent PostgreSQL writer commits a deliberately stale binding during
passage capture: the existing repeatable-read snapshot keeps it out of the
current passage; the next read sees it as invalid. Objects, envelope and review
events remain unchanged by the GET. In a throwaway checkout, changing the read
transaction to READ COMMITTED made that concurrent-binding test fail. Existing
object-capture and stale-command tests remain in place.

## Reproduction and evidence limits

On main `f7ca760dcf316e893e648c8090393b4fa02f539b`, an authenticated Review
passage with actual incomplete formation performed eight full-source comparison
operations on a small synthetic fixture. The new regression test initially
failed on this exact condition and passes with no comparisons after the change.
It verifies the same complete status, warning, source, objects, bindings and
review events. When the selected passage window contains one of four source
fragments, the formation check receives all four. A deliberately wrong
implementation that passes the smaller window failed that test in an isolated
throwaway checkout. The controlled selector in that test uses the existing real
window function with the selected object; it is not a claim about all paging.
A second isolated mutation that ignored the captured source identity also
failed the identity-mismatch test; neither mutation is part of the change.

The fixed-source candidate test runs the existing `review_work_projection`
against one prepared source with 1, 50 and 300 candidates. No full-source
snapshot comparisons occur. The source carrier's immutability is also checked.

`evidence/review-input-reuse-887/large_passage_probe.py` uses the existing
synthetic 300-candidate authenticated PostgreSQL fixture. It sets an explicit
synthetic incomplete finding before the read, verifies that the existing replay
returns that finding, then measures five requests without writes during those
GETs. Instrumented runs recorded 179,700 source comparisons per request before
and zero after. Because per-comparison instrumentation affects timing, separate
uninstrumented runs measured medians 0.720 and 0.608 seconds respectively; an
earlier after-run measured 0.625 seconds. The individual samples are preserved.
This is a local synthetic comparison, not a
production latency or p95 claim. Object counts include the document row.

The existing route-matrix fixture was run before and after for overview,
document and passage, complete and incomplete formation, multiple documents,
and continuous source. It stubs lifecycle status and uses synthetic provider
behavior. Alternating repeated runs of the small incomplete fixture give passage
medians 0.0617/0.0615 and 0.0643/0.0590 seconds (before/after), respectively;
all samples and the complete matrix are in the evidence directory. The first
full-matrix control timings varied across runs, so they are not treated as a
conclusive general regression test or production measurement.

The incomplete document inventory still computes source-accountability twice
with the same observed input. That projection includes current review and
closure decisions; this change does not memoize it or feed a caller's cached
decision into the domain authority. A safe independent reduction is not proven
here. Work package 4 owns the integrated runtime and user-performance proof.
