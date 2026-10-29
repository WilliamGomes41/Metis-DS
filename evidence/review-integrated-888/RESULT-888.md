# Integrated WP1–WP8 acceptance — 29 October 2026

**NOT READY for MET-17/#888/#884 completion.** The integrated implementation
works in the executed native scenarios, but the fixed lock and small-control
budgets are not fully met. Production runtime evidence is also absent. No
budget, domain rule or existing test assertion was relaxed.

The production tree is exactly merged main
`e2e261d09b4e24427eed57aa3a72c95bc5dcde3b`. The additional opt-in measurements ran
on evidence commit `0137ad233220c14b551c46af3abcfb95701a9a1a`; `src/` and `db/`
are unchanged. WP5 baseline: `7adb588d957e9f5461f338349e11535654ea2d10`.
Original controls: `49e50be279925b7e87d4ffa551609b998cac5869`.
Each result retains Python, actual PostgreSQL version, actual checkout and
measurement hashes. All runs used the pinned Python environment and the same
isolated native PostgreSQL16.15 server sequentially, without competing heavy
test runs. Provider transport and HTML inputs are explicitly synthetic.

## Matched WP5 → WP8 measurement

`wp5-matched`, `wp8-legacy` and `wp8-compact` each contain two native cases and
106 completed authenticated requests: five routes × eight observations, plus
the original POST/refusal/retry sequence and actual approval redirect/overview
GETs, at both sizes. All six native cases passed. Every raw sample, phase tree,
fixed SQL category, request-progress inventory and JUnit result is retained as
`.json.gz`/`.xml.gz`. `integrated_report.py` rejects unmatched source/configuration/
history/harness, missing requests, missing command phases and failed/skipped
native JUnit. A missing transaction on the known pretransaction refusal is
distinct from a missing measurement on a command that enters the transaction.
An empty 303 body is valid; a missing rendered 200/400/409 body is rejected.

The 32/128 workload manifests match exactly across all three runs: 34/130 current
objects, 42/138 stored versions, five bindings with one current matching binding,
two history candidates and depth two. The 128 source has 129 fragments and 20642
bytes, SHA256 `e56d5ddab6ae2099308159113eec01a95898d1334d5dd494edf405b4f317c9da`.
Compact cards were explicitly prepared and checked outside requests before a
fresh production composition. No measured GET rebuilt its inputs. Legacy and
compact runs have the same code and source; only the explicit reader mode differs.

| Candidates | WP5 approval / lockhold ms | WP8 legacy approval / lockhold ms | WP8 compact approval / lockhold ms |
| ---: | ---: | ---: | ---: |
|32 |1751.4 /1293.8 |250.6 /155.9 |236.0 /127.2 |
|128 |7961.7 /6960.3 |396.6 /241.0 |407.9 /269.9 **FAIL** |

The matched legacy comparison has no engineering-budget miss. The compact
comparison is **red**: 128 approval lockhold 269.903 ms exceeds 250 ms, although
transaction 269.867 ms is below 500 ms and the complete POST is below 3000 ms.
The earlier unchanged reference matrix separately observed 321.7 ms lockhold at 128;
that miss is retained in `wp8-reference-matrix.json.gz`. Later faster samples do
not erase either miss. The scale matrix performs forty read requests before
the first POST; the original reference sequence performs only its normal
passage/refusal requests. Neither is a guaranteed cold-process/database run.

Warm overview medians at 32/128 are 208.6/299.8 ms in legacy and 91.2/123.3 ms in
compact. Both modes meet the 3 s overview and 5 s detail goals in these synthetic
samples. All five routes and the actual approval redirect GET are measured;
the 128 redirect is 991.3 ms legacy and 992.7 ms compact. This is a local absolute
budget result, not a claim that every detail route improved or a production SLO.
Seven warm samples support median/range only; no p95 is inferred.

The 128 compact approval's untruncated tree places 199.208 ms of database execution
inside the 269.867 ms transaction. In-transaction source reconstruction is 0.075 ms;
the 71.275 ms native source read occurs before the transaction. Local storelock
wait is 0.058 ms. This localizes the remaining cost toward SQL/write work; it does
not identify a specific trigger, query or PostgreSQL wait as the root cause.
Only two object rows are written; boundedness alone does not prove the absolute
lock budget. Diagnostic JSON volume is not network wire bytes, and inclusive
phases must not be summed.

## Original GET controls and large sources

`control_benchmark.py` is the unchanged historical harness from commit
`490a240d9b457a4aee59813a731c1060f6bf8ad7`, SHA256
`f15fc4f537c051b64139821fb6f812495699a88c0fbe9294d1f7494658c7052e`.
Its digest equals the original retained before/current artifacts. Three controls
(small, complex, multiple persisted documents) were run baseline→current, then
current→baseline, with original lifecycle projection and default legacy reader.
All 12 native cases passed, 240 sequential plus 12 concurrent GETs per round,
and three nonassigned-reviewer refusals per round. GETs preserve the full stored
envelopes, history, bindings and review/command events. The actual comparison
and all four rounds are retained under `controls-*`.

The first round has **two of 30** control-budget misses: complete complex passage
116.4→142.1 ms (+22.0%) and complete multiple-document batch 75.1→91.1 ms (+21.3%).
Across both rounds, **eight of 30** remain above the unchanged 15% budget:

| Control | Before / after median ms | Ratio |
| --- | ---: | ---: |
| Small individual, incomplete |89.0 /102.5 |1.152 |
| Multiple inventory, complete |73.6 /90.0 |1.224 |
| Multiple batch, complete |74.8 /90.5 |1.210 |
| Multiple overview, incomplete |175.8 /207.6 |1.181 |
| Multiple individual, incomplete |77.9 /92.8 |1.191 |
| Multiple inventory, incomplete |86.5 /108.2 |1.250 |
| Multiple batch, incomplete |83.1 /114.5 |1.378 |
| Multiple passage, incomplete |212.8 /262.7 |1.234 |

These are measured misses, not yet attributed product defects. Neither reverse
order, absolute latency under the user-flow goal nor prior historical misses
waives this criterion. `report.py --assert-budget` remains red and retains the
first-round misses even when computing the combined control results.

The integrated tip also passed the original 150/600 continuing-fragment and
300-candidate occupied 20-member batch cases, complete and explicitly synthetic
incomplete formation: three cases, 240 sequential plus 12 concurrent GETs and
three denied outsiders. Maximum individual observed responses were 613.0,
1130.7 and 1982.7 ms respectively. Exact stored-state preservation and the occupied
batch assertion remain unchanged. `large-current.*.gz` retains this evidence.
The historical ≥30% large-source improvement evidence remains in RESULT.md;
the refreshed large run is not a new contemporaneous WP1-before/after ratio test.

## Integrity and remaining work

The exact existing WP5 CI reference selection passed **28 tests, zero skips**
on the merged production tip. It includes real binding-INSERT fault P9021 and
deferred COMMIT fault P9022, exact rollback and retry after a fresh composition,
live role/context and binding-only legacy/task-v1 changes, variant-specific
retry contracts, context/single and batch/single concurrency, publication race
and disjoint-object storage merge. Its numerical records, request/test inventory
and native JUnit are retained under `wp8-reference-*`.

The additional integrated source/card/command/rollback selection and final
repository/CI checks are recorded with the final PR and verification artifact.
The source is not changed by this evidence PR. No old assertion, source oracle,
timeout, required SQL budget or difficult fixture is removed.

Next: profile the document/object/fact SQL executed under the native command
lock, then reproduce and isolate the eight small-control misses before proposing
a bounded fix at the existing owner. A new persistent identity, authority,
migration or shared boundary would require the repository's rewrite-risk
reclassification; this evidence-only issue does not silently authorize that.
Repeat the same red-capable reports after any fix, retaining the current red
artifacts. Complete process-cold/representative heavy-context/load coverage where
required; current samples do not establish tail latency or sustained concurrency.

Deployment identity, original production workload and authorized logged-in live
evidence remain under #695/#699/#680. There is no production preparation,
configuration switch, deployment or live measurement in this work. Keep
MET-17/#888/#884 open; no production GO follows from these local tests.
