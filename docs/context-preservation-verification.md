# Context preservation: implementation and verification

Base: `77c028b16618f3441d4955b1edc6a0c1e5026ba3`.
Branch: `fix/context-preservation`. Verification date: 2026-10-09.

## Resulting behavior

The kernel now builds one typed preparation context for ingest, retry and resume.
Source identity is mandatory. A complete, versioned extraction record is written
to the existing workflow envelope before model work. Restart and compatible
retry/resume reuse it; review/readiness readers reuse it after validating its
identity and integrity. Explicit re-extraction remains fresh.

This is additive JSON/JSONB metadata. There is no SQL migration, new job manager,
new command identity or second workflow authority. The existing dispatcher and
durable processing attempt still own scheduling, recovery and final activation.
Decision-tree construction keeps its existing dedicated path.

## Context rules

| Context | Lifetime and owner | Validation |
| --- | --- | --- |
| Source identity | Immutable source snapshot | Snapshot, document, source, hash, version, content kind |
| Attempt and revision | Existing durable attempt and workflow store | Actor, active attempt, revision, deadline, current processing configuration |
| Extracted fragments | Complete derived record in the source envelope | Record hash, fragments hash, producing source, extractor contract |
| Semantic progress | Existing replay checkpoint | Existing open-range and completed-object preservation rules |
| Review and publication | Existing current workflow authority | Re-evaluated; never inferred from cached extraction |
| Reconstructed blocks | One calculation | Existing local reuse only |

## Evidence

The initial restart proof failed with `RESTART_RESUME_EXTRACTED_AGAIN` before the
implementation and passes after it. New local proofs cover provider failure
after durable extraction, restart/retry with extraction forbidden, partial resume
with one open-range model call and unchanged completed object, repeated readers,
corrupt fragments, wrong source identity, incompatible parser, checkpoint write
failure, concurrent writer during paused extraction, explicit fresh extraction,
historical native fallback, and preservation of the complete Docling adapter.

The HTTP extraction proof asserts that neither the store lock nor workflow
transaction is held during extraction. The paused-extraction proof permits a
competing workflow write and rejects the old worker's checkpoint afterwards.
Existing source-selection/resume regression tests cover the surrounding lifecycle
and activation fences.

Latest focused command:

```sh
python -m pytest -q tests/test_context_preservation.py tests/test_pre_review_semantic_v1.py tests/test_availability_repair.py tests/test_source_resume_acceptance.py
```

Result: **60 passed, 29 skipped**. The new test file alone: **10 passed, 7 skipped**.
PostgreSQL parameterizations are skipped because no test database is configured.
They are included in the mandatory native source-processing CI workflow.

Architecture boundary checks, change-contract validation, repository preflight,
API contract compatibility and release-control metadata preflight pass locally.

## Adversarial review and limits

- Checkpoint persistence uses the existing short transaction and commit boundary.
  The prepared in-memory envelope changes only after successful persistence.
- Initial-registration revision normalization is restricted to an ingest attempt
  reserved against an absent revision; retry/resume cannot use that exception.
- A changed envelope/revision, lost authority, obsolete attempt or incompatible
  configuration must fail at checkpoint or at the existing final activation fence.
- Hashes detect accidental corruption; they are not signatures against an attacker
  who can rewrite the database and recompute them.
- A crash before checkpoint commit may repeat extraction. A compatible restart
  after commit reuses it. Derived records do not authorize candidates or publication.
- Native PostgreSQL restart/concurrency acceptance remains outstanding until CI
  runs these tests against the real store. Local green tests do not close that gate.

The initial full suite had five failures: one recovery fixture changed extraction
output for the same immutable source; it now uses consistent source fragments and
forbids re-extraction during recovery. Four unrelated failures also reproduce at
the unchanged base commit:

```text
tests/test_bounded_model_transport.py::test_parent_process_death_terminates_transport_worker
tests/test_security_harden_wave3.py::test_ssrf_https_sni_stays_original_hostname_when_dns_rebinds
tests/test_security_harden_wave3.py::test_ssrf_redirect_hop_revalidates_and_rebinds
tests/test_security_harden_wave3.py::test_ssrf_redirect_from_pinned_public_to_metadata_is_rejected
```

The baseline-only run reports **4 failed**. These failures are not repaired by this
change. Publication, merge, deployment and production acceptance have not occurred.

The final full regression run, with only those four baseline failures explicitly
deselected, reports **3120 passed, 247 skipped, 4 deselected** in 232.47 seconds.
Skipped tests remain unproven in this environment; this is not a fully green
native-storage or production acceptance claim. The focused suite was also rerun
after the initial-registration exception was narrowed.
