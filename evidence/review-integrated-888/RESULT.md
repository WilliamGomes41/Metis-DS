# Local integrated result — #888

## Current integration after the publication move

Current production base: `e2d2302e930bbf0d10afe5dd6faad6d689648770` (#899). Integration measured on `09629b9eab64116e3dbe970ed581093ba498869a`. No production diff is added by WP4. The same harness, source manifest and original baseline are retained. Both source reconstruction hashes still identify the same pre/post algorithms.

The current native matrix passes all six cases; another three control cases pass per version in reverse version order. All ten large-case route medians still meet the 30% improvement budget.

| Formation | Route | Before median ms | Current median ms | Ratio |
|---|---|---:|---:|---:|
| Complete | overview | 14162.2 | 299.8 | 0.021 |
| Complete | individual | 13965.3 | 338.9 | 0.024 |
| Complete | inventory | 13744.5 | 324.6 | 0.024 |
| Complete | batch | 13871.9 | 311.1 | 0.022 |
| Complete | passage | 13594.4 | 333.8 | 0.025 |
| Synthetic incomplete | overview | 14258.3 | 306.4 | 0.021 |
| Synthetic incomplete | individual | 13410.8 | 337.9 | 0.025 |
| Synthetic incomplete | inventory | 13672.3 | 308.4 | 0.023 |
| Synthetic incomplete | batch | 14073.9 | 312.8 | 0.022 |
| Synthetic incomplete | passage | 26989.7 | 410.5 | 0.015 |

**Control budget remains open.** The current first round has 15 raw control misses. Across both rounds, four of 30 control comparisons remain above 15%:

| Case | Route | Incomplete | Before ms | Current ms | Ratio |
|---|---|---|---:|---:|---:|
| small | inventory | True | 55.1 | 66.8 | 1.213 |
| complex | overview | False | 71.2 | 84.2 | 1.183 |
| complex | individual | False | 55.7 | 64.4 | 1.155 |
| multiple | batch | True | 57.0 | 67.6 | 1.187 |

These are approximately 9–13 ms differences on short requests. Query counts are unchanged; reconstruction remains about 0.07–0.09 ms, while connections, SQL and other phases vary. This is insufficient to attribute a product regression or certify the no-regression budget. No threshold is relaxed and no extra production optimization is inferred from this evidence. A controlled runtime check remains necessary.

Current numerical evidence is in `current-*.json.gz` and `current-source-after.json`; earlier measurements below remain historical evidence for their own commits. The suite on the old basis was intentionally interrupted at 5,123 passes after main advanced; it is not a complete-suite pass. Final integrated suite evidence is pending.

## Earlier completed comparison on main 36c8041

Production source: main `36c80413ced37e5a4dc74a380c6b54e23235e007`. Measured integrated HEAD: `7f76a06` (evidence-only commits). Baseline: `49e50be279925b7e87d4ffa551609b998cac5869`. Python 3.12.14, PostgreSQL 16, one local ASGI process. Actual full hashes/configuration/manifests are in the raw artifacts. No deployment was contacted.

Both matrix runs passed all six cases (504 authorized measured GETs per version, plus six denied reviewer GETs). Each case has five routes, complete and explicitly synthetic incomplete formation, seven warm samples and one first-for-route sample. Stored envelopes, object histories, bindings, review and command events remained unchanged across GETs. Each state also passed one two-request concurrent passage wave.

## Large continuing source: 600 paragraphs

| Formation | Route | Before median ms | After median ms | Ratio |
|---|---|---:|---:|---:|
| Complete | overview | 14162.2 | 324.1 | 0.023 |
| Complete | individual | 13965.3 | 289.3 | 0.021 |
| Complete | inventory | 13744.5 | 302.4 | 0.022 |
| Complete | batch | 13871.9 | 304.9 | 0.022 |
| Complete | passage | 13594.4 | 350.7 | 0.026 |
| Synthetic incomplete | overview | 14258.3 | 325.6 | 0.023 |
| Synthetic incomplete | individual | 13410.8 | 324.8 | 0.024 |
| Synthetic incomplete | inventory | 13672.3 | 327.2 | 0.024 |
| Synthetic incomplete | batch | 14073.9 | 310.4 | 0.022 |
| Synthetic incomplete | passage | 26989.7 | 412.3 | 0.015 |

All ten large-case medians meet the predeclared 30% reduction budget. This establishes the local synthetic route result, not the original live incident.

## Controls and noise

The first round missed two individual control budgets: complete small overview (+26.6%) and complete multiple-document batch (+17.7%). Neither repeated: the reverse-order round gave -4.1% and -7.7%. That round instead missed complete small inventory (+24.4%). These misses remain recorded; individual rounds do not show every control within budget.

Across both rounds (14 warm samples per control/formation/route), all 30 control comparisons remain within the unchanged 15% budget. Variability in the connection/SQL timings is material relative to these short requests. Two rounds support a local median comparison, not an environment-independent no-regression or stable-tail claim.

## Preparation scaling

| Code | 150 continued fragments | 600 continued fragments | Growth | Budget result |
|---|---:|---:|---:|---|
| before | 0.515 s | 7.463 s | 14.49x | RED |
| after | 0.044 s | 0.172 s | 3.93x | PASS |

Five source-preparation samples per size/version. The full source oracle and deterministic work-volume checks are verified separately by the regression suite.

## Phase and size evidence

`comparison.json` contains total wall medians/ranges, inclusive prepare/build/reconstruct/status and SQL/fetch phase medians, JSON transfer, HTML size, and a conservative lower bound for unattributed time. Complete per-request trees/counters remain in the gzip JSON. Nested phases overlap and are not added. `controls_two_rounds` preserves the aggregate control comparison; original round samples remain available.

## Remaining evidence

No p95, process-cold, database-cold, sustained-load or production-latency result is claimed. Timed objects are fresh with zero review bindings; heavily revised/bound/context-rich documents have functional regression coverage, not timed performance evidence. The incomplete inventory still executes source-accountability twice; no decision cache was introduced.

Current deployment identity, representative production source and authorized logged-in runtime proof remain open under #695/#699/#680. Keep #888/#884 open. A merge or these local samples cannot complete the project.

## Repository verification

Pending the final repository checks and full suite. No completion claim for those checks yet.
