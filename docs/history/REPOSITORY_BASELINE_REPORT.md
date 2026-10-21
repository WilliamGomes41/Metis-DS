# Repository Baseline Report

**Date:** 2026-08-20
**Application version:** 0.1.0
**Branch:** `main`

## Purpose

Establish a permanent Git-ready baseline for V&VN Data Services before connecting a remote GitHub repository and starting Azure deployment work.

## Baseline controls

- Python package metadata present in `pyproject.toml`.
- Runtime and development dependencies pinned in lock files.
- Git ignore policy excludes caches, virtual environments, local runtime databases, secrets, canonical source binaries and returned reviewer workbooks.
- Repository preflight blocks unsafe binary/secret patterns and non-empty real tenant configuration.
- GitHub Actions CI runs on Python 3.12 and 3.13.
- CI executes repository preflight, compile check and full pytest regression suite.
- Pull request safety template added.
- Contribution, repository and security conventions documented.
- `main` is the baseline branch.

## Verification

At baseline creation:

- repository preflight: PASS
- Python compile check: PASS
- regression suite: 105/105 PASS
- `config/tenants.v1.json`: empty tenant registry
- runtime SQLite state: ignored
- human review return directory: ignored

## Transitional issue

Historical pilot output artifacts are still source controlled because several existing tests depend on them. New runtime data must not create additional source-controlled dependencies. A later repository cleanup should move deterministic test fixtures into `data/fixtures/` and make `output/` fully disposable.

## Remote next step

Create/connect a private GitHub repository named `vvn-data-services`, push `main`, enable branch protection requiring CI, and then use that repository as the deployment source for Azure DEV.
