# Final runtime performance budget: PASS

Exact base07db5080666f0428a454f5a705e50825a4fc5506 versus9cf974518d2e82939247f47e0f0ba59172131346. Clean detached source; later7a81614c contains test-only changes, src byte-identical. Actual Codex shared Linux host, Python3.13.5 and PostgreSQL17.11, synthetic fixture only. Frozen protocol/scripts and hashes were verified before and after the run. Owner and native test workloads were idle.5cores, starting load average0.82/1.15/0.82; warm OS/PG caches.

Observed fixed5% budget passed; this is not a production latency or causal speedup claim.

| Metric | Base | Candidate |
|---|---:|---:|
| Fresh-process actual application import+build_app mean,5starts/side |822.623ms|561.340ms|
| Startup median |810.620ms|557.748ms|
| Startup range |749.119–934.578ms|531.381–596.574ms|
| Ordinary authenticated Review GET server p95,100requests/side |48.233ms|44.664ms|
| Card sample range |36.495–56.059ms|36.171–58.731ms|

Five AB/BA pairs:AB,BA,AB,BA,AB;10fresh interpreters; each one untimed warm GET then20measured GETs. All10PIDs distinct,200/200responses200. Every measured response has6database connections/22queries/26770JSONbytes. Same923synthetic paragraphs/92selected candidates/925objects, same seed cloned into owned side databases and source/runtime copies. No discarded observation, retry, threshold adjustment or measured rerun. The separately labelled28024 cProfile calibration is excluded; owned clones were reset before decisive measurements. See LIMITER.md and excluded-profile.json for resource/path evidence.

Root independently recalculated both means and nearest-rank95 from all10raw JSON files, checked protocol/source hashes and database shapes; root-recalculation.json records PASS. Separate untimed HTML captures were parsed with real Chromium/native scripts: both exact SHAs show the ordinary actionable Review page with source context,3enabled unanswered question groups and native POST form. The approval button is correctly disabled until answers are selected. No read-only object page, receipt or error banner was timed. Both DOM assertions passed; view-*-semantic.json and the capture scripts are included.

The existing974-p4b driver measures repair POST/GET, so it is not represented as ordinary card timing. Current driver times actual native application imports/composition/startup and the normal candidate GET. It is not machine-cold boot, Azure, PG16, browser network latency or concurrent-user measurement. Prior44de/545raw evidence remains unchanged in its original workspace folders; none was relabelled as9cf.
