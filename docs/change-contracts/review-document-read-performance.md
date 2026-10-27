# Review document reads: one input set per calculation

Change class: B
Promise: Opening a Review document avoids archived processing payloads and repeated source/queue calculations, while every eligible passage and required source warning remains reachable.
Proof: Native PostgreSQL HTTP cost bounds, queue paging/parity, source and candidate mutation checks, partial-formation warnings, stale commands, and before/after total GET measurements.
Touches lifecycle invariants: no
Rewrite risk: none

## Ground → Sketch → Agree → Implement → Scrap

Ground: completed against `559ab4f`. The existing GET operation owns temporary
read inputs. PostgreSQL objects/bindings and existing domain validators remain
authoritative. Passage reads already use compact envelopes and prepared source
views. Explicit document tasks still load full envelopes, independently derive
several unused queues, and render all matching passages.

Sketch: compare two structurally different designs, developed by separate
read-only design agents using the same repository evidence:

* A: capture the existing compact envelope plus full current object/binding set
  in one read transaction, prepare source once, derive the requested queue once,
  and page expensive presentation after exact domain classification.
* B: page object identities in SQL before payload loading. This cannot preserve
  exact task membership/counts without replicating source, policy and approval
  validation or introducing a durable, revision-stamped task projection.

Choose A: reuse existing read/domain owners without new persisted projections,
schema, global cache or writers. B is rejected for this repair because it changes
authority and invalidation topology. Both assessments are design alternatives,
not empirical proof of runtime performance.

Agree: the user authorized implementation directly; no extra checkpoint needed.
Implement: first establish red HTTP cost/paging checks; extend the existing read
capture, pass immutable source explicitly, then remove unused queue calculations
and paginate presentation. No unrelated scaffolding or deletion.
Scrap: reconsider if exact task classification needs a second authority or a
permanent derived cache. Do not remove source validation to achieve a time budget.

## Usage and data ownership

`read_review_document(console, account, snapshot_id)` captures the compact
envelope, complete object history and bindings using the existing repeatable-read
transaction. It returns the existing temporary Review input shape. It keeps the
existing objectset revision for document forms, including batch actions; this
does not introduce another command token or approval authority.

`_render_review_room(..., read_inputs=inputs, queue_page=1)` shares those owned
objects/bindings/source views. `_render_review_index(..., page=1)` classifies the
requested task with the existing exact domain functions and renders at most 25
queue rows per page, retaining the entire captured set for connected context.
Batch pages retain one existing coherent group (at most 20 candidates), without
changing its membership or the number of required confirmations. Conflict
recovery shows the current group(s) containing surviving selected candidates.
Decision-tree heading and source-only exclusion forms retain their existing
complete selection. Queue navigation preserves search, return page and theme.

Source inputs are verified once at the read boundary and prepared once. No
prepared view is cached by mutable-object identity. A new request captures and
checks current state afresh. Commands retain their detached current-state reads,
authorization and CAS. History retains its explicit full historical inputs.

Only owned, disposable read state changes. No durable object, source mapping,
review decision, publication state or processing result changes. Failure to read
a required authority still fails closed; task-v1 open/uncertain formation still
loads the full status inputs and verifies full source closure. A passage window
may never prove document completion.

## Limits and rollback

One full document object read remains necessary for exact queue membership.
Paging bounds visible HTML/context work, not the exact domain input size.
Compact envelope projection bounds archived replay/attempt overhead for complete
documents; partial formation may still require those inputs. No claim of 26
object payloads per document queue or production subsecond latency is made.
Rollback is a code revert; no migration or data rollback is needed.

## Verification

The five new HTTP cost/paging checks were run on the original implementation:
all five failed on the intended full-envelope/source-comparison/unbounded-HTML
conditions. The repaired checks pass with the additional archive, concurrent
capture, partial-formation, coherent-batch, stale retry and navigation controls.

Final combined native PostgreSQL, source, read-operation, context, batch, stale
form, characterization and architecture round: **254 passed, 1 skipped**.
The skip is the existing Chromium browser acceptance without a configured browser;
there are no PostgreSQL skips. After aligning the large pure paging fixture with
the production prepared-source input, the same all-passage reachability assertions
were rerun separately and pass (1 test, 0.66 seconds).

Repository preflight, architecture boundaries, compileall, change-contract
validation and diff whitespace checks pass. Release-control preflight passes
against `origin/main`; this includes unrelated committed changes on the selected
checkout and is not a claim that all release-required suites were executed here.
No complete repository suite, production deployment or Azure/browser acceptance
is claimed.

The separately measured 300-candidate fixture uses authenticated real ASGI GETs
and disposable PostgreSQL 16.2, three requests per task, including source
preparation, SQL capture and complete response rendering. The measured JSON and
runnable harness are versioned in `evidence/review-document-read-performance/`.
The batch timing uses a sectionless source with an empty batch queue; populated
batch paging and stale recovery have separate 60-candidate native regressions.

Read-only design/code reviews found a stale-batch selection recovery regression
and lost return filters during paging. Both were repaired and have native HTTP
regressions; the follow-up review found no remaining blocker within this scope.
Those reviews did not independently run the tests.

## Integration before PR

The implementation was rebased without conflicts onto `origin/main` at
`96b22c16c6aacc554d64ccf75971595a5d549000`, retaining its Vorming/Review ownership
changes. On the integrated code (`902f3af` before evidence-only updates), the
focused native Review, source, stale-form, formation-repair, characterization and
architecture selection passes: **154 passed, 1 browser skip**.

The original 254-test result and timing comparison predate this integration;
they are not presented as new timing measurements of the integrated head.
The full local suite was attempted with fail-fast and stopped after 115 passes
because `psql` was absent from PATH. The bundled PostgreSQL 16.2 client is now
available; the complete affected Tier-D test module passes on rerun (**98 passed**).
A complete green suite on the final PR head
remains a CI requirement; the PR is offered as a draft performance improvement,
not as proof that the original production latency is resolved.

## CI follow-up on PR #872

Run `40429746475` on `c272d2d` failed in suite shards 0, 1 and 2 on both Python
3.12 and 3.13, with five unique failing tests. Other workflows, preflights,
characterization and browser checks passed. The aggregate jobs' missing XML
files followed the failed suite gate; no CI gate is removed or weakened.

All five failures reproduce locally in one 3.48-second command. The remaining
regressions still assumed unpaged lists or injected changes above the old
snapshot helper, which the explicit captured read no longer calls. Tests now:

* verify every one of 338 unresolved and 343 total passages across all pages,
  preserving exact identities, uniqueness and read-only behavior;
* observe the captured input boundary for navigation and the actual concurrent
  writer, retaining the stale form/refusal and visible-text assertions;
* bound native object-payload reads on both Review and Vorming instead of
  comparing invocation counts of different high-level helpers;
* retain the full 2,000-candidate/100-group oracle and compare the first, middle
  and last HTTP pages against those exact coherent group memberships.

The five-case reproduction is green (5 passed, 5.03 seconds). The complete
affected modules plus native Review, passage, stale-command, batch and unchanged
characterization coverage pass: **114 passed, no skips** (Python 3.12,
PostgreSQL 16.2). Production code is unchanged in this CI correction. Final
Python 3.12/3.13 CI results must be checked on the new pushed head.
