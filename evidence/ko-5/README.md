# KO-5 synthetic verification evidence

Measured runtime9cf974518d2e82939247f47e0f0ba59172131346; follow-up tests through7a81614c0e9c12ae9e26d3168e540853c3505eb9 have identical src. The evidence-only commit containing this folder must also preserve src/tests exactly. Final GitHub CI and automatic review apply to that actual PR head and remain separate from these local receipts. No merge/deployment or live Azure proof is claimed.

- performance/RESULT.md: frozen matched10starts/200ordinary card GETs, raw samples, scripts, hashes, independent recalculation, limiter/profile boundary and actual DOM checks.
- native/REPORT-9cf.md:49independent native cases plus actual previous KO4 source version code performing second approvals on the same head-written database. native/REPORT-545b.md records earlier exact-head proof and its bounds.
- native/rollback_probe.py: unchanged reproducible same-database subprocess driver, using existing repository native fixtures and own disposable PostgreSQL databases.
- code-review/ko5-code-review.md: findings, actual red/green counterexamples, independent review and later bounded follow-ups. Earlier receipts are explicitly pinned rather than retagged.

All data in this folder is synthetic or source/code evidence. No operator production counts, account, host, raw source document, session/cookie, access token or production database receipt is included.

## Reproduce

Use exact clean source checkouts at the pinned base/candidate; install repository test dependencies, real PostgreSQL and Chromium/Playwright for DOM proof. Scripts record original workspace paths and local owned database namespace; adjust these consistently for another machine, and freeze new hashes/protocol before new measurements. Do not overwrite the committed receipts or reuse these numbers for another head.

For performance, seed.py generates the923paragraph synthetic fixture using native ingest and the baseline. Initial setup must create side databases by cloning that owned seed, copy the fixture root to runtime-base/runtime-head, and add base_dsn/head_dsn entries to fixture.json pointing to those owned clones. runner.py then resets ONLY those owned side clones and uses the same immutable seed. Set KO5_QUIET_GO=1, KO5_HEAD_SHA and KO5_HEAD_CHECKOUT before running it with the repository Python; preserve all raw results. Run view-confirmation.py once per side after timing and view-confirmation.cjs with the recorded Playwright/Chromium dependencies. This is an auditable original driver, not a machine-independent one-command installer.

For native rollback, follow the exact command in REPORT-9cf.md with METIS_TEST_POSTGRES_DSN pointing to a disposable local server and PYTHONPATH to the candidate. Driver creates/drops its own isolated database through tests.postgres_support. Supply separate base and actualKO4 checkouts; --old-act selects which old binary executes the real second-review commands. Never point this proof at production.

KO4 SHA references identify public historical source versions used in synthetic local compatibility tests; this bundle makes no assertion about any live deployment.
