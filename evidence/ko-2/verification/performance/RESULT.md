# V4.1 acceptance: FAIL

Legacy initial-card p95 exceeds10%:60.425→73.196ms(+21.14%). Legacy whole-save p95 also exceeds10%:1055.435→1256.677ms(+19.07%). Native gates and all PostgreSQL JSON-byte gates pass. No observations were removed and no further run started.

Product f64c476b9cde822af650397c1c938a98c83dcb09 versus baseline595fe8f233fdee98dfb67609bd5c7206136ee956. Five alternating baseline/head pairs per fixture;15samples/path/side. Nearest-rank p95 is max of15. The fixed10% server-p95 and JSON-byte-p95 criteria are unchanged.

| Fixture/path | Server median ms base→head | Range base | Range head | p95 delta | JSON bytes p95 base→head | Byte delta | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
|legacy/card|47.712→49.238|45.361–60.425|44.274–73.196|+21.14%|26,231→28,127|+7.23%|FAIL|
|legacy/save|990.671→1030.424|866.022–1055.435|898.417–1256.677|+19.07%|19,859,838→19,892,540|+0.16%|FAIL|
|native/card|37.358→36.908|30.893–52.384|34.290–44.011|-15.98%|33,436→35,436|+5.98%|PASS|
|native/save|246.043→265.208|213.093–346.743|230.904–346.826|+0.02%|1,618,365→1,675,263|+3.52%|PASS|

Whole-flow median change:legacy990.671→1030.424ms(+4.01%);native246.043→265.208ms(+7.79%). These medians do not override failed p95 gates. The new bon is measured and remains real additional work.

| Fixture/path | Wall median ms base→head | Wall p95 ms base→head | Physical connections base→head |
|---|---:|---:|---:|
|legacy/card|48.595→50.263|61.279→74.181|6→6|
|legacy/save|995.038→1033.785|1057.847→1262.653|19→22|
|native/card|38.214→37.870|50.361→45.008|6→6|
|native/save|247.565→268.614|350.556→352.172|19→22|

All20executions pass their correctness checks:60durable approvals,30exact HEAD assessments,20startup-immutability checks,20after-stop committed-event checks,10real full-section expansions. Zero forced reaps; all child exits areSIGTERM(-15). Both detached worktrees are clean.

Source-display optimization is observed:both initial-card paths use6physical connections, matching baseline. HEAD still performs one additional bounded display SQL query(card22versus21). Source closure/fragments remain unchanged, hashes/member checks retained. Standalone bon uses3connections/11queries;whole save22connections versus19baseline. Bon median/p95:legacy19.550/28.227ms;native19.245/28.400ms.

V4.1 changes only log-finalization in the external observer:save complete parent HTTP timings/request IDs/proof flags to a raw transcript before teardown, close client and stop/join child, then parse finalized request_finished logs. Every timed HTTP flow, fixture, security check and budget stays unchanged. Probe SHA256fb391e729d961d9bdf54c09627f6a5b9deb346ed918c609f4421d0464f238722;server SHA256c35ff047ca57ca548f20dcf0db9968e5ea0e42db0dd9061f94de8b2d4851b749. Entire five pairs restarted anew; no favorable baseline reuse. Original V2/V3/V4 failures and incomplete V4-f64c bootstrap remain in separate directories.

The fresh serving process only composes ordinary production startup over parent-seeded persisted PostgreSQL/source files and serves actual HTTPS. Parent exclusively seeds, parses HTML/HTTP/logJSON and verifies. Default GC remains enabled([2000,10,10]);no forced collection, runtime tuning, profiling callbacks, in-child seed or capture observer. All direct validation follows all3timed flows; exact events are reverified after process stop. Actual POST→standalone bon→next is fully included and compared to baseline POST→next. Optional explicit full-section read is separately retained after the timed flows. Secure production session cookies stay enabled; local certificate is trusted by the client.

Local Python3.13/PostgreSQL17 synthetic fixtures legacy923/92 and native128/128. Initial host load0.07;pair-start loads0.63/0.90/0.90/0.97. Root stopped other local test/browser/build jobs during the measurement. This is local budget evidence, not an Azure SLO or production traffic claim. Default GC and OS scheduling remain ordinary runtime behavior; this run did not record GC callbacks/process CPU/scheduler or PostgreSQL executor plans, so their contributions cannot be assigned from these records.

See record-diagnosis.json and DIAGNOSIS.md for every per-pair distribution and measured attribution limits. The failed budget remains a release gate; this report does not grant an architecture exception or justify another repeat without a new specific hypothesis.
