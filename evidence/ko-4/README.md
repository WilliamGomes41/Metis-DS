# KO4 core verification

Core implementation belongs to issue #1006 and PR #1007. The source-context
phase remains pending on #942; this package does not complete that phase.
The operator owns merge and deployment. Parent #1005 has landed; the root
verified integration `837b115f` is an ancestor of main `3462291d` and their
trees match. PR #1007 now targets main. Its original integration branch must
not be used as its merge target after the parent closes.

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
| Native independent full-set endpoint closure on `5b8fa397` | 37 passed in 24.86s, including malformed source/target identity and valid support |
| Native independent candidate exception closure on `2621773f` | Four passed in 1.82s: unresolved PDF refuses without writes; resolved graph, historical HTML and genuine structural conversion succeed |
| Active retained 888 native POST producers | 19 passed in 76.14s after explicit positive assessment/N/A inputs in its two executable fixture scripts; original draft, no-write, semantic refusal and lock-cycle assertions retained; archived measurements untouched |
| Architecture, compilation, diff | Passed at `fa77d584` |
| Frozen performance method | All five source hashes verified; acceptance pending explicit quiet GO and immutable final head |

The chronological [independent native report](native-adversarial.md) retains
its original head boundaries, failed diagnostics, scoped closures and remaining
contradiction finding. Referenced existing native artifacts are copied into
`native/` with a SHA256 manifest. Its final contradiction closure will be
posted separately at the exact committed fix head.

The 768px long-text screenshot revealed cramped internal columns despite zero
page overflow. The stacking threshold moved from 760px to 960px; 1024px and
1440px retain the approved two-column design. The final independent browser
pass used source `5b8fa397` and exact three-file harness head
`13b10ee9bada80f645b700d714e5e95b84856758`: one passed in 46.06s. The root
personally inspected the stacked 768px long card and the 1440px N/A receipt.
Screenshots, exact result, native keyboard trace and the 34.6-second real
support-repair-to-approval film are retained in [live-5b8](live-5b8/).
Model fixture output and Blob network transport are substitutes; decisions
enter actual HTTP commands, use PostgreSQL and survive a server restart.
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

Automatic review also identified an overly broad boom exception for existing
Kandidaat objects. A real unresolved PDF graph reproduced approval of an
unassembled existing KO. The exception now applies only to genuine structural
to-KO conversion. Resolving graph structure before individual reviews remains
supported, followed by graph confirmation; historical boom and bundle flows
are preserved. Native graph, bundle and conversion checks passed 22 cases in
14.60s after the fix.

Explicit N/A alongside valid confirmed support now refuses instead of hiding
the actual relation on the receipt. Native first-review reproduction failed
because no refusal occurred; the first/second-review and truthful-receipt
suite passed 75 cases in 34.26s after the fix. This postdates the retained
5b8 film and needs its own exact-head independent closure.

Independent browser runs found a hidden N/A control caused by reusing an
adjustment-only CSS class, and an inherited header overflow at 768px. Both
were fixed and verified with native keyboard/geometry checks. The further
internal readability correction passed the visual inspection recorded above.

Pstack no-comments used a fresh read-only reviewer: eight redundant comments
or docstrings removed across the implementation and final browser integration,
machine-consumed release markers retained, no suppressions or constraint
comments added. Deslop inspected the bounded final source and producer diff.
Interrogate findings are grounded in actual
independent native/browser runs; no unavailable model seats are claimed.

The published restart diagnostic retained a strict physical-row failure:
document revision increments 18 to 19 on restart while its envelope payload,
objects, bindings, events and source remain identical. The same real publish
and restart on baseline 837 reproduces it. This is recorded as pre-existing
startup debt, not a passed whole-physical-state restart assertion, and no
unrelated startup rewrite was introduced.

## Post-01bc native and CI corrections

The first 01bc performance execution was stopped for correctness work: eight
executions finished, execution nine was partial and execution ten never
started. None of those timings is acceptance or reused for the next candidate.
The frozen method and baseline remain unchanged; the next runtime head needs
a fresh complete five-pair run.

Real native comparison found that an identical successful BOOM approval retry
was accepted by baseline 837 but wrote again; 01bc refused it. A primary retry
while second review was pending was refused on both heads. The bounded fix
lets BOOM reach the existing exact reviewer/command-hash/current-binding no-op,
including pending-second work, while preserving existing non-BOOM semantics.
Zero-write idempotence is an improvement, not a relabelled baseline property.
Valid PDF/initial-graph-update controls for both policies passed two cases in
1.49s, retaining negative/conflicting/new-command refusal and stale CAS.

Another native comparison exposed a historical approved heading reclassified
as exception retaining its old approval stamp without a valid binding. The
01bc post-state guard correctly refused that invalid result. The existing pure
revision builder now handles genuine structural-heading to non-BOOM KO entry
through its existing version, predecessor-lineage and governance-reset code.
It does not invent selected materialisation or broaden all raw records into
knowledge revisions. Stronger assertions retain the approved heading history,
require a new open unpublished successor, invalidate structural authority and
preserve the existing four-eyes requirement. The heading, existing T11,
native guard and bundle group passed 61 cases in 35.79s.

Actual remote CI revealed missing explicit positive decisions in native
thread/process callers, existing browser fixture seeds/clicks and two batch
payloads. Their fixtures now explicitly provide the three answers and N/A
through real commands/visible controls. All existing assertions remain.
The six previously failing browser cases passed in 46.05s; affected native
A08/D5 controls passed; both positive batch cases passed in 3.85s. Four MET36,
discrepancy and closure cases passed in 24.54s with their original budgets and
history/source/no-write assertions. Only the executable positive producers in
the retained 951 probe changed; archived measurements remain untouched.

Three legacy-compatibility tests now install actual persisted historical
revise rows through the native fixture installer instead of asking a current
production command to write a new obsolete state. Their original closed-route,
requested-revision and published-startup-immutability assertions remain.
The outcome-strength fixture first assembles its real graph through the
existing graph-update command; four legacy/outcome cases passed in 3.68s.
The proposed explains target remains visibly labelled as unconfirmed support
beside six unchecked answer radios; its updated markup assertion passed in
1.00s. These are bounded local results on 01bc plus the recorded working-tree
fixes; final committed-head independent closure and all new CI shards remain
required.

Initial remote shard-zero logs for both Python versions could not be retrieved
through the available connector; artifact access was also unavailable under
the configured network policy. The initial failure inventory is therefore
explicitly incomplete. No test was skipped or suppressed for that limitation;
the next CI run must pass all eight complete native suite shards and the
browser/characterization jobs.

## Remaining verification

Post-b82 CI diagnostics identified three test-only compatibility/setup repairs.
The rollback test now proves every pre-existing event is unchanged, explicitly
checks the new current approval's three answers/N/A, and compares only the
known common fields of new decisions created by the pinned old binary; both
backends passed in 17.96s. Policy fixtures assemble their graph through the
real command while retaining an active scorelist KO and all reviewer/risk
assertions; five cases passed in 3.29s. The exact legacy-discrepancy HTTP probe
now submits explicit attempted-approval answers so it reaches its original
semantic refusal; its complete rejection/report assertions passed in 1.09s.
The original partition-zero diagnostic exercised 1,991 distinct cases plus
five known-file exclusions; its final unknown suffix passed 1,553 cases with
one optional skip. This is bounded diagnostic coverage, not a fresh full CI
partition pass.

Production/configuration, frozen performance methods and shared fixture
composition remain unchanged from measured runtime
`b82a046592961c4cb4ec8c1240a33bfadd944cdc`. Its fresh complete 80-save
performance run passed; the independently recomputed durable result is
[recorded on PR #1007](https://github.com/WilliamGomes41/Metis-DS/pull/1007#issuecomment-6690387964).
Those timings remain labelled b82, not the later test-only commit. A fresh
complete final-head CI run is still required.

Final-head remote CI, exact-head closure of the last contradiction guard,
final source read-only audit and frozen approval/correction p95 acceptance
remain required. The actual responsive browser proof above is bounded to its
recorded source/harness heads. A later test/evidence-only head needs explicit
runtime equivalence against the measured head. No merge, deployment, source
phase completion or performance acceptance is claimed here.


### Legacy structural HTTP carrier correction after f3

Actual legacy structural path cards contain no clinical answer controls. The
first/second adapters previously manufactured an explicit three-empty-answer
carrier, blocking an otherwise supported structural approval; the reachable
decision-passage adapter had the same issue. Absence now remains absence only
when none of the three field names is submitted. Blank, partial and negative
carriers stay explicit; final prepared KO approvals retain the native guard.

The focused real PostgreSQL/HTTP suite passed 15 cases in 6.75s, covering
structural first/required second approvals through both supported second
routes, supplied-answer refusals without writes, clinical missing-answer and
path-to-KO refusals, and legacy reject/later. A valid clinical second decision
refuses specifically `review_assessment_required` without answers, then saves
with explicit three-Yes/N/A on the same eligible tuple. Three existing compact
and legacy clinical parity cases also passed. The decision-route RED used a
valid native revision and refused `review_assessment_requires_three_yes`; an
earlier exploratory scoped-token failure was a fixture CAS error, not proof
of the adapter defect.

This correction changes runtime source. The b82 80-save PASS above remains
historical evidence and cannot establish acceptance for this adapter head.
Fresh immutable-head HTTP closure, source audit, complete remote CI and a new
full frozen 80-save performance run remain pending. Source-context phase #942
remains outside the completed core scope.
