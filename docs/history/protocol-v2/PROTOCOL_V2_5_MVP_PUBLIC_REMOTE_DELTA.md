# V&VN Data Services Protocol v2.5 — MVP Public Remote Exception

**Status:** Approved for project use  
**Protocol delta version:** 2.5.0  
**Approval date:** 2026-08-27  
**Approved by:** Project owner  
**Extends:** Protocol v2.4.0  
**Highest change class:** C5 (repository identity/visibility / supply-chain access)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.5 is a scoped owner-approved exception to Protocol v2.2 §4.1. GitHub branch protection (G1) cannot be enabled on a private repository on the current free personal plan (403: Pro or public required). The project owner therefore permits the authoritative remote `WilliamGomes41/VENVN-DS` to be public during a declared MVP period so that G1 technical protection can be enabled.

Protocol v2.2.0, v2.3.0, v2.4.0 and this delta jointly form normative baseline v2.5.0. This delta is a **scoped supersession** of v2.2 §4.1 ("One private remote repository MUST be designated as the authoritative software repository") for the declared MVP period and repository named below. It does not weaken any other fail-closed requirement. Where this delta and earlier protocol text conflict on repository visibility for that declared period and repository, this delta governs. For all other requirements, the stricter fail-closed requirement applies.

This protocol-only change does not itself change GitHub visibility. Visibility is applied after merge.

## 2. Declared MVP period and repository

The §4.1 private-remote MUST is relaxed **only** for a declared MVP period on `WilliamGomes41/VENVN-DS`.

During that period:

- the authoritative software remote MAY be public;
- `main` remains the default branch and the authoritative code baseline;
- the repository identifier, default branch and hosting account MUST remain recorded.

This exception MUST NOT be treated as a general permission to make any other copy, fork, mirror or future repository public.

## 3. After-MVP restoration

Public hosting is not the production baseline.

After the MVP, a new plan MUST restore private hosting or move the authoritative remote to an organization plan that can protect a private default branch. Until that plan exists, G1 technical protection on a public MVP repository is accepted.

G1 PASS still requires the other G1 controls:

- protected default branch;
- pull-request workflow;
- required CI checks;
- no direct push to `main`;
- clean lockfile installation;
- release and commit traceability.

G1 PASS during the declared MVP period does **not** require the remote to be private.

## 4. Unchanged fail-closed rules

The following rules remain mandatory and are not relaxed by this delta:

- Canonical source binaries (HTML, PDF and other official source bytes) MUST NOT be committed to Git.
- Secrets, API keys, passwords, certificates and private keys MUST NOT be committed.
- `config/tenants.v1.json` MUST remain an empty tenant list in the repository.
- Confidential review artefacts MUST NOT be committed.
- Runtime databases and local runtime state MUST NOT be committed.

`.gitignore` already covers these classes and MUST be kept. Removing those exclusions is a C5 change.

## 5. G1 branch protection after the repository is public

Once the repository is public, G1 branch protection on `main` MUST be enabled with at least:

- required CI checks `test (3.12)` and `test (3.13)`;
- require a pull request before merging;
- no force-push to `main`;
- no deleting `main`.

Metis applies this immediately after this protocol change is merged. This protocol pull request does not wait for that GitHub setting to exist and MUST NOT be treated as G1 PASS.

Until visibility is switched **and** the protection above is on, G1 remains `BLOCKED`.

## 6. Software-artefact visibility during the public MVP

Fixtures, holdouts and already-tracked historical artefacts under `output/` MAY remain in the public MVP repository. They are software artefacts and test evidence, not canonical source binaries.

The project owner accepts that software-artefact visibility for the MVP.

Canonical source HTML/PDF still MUST NOT be committed. A fixture derived from unverified or unpublished source material MUST NOT be described as canonical or publication eligible.

## 7. Security reporting for a public MVP

While the authoritative remote is public, security findings MUST be handled privately:

- use GitHub private vulnerability reporting when available;
- otherwise handle findings privately with the project owner and security/operations reviewers;
- MUST NOT post source bytes, credentials, unpublished knowledge, or exploit details in public issues, pull requests or discussions.

`SECURITY.md` records this reporting path. Public dumping of source bytes, credentials or unpublished knowledge remains prohibited.

## 8. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest applicable class is **C5** (repository identity/visibility / supply-chain access).

Named C5 reviewers are not yet staffed. The project owner approves this delta. Retrospective independent technical and security/operations review remains due, using the same pattern recorded in `HANDOFF.md` for PR #4 and PR #5.

This delta does not invent named reviewers and does not reopen GD-03. GD-03 remains ESTABLISHED as written.

Any later implementation that changes publication eligibility, entitlement, secrets or external access remains separately classified, including at least C5.

## 9. Gates and approval effect

Approval of v2.5 establishes the declared MVP public-remote exception. It does not:

- change GitHub visibility;
- enable branch protection;
- convert G1, G0 Azure DEV or G8 to PASS;
- authorize source binaries, secrets or confidential review artefacts in Git;
- publish a source or knowledge object;
- authorize an external consumer;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- reopen or alter GD-03.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest.
