# Recognizable console version and direct sign-in

Implementation issue: #882. Base: `8e785cdbcf41fb1947198726d75ce467bf59f0ca`.

Change class: B
Promise: Users see the running package's product version before and after sign-in, can read its public release notes, and start Microsoft sign-in with one Metis button.
Proof: tests/test_console_release_v1.py, tests/test_wave_c_deploy_packaging.py, tests/test_console_entra_v1.py, tests/test_console_entra_auth_evidence.py, tests/test_login_light_theme_v1.py.
Touches lifecycle invariants: no
Rewrite risk: none

Implementation authorized directly by the user in chat after repository research
and the proposal: "Start implementatie". This is the bounded implementation task;
no production deployment or merge is part of it.

## Ownership and existing path

The build owns product release metadata. The console only projects it; it creates
no durable domain state. The existing Entra/SQL identity boundary continues to
own flows, account identity, roles, sessions, atomic sign-in and replay protection.
Document/review/publication identities and lifecycle are unchanged.

Before: `/` -> button -> `/login` -> button -> `/auth/microsoft`.
After: `/` and `/login` render the same sign-in form; the Microsoft button goes
straight to `/auth/microsoft`. The local-auth form remains available only in local
mode. The existing callback, return target validation, PKCE/state/nonce, rate
limiting, session rotation and authorization are unchanged.

## Release contract

- Format: `generation.release.build`. Generation stays 1 until an explicit
  product decision for the Athena integration. Release is maintained in
  `config/console_release.json` with public, plain-text user changes.
- Build is the first-parent commit count for the exact packaged commit, using
  complete Git history. It is a stable build sequence, not a deployment attempt
  counter or semantic-version patch promise. Rebuilding the same commit through
  ZIP/container produces the same number; redeploying/rolling back a package
  retains that package's version and notes. Normal main advancement increments
  the sequence. Rewritten history is unsupported.
- Both build routes stamp `config/console_build.json` next to the existing
  deployed-commit marker. Runtime accepts the version only when it matches the
  packaged release definition and commit marker. No Git/network access at runtime.
  Historical source without the version-projection module retains the old build
  path. New code with a missing release definition fails the build. No fabricated
  version or notes are retroactively assigned to historical code.
- A source checkout is explicitly a development version; absent/inconsistent
  deployment metadata displays version unavailable, never a fabricated number.
- `/health` retains its existing technical fields and adds `product_version`.
  Commit-based diagnostics and historical reports retain their technical identity.
  Human-facing labels distinguish product version from build reference.
- `/wat-is-nieuw` serves only bundled public release information, without session
  renewal, document reads or authentication-flow creation. It is read-only and
  available before login; it adds no other public route.

## Observable proof

Tests cover the real production-composed HTTP application with PostgreSQL:
both public entry points lead directly to Microsoft, release notes are public
without creating flows/sessions, a protected route still redirects to auth,
callback lands on home, and authenticated home shows the same product version.
Existing Entra tests prove rejection/replay/session behavior on unchanged paths.
Build tests exercise stamped metadata without Git at runtime, older-package
identity after source advances (rollback), full-history enforcement and real ZIP
contents. Visual checks cover the merged light sign-in page and release link.

Real Microsoft account selection/MFA remains organization policy and requires
live integration acceptance; local tests do not establish the number of Microsoft
prompts in production.

## Executed verification

Runtime/UI revision: `d5276bef692a1f1f9b2540641e58f71ca562fdfb`;
Python 3.12.14, native PostgreSQL 16.2. The final compatibility correction only
adds the legacy/new-code distinction at both package builders and its shell
regression; it does not change the console, release reader, identity or domain
logic. That correction was checked separately against the final working tree.

- Full suite using the repository's four CI partitions: **6,164 test IDs**,
  **6,122 passed**, **39 optional skips**, **3 established B23 xfails**,
  **zero failures/errors and zero PostgreSQL skips**. The normal CI merge checker
  verified complete, non-overlapping execution of the collected test IDs.
  Longest partition: 707.677 s. No performance improvement is claimed.
- Final build/version/preflight regressions after the compatibility correction:
  **44 passed**, including real ZIP dependency vendoring and the real container
  shell route on local Git fixtures. Legacy source rebuilds; new source missing
  its release definition is rejected. The old failure was reproduced as a
  missing `config/console_release.json` during an actual historical dry-run.
- Final collection: **6,165 test IDs**. Set comparison establishes that the full
  partitioned collection plus the separately passing new legacy-build test is
  exactly the final collection. The extra case has its own passing JUnit record.
- Final release/theme/Raad/safety checks: **32 passed**. Shared-layout and
  stylesheet-cache checks: **10 passed**. Architecture invariants: **6 passed**.
- Characterization: **38 passed** after deliberately updating shared chrome only.
  The existing in-memory mutation still produces exactly **24/27 red cases**,
  validated by `tests/characterization/check_evidence.py`; no domain output was
  normalized away or regenerated from unreviewed output.
- Actual PostgreSQL + Chromium Raad/deploy-check and view-check regressions:
  **2 passed**. Separate desktop/mobile browser inspection of captured real
  production-composed responses established direct sign-in navigation, public
  notes without authentication, light sign-in under dark preference, no
  horizontal overflow and no script errors. The displayed numeric version in
  that visual fixture was simulated, not an observed production version.
- Container build context dry-run passed on a local main fixture; no Azure/image
  build was performed. Repository/release-control preflights, compilation,
  architecture boundaries, PR change-contract validation and whitespace passed.
- Bounded surface self-review: no blocking finding after preserving the shared
  CSS baseline and restoring legacy rebuild compatibility. No new runtime
  dependency, database migration, state owner or alternate identity path.

Optional Bend/real Docling/model acceptance and remaining opt-in browser jobs
were not established by the full local suite. Two existing browser jobs were
executed separately as noted above. Hosted CI, real Microsoft prompts and
production acceptance remain separate. No merge or deployment was performed.
