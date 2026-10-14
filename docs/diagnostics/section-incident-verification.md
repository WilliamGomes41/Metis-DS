# Issue #614 verification

Local implementation commit tested: 6719d409 (code and tests). This report is
added afterward. Base: c58f018a; the two modified pre-existing files have identical
blob SHAs to PR #613 at c5dac3ec. The remote commit adds only the issue-614 diff.

## Passed

- 38 focused Python checks: section incident/export, request diagnostics,
  source-selection read cost and architecture invariants.
- Includes real authenticated Metis source-selection through Chromium -> HTTP ->
  request observer -> offline incident projection. Existing document/object
  snapshot is unchanged; document ID and session contents are not exported.
- Seven real Chromium/local HTTP scenarios: visible section, HTTP 200 wrong page,
  403, login redirect, 502, timeout and process unavailable. POST writes were
  blocked and secret query content excluded. These are simulated upstream
  responses, not proof of Azure gateway behavior.
- Repository preflight, release-control preflight against origin/main,
  compileall and architecture-boundary checks passed after committing the diff.
- Deployment packaging test passed separately with a stable commit.

Environment: Python 3.12; Node 24; installed Playwright module with independently
installed Chromium 133. Standard Playwright browser downloads failed in this
executor; the alternative browser ran the same probe. No browser package or
binary was added to the repository or Azure runtime. Native PostgreSQL and live
Azure ingestion were not tested.

## Broad-suite result and diagnosis

A broad run reported 3497 passed, 418 skipped, 6 failed. It ran while the final
local commit was being created; its packaging test compared two different HEAD
values. Rerunning that packaging test with a stable HEAD passed (1 passed).
The remaining five failures reproduce on unchanged base c58f018a:

- test_bounded_model_transport::test_parent_process_death_terminates_transport_worker
- test_security_harden_wave3::test_ssrf_https_sni_stays_original_hostname_when_dns_rebinds
- test_security_harden_wave3::test_ssrf_redirect_hop_revalidates_and_rebinds
- test_security_harden_wave3::test_ssrf_redirect_from_pinned_public_to_metadata_is_rejected
- test_v224_console_retrieval_requirements_split::test_v224_console_requirements_exclude_sklearn_stack

The last failure rejects telemetry dependencies already introduced by PR #613.
The transport/security failures remain unresolved in this executor; no claim that
they are harmless or production-safe is made. They were not changed as part of
this issue. Later added browser/redaction tests were verified in the 38-check
focused run; the broad run is not a green final-commit proof.

## Gate

Sufficient for a draft PR and code review of this diagnostic slice. Not a merge,
deployment, full-suite or end-to-end publication GO. Reconcile the base-branch
failures, run remote CI, then verify the reviewed deployment's actual Azure
receipt and a representative section-opening incident. Platform observations in
this export are operator-supplied and independently timed; they are not an atomic
snapshot or an established cause.
