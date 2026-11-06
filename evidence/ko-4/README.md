# KO4 core verification

Core implementation belongs to issue #1006 and PR #1007. The source-context
phase remains pending on #942; this package does not complete that phase.
The operator owns merge and deployment. While #1005 is open, #1007 targets
`feat/ko2-main-integration`. After #1005 lands, verify its actual ancestry in
main and retarget #1007 to main before merging the child.

## Boundaries

The central policy checks captured current/prepared facts inside existing
atomic commands. Existing commands retain SQL, CAS, authorization and ledger
ownership. No state label, receipt, cache, schema or transaction is added.
Every new KO approval requires three explicit Yes answers and current
confirmed evidence or the reviewer's explicit N/A. Genuine structural results
remain structural. Published history remains immutable.

Both object classifications matter: non-KO/non-KO is exempt; non-KO/KO enters
the KO guards; KO/KO follows its current transition; KO/non-KO retains the
current-state/event guard without inventing a KO result. Prospective exact
bindings determine the actual approval post-state, including multiple required
reviewers. Correction commits an open successor, never a new stored revise.

## Recorded checks

Local verification uses PostgreSQL 17 and the production composition. CI uses
its configured PostgreSQL service; local results do not assert CI completion.
Run `scripts/test_postgres.sh` before native tests.

| Check | Bound result |
| --- | --- |
| Final owner focused suite at `fa77d584` | 1,202 passed in 56.90s: 1,098 pure matrix cases and 104 other focused cases, including native commands and existing reviewer-policy unit cases |
| Matrix | Independent 11 states × 9 events × 11 prepared states, alphabet coverage, four classification combinations and terminal conversion refusal; state derivation is deliberately isolated |
| Real command checks | Missing/negative answers, missing evidence, no-write refusals, real support repair and final versions, stale support, outgoing explains/incoming non-support, N/A exact bindings, replay, historical absent-facts replay, renewal, prepared wrong-state injection, structural conversion, second-review policy |
| Existing focused regression at `8bb305be` | 253 passed in 141.83s; later expanded sweep is reported separately and is not an exact-final-head claim |
| Expanded 58-file sweep | 1,124 passed, seven early failures and one optional-browser skip in 853.56s; all seven plus two further positive-form regressions passed together in 16.07s after the bounded fixes. The long run began at 8bb while development continued; this is not a single final-head green sweep |
| Review-room snapshots at `fa77d584` | 24 passed in 12.54s; deliberate heading mutation failed as intended |
| Snapshot audit | Every changed JSON value was checked: only verified stylesheet digest plus one unchecked N/A paragraph; all other HTML bytes and JSON fields unchanged |
| Independent live harness on `deb26661` | Actual browser/PG/HTTP/restart passed in 47.11s, including real linked support, separate N/A, keyboard, historical receipt, required second review and four viewport widths |
| Native independent structural-conversion closure on `71633492` | Five passed in 2.07s; original 8bb counterexample retained |
| Architecture, compilation, diff | Passed at `fa77d584` |
| Frozen performance method | All five source hashes verified; acceptance pending explicit quiet GO and immutable final head |

The 768px long-text screenshot subsequently revealed cramped internal columns
despite zero page overflow. The responsive stacking threshold is moved from
760px to 960px; 1024px and 1440px retain the approved two-column design. Final
browser screenshot inspection after this CSS change is pending. The earlier
live pass is not presented as verification of that later stylesheet.
The 24 review-room snapshots pass in 13.13s after the threshold change; their
only further golden change is the actual stylesheet digest
`7e605541c4d04c43` to `0d43211c094f766f`.

## Adversarial findings and fixes

Actual native runs found and closed three boundary defects: new negative
answers could replay a prior positive command; a path-to-node conversion could
inherit the current structural exemption; same-tuple renewal could retain the
old command hash. Regression tests retain each counterexample and positive
compatibility cases. Contradictory answer carriers also refuse before saving.
The converse KO-to-structural bundle case was restored without weakening its
original source, per-member review or publication assertions.

A later independent native run found that N/A could bypass an incompatible
confirmed semantic endpoint during second review of an existing exact binding.
All confirmed semantic endpoints now undergo the existing D4 compatibility and
current-target checks before N/A is considered. Validation visits the whole
set even after finding valid support. Native regression first failed because
no refusal occurred; the targeted command/receipt/reviewer suite then passed
70 cases in 32.41s. Exact-final-head independent closure remains required.

Independent browser runs found a hidden N/A control caused by reusing an
adjustment-only CSS class, and an inherited header overflow at 768px. Both
were fixed and verified with native keyboard/geometry checks. The further
internal readability correction above still requires its final visual pass.

Pstack no-comments used a fresh read-only reviewer: six redundant comments or
docstrings removed, machine-consumed release markers retained, no suppressions
or constraint comments added. Interrogate findings are grounded in actual
independent native/browser runs; no unavailable model seats are claimed.

## Remaining verification

Final-head remote CI, independent complete native/adversary report, final
responsive browser captures/video and frozen approval/correction p95
acceptance remain required. A later test/evidence-only head needs explicit
runtime equivalence against the measured head. No merge, deployment, source
phase completion or performance acceptance is claimed here.
