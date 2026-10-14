# Slice 4 verification — issue #620

Base: `fe5c4b7` (main after slice 3 / #619).
Environment: Python 3.12.14, existing development dependencies, local isolated
HTML source and injected canonical/source authorities. No production/Azure writes.

## Executed behavioral evidence

- Real locked publication captures readiness, selected exact canonical object
  tuples, commit readback and completion under one request ID. Duplicate boundary
  records cannot be treated as a complete route.
- A publisher can download evidence through the independent HTTP route. Anonymous
  and reviewer access are denied by the existing authentication/role boundaries.
- A reviewed representative HTML fixture can be published through existing gates.
  Product API real-mode HTTP readback returns the same release-ID, object version
  and content hash, including with a new Product application and console instance.
- Invalid source/readback and unauthorized publication create no release and
  preserve the unpublished state.
- Local copy failure after canonical commit remains distinguishable from no commit;
  existing retry converges on the same release rather than creating a second one.
- Registry read failure preserves the observed canonical commit, but does not
  manufacture current serving success.
- Optional telemetry failure does not undo a valid release.
- Missing browser, command/review binding, source/tuple identity, readback, runtime
  identity or process-restart observation prevents a complete route claim.
- Native query shape is parameterized, filters exact release plus active registry,
  reads no canonical content and limits item count. This check uses an injected
  connection and is not native database execution evidence.
- Export composes evidence in one JSON dossier with input hashes and refuses to
  overwrite an existing export directory.

Final affected combined run with configured Chromium: 62 passed, covering
publication evidence, request diagnostics, Publish presentation, durable publication,
section incidents and architecture invariants.

## Actual browser execution

Chromium/Playwright on a local HTTP server: login as publisher -> visible Publish
confirmation -> submit -> successful Publish room -> evidence download -> exact
real-mode Product HTTP readback. All assertions passed. Storage authorities were
injected teststores. This proves browser behavior, not native database durability.
A distinct-process restart was not part of this browser run.

## Full-suite environment diagnosis

Initial full run: 3541 passed, 438 skipped, 4 failures. All four failures reproduce
unchanged on main at the same base commit.

- Three SSRF HTTPS tests route the synthetic HTTPS hosts through inherited proxy
  settings; the fixture server rejects CONNECT. Removing proxy environment variables
  makes all three pass without product/test changes.
- `test_parent_process_death_terminates_transport_worker` compares subprocess PID
  with parent PID from /proc. Here os.getpid() differs from /proc/self/stat's PID:
  the shell/runtime and mounted procfs have different namespace identities. This
  fixture fails before testing child termination (zero matched children). The same
  failure reproduces on unchanged main. Child-termination behavior is unproven in
  this environment; the test is neither weakened nor skipped to obtain a pass.

Final full run without inherited proxies: 3547 passed, 438 skipped, 1 failure
(the reproduced /proc namespace check). Final readout hardening was additionally
covered by the 62-test affected suite. Native PostgreSQL tests in the full suite
remain unconfigured/skipped. No claim of a fully green suite or deployment
readiness is made while this environment check remains blocked.

## Open acceptance evidence

Native PostgreSQL transaction/read/restart and Azure Blob evidence are not provided
by injected stores. No representative production publication or Azure restart was
performed. Actual deployment identity, source and persisted release must be supplied
for live acceptance; absent evidence remains absent in the report. The PR remains a
draft until the remaining acceptance/check evidence is established. The independent
revision-read failure is projected as unavailable while retaining the already-read
canonical release; diagnostic metadata failure does not become an HTTP 500.

## Surface review

The change adds one read-only evidence projection and extends existing HTTP/export,
request diagnostics and canonical registry read paths. Existing authorization,
readiness and publication transactions remain the owners. No new durable state,
lifecycle, migration, alternate gate or repair executor is introduced. The strict
external-schema validator has several independent failure checks intentionally:
missing/contradictory observations must not be silently accepted. Those checks
validate evidence input; they do not recompute publication domain rules.
