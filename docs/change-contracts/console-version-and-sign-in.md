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
