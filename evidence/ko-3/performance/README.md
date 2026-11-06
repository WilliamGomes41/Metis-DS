# Frozen KO-3 performance method, version 1

`protocol.json` records PREPARED status at freeze time. Final results live on the implementation PR/#1002; this file does not claim a measurement has passed. `source.sha256` covers the four scripts and protocol; runner checks the four script hashes again before every execution. Do not change the method after seeing results.

Required gates: first actual `consider_publish` wall p95 and authenticated selected `/publish?document` server p95 must each be <=1.10 times baseline. Baseline is c6fa679b7c0cc630d24e32e4578e21398cb796c4. Six counterbalanced pairs (3 AB/3 BA), 18 samples per side/path, nearest-rank p95 (maximum at this sample count); retain every sample. SQL/byte counts are attribution only, not extra gates. Direct query counters come from a separate untimed warm call and do not describe the measured first call.

Fixture: 900 raw fragments, 899 paragraphs, one heading and 92 definition candidates. Each execution uses four fresh production children: one HTTPS child with actual publisher login/three selected pages, then three direct children each measuring one first consider call. Setup/startup are outside timing. Default GC/auth remain. Parent finalizes observations and compares business database/source fingerprints after all timed paths. Only deliberately created auth sessions are excluded from business-state comparison. Existing baseline fields must match exactly; head only adds object_readiness.

Reproduction in this workspace:

1. Copy the five frozen files to `/tmp/ko3-perf/`; verify `sha256sum -c source.sha256` in this directory.
2. Create clean detached worktrees `/tmp/ko3-perf/base` at the baseline and `/tmp/ko3-perf/head` at the exact committed head.
3. Use PostgreSQL on port 55432, `/workspace/.venvs/metis-ds/bin/python`, and an ordinary localhost TLS certificate/key at `/tmp/ko3-perf/server.crt` / `server.key`. Private keys are never committed. Run the repository PG helper first.
4. Stop other local PG/browser/test work. Set `KO3_HEAD_SHA` to the full committed head and run `python /tmp/ko3-perf/runner.py`. It refuses an existing output directory.
5. Run the committed `summarize.py OUTPUT_DIRECTORY`. It validates source hashes, all 24 ordered start/completion events, exact heads, 36 measured consider calls, 36 pages and all immutability/parity proofs before calculating both gates.

The baseline-only setup smoke is not acceptance and none of its observations are reused. Preserve failed runs; never overwrite or silently discard observations.
