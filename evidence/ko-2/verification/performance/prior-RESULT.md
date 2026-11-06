# V4 acceptance: FAIL

The native initial-card p95 server time exceeds the unchanged10% budget: 40.834→46.271ms (+13.31%). Every other specified p95/JSON-byte gate passes. No additional run was started.

Baseline: 595fe8f233fdee98dfb67609bd5c7206136ee956. HEAD: 97d79f9ecadbedc0cdba7dfec6abaaf91614fee8. Five alternating baseline/head pairs per fixture,15samples per path/side; nearest-rank p95 is the largest of15samples.

| Fixture/path | Server median ms base→head | Server p95 ms base→head | p95 delta | JSON bytes p95 base→head | Byte delta | Gate |
|---|---:|---:|---:|---:|---:|---|
|legacy/card|46.682→49.135|53.566→58.422|+9.07%|26,231→28,127|+7.23%|PASS|
|legacy/save|992.890→999.080|1061.071→1084.666|+2.22%|19,859,838→19,892,540|+0.16%|PASS|
|native/card|34.482→37.756|40.834→46.271|+13.31%|33,436→35,436|+5.98%|FAIL|
|native/save|227.287→261.061|284.314→310.536|+9.22%|1,618,365→1,675,263|+3.52%|PASS|

Native whole-flow median increased227.287→261.061ms (+14.86%), even though its p95 increase9.22% passes the specified p95 gate. The bon remains a real additional operation; passing the p95 gate does not mean it is free.

| Fixture/path | Wall median ms base→head | Wall p95 ms base→head | Connections base→head |
|---|---:|---:|---:|
|legacy/card|47.732→50.071|54.569→59.411|6→7|
|legacy/save|995.127→1002.371|1063.172→1089.578|19→22|
|native/card|35.370→38.728|41.075→47.504|6→7|
|native/save|229.214→264.999|286.770→313.730|19→23|

Standalone bon physical connections are3 in all30HEAD approvals, versus4 before the bounded fresh-role-read optimization;11queries remain. Bon server median/p95: legacy18.115/19.589ms, native18.606/26.843ms. The connection-count reduction is observed directly; this run does not establish a cross-run speedup because it uses a different accepted product SHA.

All20executions pass:60durable approvals,30exact HEAD assessment records,20restart-immutability checks,20after-stop committed-event checks,10real full-section expansions. Zero forced reaps; all children exit on SIGTERM(-15). The existing public form submits actual threeYes answers; the bon is standalone and actual next-navigation follows its clean link. Native continues to a real next review card. Event identity/version/hash binding assertions are preserved.

The fresh HTTPS child is composed with the existing production_application restart helper over parent-persisted PostgreSQL and source files. Parent exclusively seeds, parses HTTP/HTML/logJSON, and verifies. Child only performs ordinary production startup and serving, with default GC enabled([2000,10,10]); no forcedGC, cache/authority changes, profiling, callback observers or in-child fixture ingestion. Production Secure cookies remain enabled and the local test certificate is trusted by the client. Exact request IDs join ordinary request_finished logs after all timed flows. All proof checks run after all3flows and repeat committed-event checks after stop. Actual POST→bon→next sums are compared to baseline POST→next; no redirect/read cost is omitted. Optional full-section expansion is measured separately after all flow samples. Its bytes/time are retained in summary.json.

Frozen probe SHA256:8524677b5aa41eb75da8bc3e9e97d5183ba9f2ccfeeb1e6a24f3f976846d23a0. Frozen server SHA256:c35ff047ca57ca548f20dcf0db9968e5ea0e42db0dd9061f94de8b2d4851b749. No protocol changes during this run, no failed samples removed, no repeat or threshold changes. Prior V2/V3 failures and the V4 diagnostic/bootstrap attempts remain in separate evidence directories.

The native card failing maximum is round5/sample3(index2). Its server46.271ms includes7connections/22queries, versus baseline6/21. Median native card connection time8.609→10.060ms; SQL-execute17.503→19.110ms; review_render1.043→4.377ms. These inclusive phase timings overlap, so they must not be added. The canonical publication guard remains deliberately present and reuses the current request batch. The extra connection/query here is the missing-raw-heading/neighbor display capture (review_source_records_v1.py:230), not the canonical lookup. See native-card-diagnosis.md for the corrected attribution and bounded alternatives. This is grounds for a bounded read-ownership investigation, not permission to delete the guard or rerun until favorable.

Local Python3.13/PostgreSQL17 and synthetic fixtures(legacy923/92; native128/128), with root-owned competing jobs stopped for the entire window. Initial host load0.00, then0.54–0.94 reflecting this run. This is local budget evidence, not an Azure SLO or production-traffic claim. See summary.json for medians/p95/bytes/connections and request-breakdown.json for separatePOST/bon/next phases. Both detached worktrees are clean.
