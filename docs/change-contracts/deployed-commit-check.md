Change class: B
Promise: Both deploy workflows and the documented manual ZIP route reject a running console whose health identity or exact packaged commit differs from the requested release.
Proof: Execute the three checked-in post-deploy commands against a local HTTP server; an old SHA with HTTP 200 fails, the exact SHA passes, and invalid metadata/transport plus bounded startup retries are checked through the same CLI.
Touches lifecycle invariants: no
Rewrite risk: none

## Program design (#684)

Authority/mechanism: packaging writes the exact checked-out commit into
`config/deployed_commit.txt`; `/health` reads that marker via `deployed_commit()`.
The current deploy steps only use curl's HTTP success status.

Call path after this change: production workflow (`inputs.commit_sha`), test
workflow (`github.sha`, the checked-out revision), or manual ZIP runbook
(`METIS_MAIN_SHA`) -> one read-only CLI -> GET /health -> exact status, service
and SHA comparison -> shell exit status. The new gate blocks acceptance of a
different running version; it does not grant deployment/publication permission.

Only command-local retry state changes. No durable state, identity, authority,
application endpoint, database, Blob, provider or domain mutation changes.
Existing deployment activation, main ancestry, environment identity and approval
guards remain in place. Transport time/body bounds affect only this checker.
No stateful Class B overlay is needed for these stateless reads.

One CLI reuses curl, which all existing deploy routes already require. Curl's
config file and redirects are not used; each call is limited to 10 seconds and
64 KiB. The CLI logs fixed diagnostic codes and the expected commit, never a
response body, URL or raw transport error. All nonmatching responses can retry
within the same bounded startup window. Exhaustion returns nonzero.

The original route-level probe on base 59208f0 produced 3 failures (old SHA
accepted on each route) and 3 passes (expected SHA). This deterministic trace
directly establishes the defect; no speculative hypothesis/instrumentation phase
or production replay is necessary.

## Validation and remaining release gates

Run the route probe, CLI failure/retry cases, existing deploy/packaging/step9
checks and the repository's mandatory verification sequence. Native PostgreSQL
or Azure availability is not claimed by a local health server. CI, Sherlock,
Argos and William's merge/deploy GO remain separate requirements.

## Geprobeerd en mislukt

- The first test harness treated YAML folded run lines as separate Bash lines.
  That produced incidental `curl: no URL` failures. The harness now respects the
  folded scalar before running the real command; only the three intended
  old-SHA assertions fail on the unchanged base.
