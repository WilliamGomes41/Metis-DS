# V4.1 recorded-tail diagnosis

Takeaway: the measured new-flow work is one bounded source-display query on the existing connection, plus the standalone bon(3connections/11queries,~19ms median). No new duplicated large-source read is evidenced. Most of the failed legacy tail increase occurs in existing reads with identical query counts and byte volumes. These records cannot establish whether runtime/GC/scheduler/database variability or allocation timing caused that inflation. The10% gate remains FAILED; calling it merely noise would overstate the evidence.

Independent review subsequently identified that every V4.1 pair ran baseline beforeHEAD. This correlated ordering limits causal attribution; it does not turn the failed gate into a pass or establish noise as the cause. A separately versioned six-round3AB/3BA plan addresses that limitation without excluding any earlier observations. No new timing requests, profiling hooks, production edits or runtime changes were performed for this diagnosis. Full per-sample CSV and record-diagnosis.json retain every observation.

## Per-pair server distributions

Each cell is median[min,max]ms over3samples. Every row remains included in the final p95.

|Fixture|Pair|Card base|Card HEAD|Whole base|Whole HEAD|
|---|---:|---:|---:|---:|---:|
|legacy|1|46.607[45.614,47.012]|49.727[49.038,50.508]|959.127[872.216,984.062]|1030.424[898.417,1038.472]|
|legacy|2|52.096[48.131,58.705]|44.737[44.274,47.291]|1027.185[895.474,1036.276]|1002.281[934.146,1011.254]|
|legacy|3|51.297[47.712,60.425]|47.657[46.194,59.180]|1022.787[915.052,1055.435]|1035.700[903.667,1054.044]|
|legacy|4|47.013[45.361,47.552]|59.309[49.238,60.739]|990.671[866.022,999.771]|1156.769[938.445,1256.677]|
|legacy|5|48.118[47.198,50.372]|54.944[45.725,73.196]|1013.810[891.965,1039.125]|1097.658[1022.700,1125.611]|
|native|1|31.529[30.893,33.202]|38.905[34.290,44.011]|223.716[213.093,272.730]|271.914[265.208,292.202]|
|native|2|36.932[35.909,37.467]|38.877[35.913,39.942]|251.810[232.992,286.214]|255.588[246.125,304.327]|
|native|3|38.669[34.918,43.966]|34.684[34.366,36.908]|227.505[221.273,277.240]|231.534[230.904,315.007]|
|native|4|37.358[33.956,38.618]|35.430[35.178,36.669]|223.644[219.274,285.732]|244.278[239.748,297.916]|
|native|5|43.592[39.240,52.384]|40.307[39.432,41.777]|296.141[246.043,346.743]|267.733[253.913,346.826]|

Legacy HEAD tails concentrate in pairs4–5. Pair2 HEAD whole maximum1011.254ms is lower than baseline1036.276ms, while pair4 HEAD maximum1256.677ms exceeds baseline999.771ms. Native baseline also has a high final-pair tail346.743ms, so variation is visible on both sides. This is distributional evidence, not proof of an external cause.

## Actual per-request work

SQL/connect/fetch columns are median inclusive phase times; overlapping phases must not be added to other inclusive totals. Bytes are returned PostgreSQL JSON; query counts include actual driver-instrumented statements.

|Fixture/side/stage|Server median[min,max]ms|Connections|Queries|JSON byte min–max|Connect/execute/fetch median ms|
|---|---:|---:|---:|---:|---:|
|legacy/base/card|47.712[45.361,60.425]|6–6|21–21|25,672–26,231|9.137/29.992/0.942|
|legacy/base/post|430.988[394.434,523.436]|12–12|68–68|5,714,188–5,718,272|20.635/242.277/27.967|
|legacy/base/next|503.749[469.084,624.447]|7–7|20–20|14,100,344–14,141,566|13.661/131.414/65.362|
|legacy/head/card|49.238[44.274,73.196]|6–6|22–22|26,614–28,127|10.243/31.150/0.946|
|legacy/head/post|450.742[400.685,560.458]|12–12|68–68|5,714,424–5,718,508|22.771/240.812/28.590|
|legacy/head/next|516.108[474.079,718.020]|7–7|20–20|14,100,344–14,141,566|12.814/133.415/77.773|
|legacy/head/bon|19.550[17.240,28.227]|3–3|11–11|31,276–32,466|5.870/8.159/0.642|
|native/base/card|37.358[30.893,52.384]|6–6|21–21|32,822–33,436|9.610/18.881/0.954|
|native/base/post|167.955[155.583,223.942]|12–12|68–68|983,690–988,548|19.291/101.582/5.104|
|native/base/next|64.870[57.510,149.068]|7–7|28–28|626,577–629,817|12.371/26.900/4.650|
|native/head/card|36.908[34.290,44.011]|6–6|22–22|33,822–35,436|9.315/19.762/1.103|
|native/head/post|165.647[152.324,199.346]|12–12|68–68|983,926–988,784|18.383/102.396/5.251|
|native/head/next|64.857[57.611,124.673]|7–7|29–29|628,577–631,817|11.362/27.258/4.773|
|native/head/bon|19.245[17.231,28.400]|3–3|11–11|53,196–54,662|5.491/7.939/0.759|

## Legacy card maximum: same shared reads slow down

HEAD maximum73.196ms is pair5/sample2(index1). Compare the same baseline pair/sample50.372ms, rather than assigning the difference between two unrelated maxima:

|Non-overlapping phase-tree bucket|Baseline|HEAD|Difference|
|---|---:|---:|---:|
|Unscoped4connections|5.678|9.630|+3.952|
|Unscoped13SQL executions|29.175|43.617|+14.442|
|Entire scoped source-read capture|4.544|7.366|+2.822|
|Render inclusive|0.963|1.495|+0.532|

The total matched difference is22.824ms. Most is in the same13unscoped statements/four connections, not a new renderer query. Source capture retains one connection and one hydrate call; its statements change7→8for the same display-row query moved into that open connection. All-card legacy medians:source records4.905→5.744ms;hydrate0.209→0.212ms;render0.990→1.230ms. Initial-card total median47.712→49.238ms(+3.20%). Its extra bounded JSON1,896bytes at the p95 does not imply a new whole-source load. The prior avoidable source-display connection is gone:6physical connections on both sides.

## Legacy whole maximum: existing POST and next-page tails

HEAD whole maximum1256.677ms is pair4/sample3(index2). Its corresponding baseline sample990.671ms has the same substantive work:

|Request|Baseline ms|HEAD ms|Difference|Queries base→HEAD|JSON bytes behavior|
|---|---:|---:|---:|---:|---|
|POST|416.822|510.430|+93.608|68→68|HEAD adds236bytes of persisted answer evidence|
|Bon|—|28.227|+28.227|0→11|Bounded receipt31–32KB|
|Next|573.849|718.020|+144.171|20→20|Identical14MB JSON reads|

The266.006ms matched difference consists of237.779ms inflation in existing POST/next work and28.227ms real bon cost. This does not identify a safe way to remove237.779ms. POST physical connections stay12on both;next stays7on both. At this HEAD next maximum:the same7unscoped fetches cost162.889ms versus118.632ms baseline(+44.257);review_capture349.494versus274.190ms(+75.304);revision84.788versus its baseline lower value;source hydration45.034ms is close to ordinary baseline ranges, not an extra hydration count. Review render12.727versus13.029ms does not account for the tail. Exact per-request phases in request-breakdown.json/record-diagnosis.json include the shared SQL/read/fetch costs.

Across all legacy samples,POST median430.988→450.742ms;next503.749→516.108ms;bon19.550ms. Next source-read medians176.424→178.791ms, capture281.438→289.779ms, render12.801→12.791ms, same one capture/read/hydrate each. The wide14MB overview on this exhausted legacy contextual queue already exists on baseline. It is not introduced by the bon.

## Native flow confirms the bounded new cost

Native POST median167.955→165.647ms;next64.870→64.857ms;bon19.245ms. Whole median246.043→265.208ms(+7.79%). HEAD next adds the bounded display query(28→29), keeps7connections and only2,000additional JSON bytes. Native initial-card median37.358→36.908ms;both have6connections. These observations support removal of the redundant display connection; they do not establish a cross-run speedup or override legacy failure.

## Correlation limits and recommendation

Recorded host-load snapshots are0.07,0.63,0.90,0.90,0.97during five pair starts. They are neither per-request scheduler traces nor proof of zero OS/database variance. Default GC stayed enabled, but no GC callbacks, process CPU samples, PostgreSQL EXPLAIN/pg_stat observations or OS scheduler traces were recorded. Therefore no causal GC/OS/database diagnosis can be made. Driver execute/fetch times include waiting and decoding; they are not pure server CPU.

There is no newly evidenced avoidable duplicate to repair from this run. The remaining new work is the necessary bounded display read and the bon; the measured~19ms bon cannot explain a201ms p95 legacy gap by itself. Do not widen ownership, remove authority/source checks or change formatting to chase this maximum. Keep the performance gate explicitly failed/pending. A further product optimization needs a separately grounded hotspot; another acceptance repeat needs a specific justified cause and a fresh quiet authorization. Architectural admission or a different budget has not been granted by this evidence.
