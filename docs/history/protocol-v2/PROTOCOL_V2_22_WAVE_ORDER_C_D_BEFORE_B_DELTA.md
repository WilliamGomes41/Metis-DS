# V&VN Data Services Protocol v2.22 — Wave-order C then D then ZIP then B

**Status:** Approved for project use  
**Protocol delta version:** 2.22.0  
**Approval date:** 2026-09-03  
**Approved by:** Project owner  
**Extends:** Protocol v2.21.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (next-implementation order after wave A; isolated test/release; recoverability; ZIP does not open publication)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.22 records the owner-approved lock of 2026-09-03 (William Gomes). After wave A, do C and D first; then he will ingest a document; then one Cloud Shell ZIP from the PR #82 line. He asked if that has problems. Metis locked this safe reading:

**Bounded supersession of Protocol v2.21 §3 order A then B then C then D, for next-implementation order only.** Waves themselves unchanged.

Live baseline on `main` before this delta is Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Wave A is already in code on `main` `512ffa5026d06ff804434ddf4d07a08a36c02305` (PR #85). Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0 and this delta jointly form normative baseline v2.22.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes, Protocol v2.15 ingest-date/version, Protocol v2.16 one-door / stacks / compact-rows / stamps / tiny-objects, Protocol v2.17 slogan / help / Onderwerp / bronpassage-prose / chrome / stamp-UI / relation-checkbox rules, Protocol v2.18 once-only card sentence / trailing-clause / identical-`clean_text` rules, Protocol v2.19 review duty / queue presentation, Protocol v2.20 every-guideline law / unpublished-snapshot delete, or Protocol v2.21 wave A / wave B / wave C / wave D **definitions** (those stay in force). It MAPS, and does NOT rewrite, existing law. Historical v2.21 wave definitions remain law except the A-B-C-D next-impl order superseded here. Protocol v2.16–v2.18 already forbid tiny objects, stamp-as-heading/object, truncated/trailing clauses, chrome objects, and identical `clean_text`. Protocol v2.19 is duty-queue. Protocol v2.20 unpublished-delete remains on main, not a fifth wave. Protocol v2.21 wave A is already on `main` `512ffa5026d06ff804434ddf4d07a08a36c02305`. It does NOT reopen four-eyes or publish as C5. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page, paragraph, stamp, strength, GRADE, chrome, “light/heavy” review, wave, splitter, or reject. This delta’s bar is the next-implementation order after wave A (C then D then one controlled ZIP then B), not a new object type.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17), all Protocol v2.12 type/review/projection rules, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded by Protocol v2.20), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules, all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, all Protocol v2.19 review-duty / queue-presentation rules, all Protocol v2.20 every-guideline-law / unpublished-snapshot-delete rules, and all Protocol v2.21 wave-definition / G2-evidence / PR-#82 / recoverability rules remain in force, except the next-implementation order A then B then C then D in Protocol v2.21 §3 (and the matching next-impl sentences in Protocol v2.21 §§1, 6, 7, 9 and 11) superseded in sections 3–8 and 9. This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.21 files except index/conflict pointers. MUST NOT implement C/D in this PR. Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete, or wave A/B/C/D definitions except as already required.

This delta is a **scoped supersession** of any reading that (1) the next implementation after wave A is wave B, G2 evidence/smoke, Azure ZIP of v2.20, Cloud Shell now, or G2 activation; (2) a Cloud Shell / production ZIP MAY be taken from the current PR #82 line before waves C and D are finished on a controlled SHA; (3) that ZIP MAY be git-archive-only or a live-URL ingest; (4) ingest of a new freeze MAY happen before that ZIP; (5) G2 status MAY depend on a stale static JSON field or an app-setting being present; or (6) PR #82 MAY be activated before the four known faults are fixed AND Azure test App Service `vvn-metis-console-test` exists. Where this delta and those readings conflict, this delta governs. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain (stamp words as Koppen; 2008 Inhoud cards). Those sentences are live evidence of fails, not the product identity. PROTOCOL.md is every-guideline law, not Continentie-only (Protocol v2.20). Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.21 §3 and §9 set the next implementation as wave A only, then B, then C, then D. Wave A is already in code on `main` `512ffa5026d06ff804434ddf4d07a08a36c02305`. Where this delta and Protocol v2.21 conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/repo for wave C (finish PR #82, do not activate) AND wave D (backup/restore + deploy-persistence test), same kernel/repo, no G2 PASS, no Blob grant. Then stop for William Cloud Shell ZIP of that SHA, then ingest. Wave B (G2 evidence/smoke) AFTER that ZIP. G2 still BLOCKED; `publish()` still G2-BLOCKED. ZIP does not open publication. Protocol v2.14 is still not written and is still not the next step. v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation, v2.20 every-guideline law / unpublished-snapshot delete and v2.21 wave definitions remain required law, except the bounded supersessions in this file.

G2-readiness (PR #69) already pinned `azure-identity==1.25.3` / `azure-storage-blob==12.30.1` and a report-only preflight. G2 is still BLOCKED. `publish()` remains G2-BLOCKED. RBAC Storage Blob Data Contributor on `aidataservice/canonical-sources` for the `vvn-metis-console` managed identity is external. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS.

PR #82 (`ci: isolated test deploy + manual production`) is OPEN and MUST NOT be activated until the four faults are fixed AND Azure test App Service `vvn-metis-console-test` exists. MUST NOT activate deploy-test/deploy-production until Azure test App Service `vvn-metis-console-test` exists. Merge to `main` MUST NOT auto-deploy to a missing test app. This protocol MUST NOT start Azure test app in this protocol PR. MUST NOT create or activate that test App Service.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9, v2.10, v2.11, v2.12, v2.13, v2.15, v2.16, v2.17, v2.18, v2.19, v2.20 and v2.21 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. The v2.10 console follow-up now exists in code. The v2.11 ingest lock, the v2.12 kernel, the v2.13 kernel, the two-column review card, the v2.15 ingest-date / ingest-version / heading-proposal / review-list-snippet / type-lane wave, the v2.16 one-door / stacks / compact-rows / stamps / tiny-objects wave, the v2.17 researcher-surface wave, the v2.18 extract+card wave, the v2.19 queue/duty wave, the v2.20 unpublished-delete wave and the v2.21 wave A splitter/reject wave now exist in code. Every rule in Protocol v2.6.0 through Protocol v2.21.0 remains mandatory as already written in Protocol v2.21 §2, except the next-implementation order A then B then C then D superseded here.

Wave A definitions in Protocol v2.21 §4 remain law. Wave B definitions in Protocol v2.21 §5 remain law. Wave C definitions in Protocol v2.21 §6 remain law. Wave D definitions in Protocol v2.21 §7 remain law. This delta does not rewrite those wave bodies. It changes only the next-implementation order after A, and records the owner-locked ZIP/ingest timing plus the named test-app and `--clean true` proofs that belong to that order.

v2.20 unpublished-delete remains on main, not a fifth wave.

## 3. Next-implementation order after A: C then D then ZIP then B

Owner 2026-09-03: after wave A, do C and D first; then he will ingest a document; then one Cloud Shell ZIP from the PR #82 line. He asked if that has problems. This is the safe reading.

New order after A (already in code on main):

1. Wave C: finish PR #82 faults (packaging via bash or executable; ZIP MUST be fully deployable with dependencies — git-archive-only is not enough; per-env storage via app settings no secrets in Git; separate test vs production deploy identities). MUST NOT activate deploy-test/deploy-production until Azure test App Service `vvn-metis-console-test` exists. Merge to `main` MUST NOT auto-deploy to a missing test app.
2. Wave D: `/home/data` inventory, export/restore, proof that `--clean true` wipes wwwroot and MUST NOT delete runtime data.
3. THEN one Cloud Shell / production ZIP of that controlled SHA (A+C+D), not a live-URL ingest. Ingest of a new freeze MUST be after that ZIP, not before (live still runs pre-wave-A extract until ZIP).
4. Wave B (G2 evidence/smoke) AFTER that ZIP. G2 still BLOCKED; `publish()` still G2-BLOCKED. ZIP does not open publication.

This supersedes Protocol v2.21 §3 order A then B then C then D, for next-implementation order only. Waves themselves unchanged.

Cloud Shell / production ZIP stay off until waves C and D are on the same controlled SHA as wave A. A ZIP of current `main` (A only, or the unfinished PR #82 line) is not that ZIP. git-archive-only is not enough.

## 4. Wave C — finish PR #82; do not activate (first after A)

Wave C is the first implementation after this protocol merges. Wave C definitions in Protocol v2.21 §6 remain law. This section MAPS that law into the new next-impl slot. It does not rewrite Protocol v2.21.

Finish PR #82. Do not activate until Azure test App Service `vvn-metis-console-test` exists.

- Invoke the packaging script via bash or make it executable.
- The Azure ZIP MUST build dependencies or the artifact MUST be fully deployable with dependencies. git-archive-only is not enough; live Oryx-during-deploy caused HTTP_504 on B1.
- Storage account / container per environment via safe app settings; no secrets in Git.
- Separate deployment identities: the test identity MAY only deploy to test; the production identity MAY only deploy to production.
- Production is manual: only a full SHA already on `main`, after protection / approval.
- MUST NOT deploy runtime data from Git.
- MUST NOT overwrite `/home/data`.
- MUST NOT activate deploy-test/deploy-production until Azure test App Service `vvn-metis-console-test` exists.
- Merge to `main` MUST NOT auto-deploy to a missing test app. Merge to `main` MAY deploy only to test, and only after that named test app exists; production requires an explicit release action of the exact same tested SHA.

Known PR #82 faults to fix:

1. `create_azure_deploy_package.sh` invoked without bash and may not be executable;
2. package is git archive HEAD only, no dependencies;
3. workflows do not configure per-environment storage;
4. one Entra app is not enough if it can deploy to both — identities MUST be scoped so test cannot production and production cannot test.

MUST NOT start Azure test app in this protocol PR. MUST NOT create or activate a test App Service in this protocol PR. MUST NOT implement C/D in this PR. PR #82 is OPEN and MUST NOT be activated until those four faults are fixed AND `vvn-metis-console-test` exists.

## 5. Wave D — backup/recoverability and deploy-persistence (with C; before ZIP)

Wave D is with wave C, before the Cloud Shell ZIP. Wave D definitions in Protocol v2.21 §7 remain law. This section MAPS that law into the new next-impl slot and records the `--clean true` proof. It does not rewrite Protocol v2.21.

Inventory of `/home/data/metis-console` MUST include:

- accounts / roles;
- document snapshots;
- review decisions and audit ledger;
- canonical objects;
- derived projections.

MUST have an export / backup procedure; a controlled restore to a clean environment; an integrity check after restore; and a test proving a deployment does not delete existing runtime data.

MUST proof that `--clean true` wipes wwwroot and MUST NOT delete runtime data. Runtime data lives under `/home/data` (including `/home/data/metis-console`). A clean deploy of `wwwroot` MUST NOT SSH-wipe `/home/data` and MUST NOT treat SSH or a wipe of `/home/data` as the product path.

No large database migration. MUST document the migration boundary: a managed database becomes required before multiple App Service instances or concurrent multi-reviewer writes.

MUST NOT implement C/D in this PR. MUST NOT hide fragments. MUST NOT SSH-wipe `/home/data`.

## 6. One Cloud Shell / production ZIP of the controlled A+C+D SHA

THEN one Cloud Shell / production ZIP of that controlled SHA (A+C+D), not a live-URL ingest.

- The ZIP is William Cloud Shell ZIP of the SHA that contains wave A plus finished wave C plus finished wave D.
- The ZIP MUST be fully deployable with dependencies. git-archive-only is not enough.
- That ZIP is not a live-URL ingest. Live URL-HTML remains rejected at ingest (Protocol v2.11).
- Ingest of a new freeze MUST be after that ZIP, not before.
- Live still runs pre-wave-A extract until ZIP. The running console remains the pre-wave-A extract until that controlled ZIP is deployed.
- ZIP does not open publication. G2 still BLOCKED. `publish()` still G2-BLOCKED.
- Wave B is AFTER that ZIP. The ZIP does not start wave B and does not grant Blob.

Owner asked if a Cloud Shell ZIP from the current PR #82 line has problems. Yes, if taken before C and D are finished on a controlled SHA, or if the artifact is git-archive-only. This delta is the safe reading: finish C and D first, then one ZIP of that SHA.

## 7. Wave B — G2 status evidence AFTER the ZIP

Wave B (G2 evidence/smoke) AFTER that ZIP. Wave B definitions in Protocol v2.21 §5 remain law. G2 still BLOCKED. `publish()` still G2-BLOCKED. ZIP does not open publication.

G2 status MUST NOT depend on a stale static JSON field.

Read-only preflight MUST show:

- Blob container reachable;
- managed identity usable;
- required Blob role present or access actually proven;
- container matches the active environment;
- a source can be stored and read back byte-identical.

Controlled SHA-256 smoke. Machine-readable evidence MUST include timestamp, environment, container, SHA-256, and outcome.

G2 PASS only after a successful controlled test; else BLOCKED. The publication gate MUST NOT open because an app-setting is present.

Do not claim G2 PASS in this protocol. MUST NOT claim G2 PASS. RBAC grant remains external. `publish()` remains G2-BLOCKED. G2-readiness (PR #69) already pinned `azure-identity` / `azure-storage-blob` and a report-only preflight; that is readiness, not PASS.

MUST NOT start Azure test app in this protocol PR. MUST NOT start Azure in this protocol PR. No Blob grant in the C+D implementation that follows this protocol.

## 8. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API, Azure or `publish()`. This delta does not implement wave C, wave D, the ZIP, G2 evidence, pipeline or backup.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged for type-confirm and high-risk. Protocol v2.14 unchanged (not written, not next). Azure unchanged in this protocol PR (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication. Do not claim G2 PASS in this protocol.

The following rules remain mandatory and are not relaxed by this delta:

- Canonical source binaries (HTML, PDF and other official source bytes) MUST NOT be committed to Git.
- Secrets, API keys, passwords, certificates and private keys MUST NOT be committed.
- `config/tenants.v1.json` MUST remain an empty tenant list in the repository.
- Confidential review artefacts MUST NOT be committed.
- Runtime databases and local runtime state MUST NOT be committed.
- GD-03 remains ESTABLISHED as written. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.
- Holdout B MUST NOT be tuned from console analytics or any other operational metric.
- AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT count as required reviewers, MUST NOT approve, and MUST NOT publish.

`.gitignore` already covers the source, secret, tenant, review and runtime classes and MUST be kept.

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. No huisstyle-bar-only tweaks without the bar in sections 3–7.

## 9. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`. MUST NOT implement C/D in this PR. MUST NOT start Azure test app in this protocol PR. MUST NOT rewrite v2.16–v2.21 files except index/conflict pointers.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before waves C and D finish PR #82 faults and the `/home/data` backup/restore plus `--clean true` proof.

Where this delta and Protocol v2.21 conflict on which implementation is next, this delta governs. Wave A is already in code on `main` `512ffa5026d06ff804434ddf4d07a08a36c02305`. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/repo for wave C AND wave D, then stop:

1. Wave C: finish PR #82 faults (packaging via bash or executable; ZIP MUST be fully deployable with dependencies — git-archive-only is not enough; per-env storage via app settings; no secrets in Git; separate test vs production deploy identities). MUST NOT activate deploy-test/deploy-production until Azure test App Service `vvn-metis-console-test` exists. Merge to `main` MUST NOT auto-deploy to a missing test app.
2. Wave D: `/home/data` inventory, export/restore, proof that `--clean true` wipes wwwroot and MUST NOT delete runtime data.
3. Then stop for William Cloud Shell ZIP of that controlled SHA (A+C+D), not a live-URL ingest. Ingest of a new freeze MUST be after that ZIP, not before (live still runs pre-wave-A extract until ZIP).
4. Wave B (G2 evidence/smoke) AFTER that ZIP. G2 still BLOCKED; `publish()` still G2-BLOCKED. ZIP does not open publication.

No G2 PASS. No Blob grant. Do not start Azure in this protocol PR. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation, v2.20 every-guideline law / unpublished-snapshot delete and v2.21 wave definitions remain required law, except the bounded supersessions in this file. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. The 2026-08-29 two-column review card is already in code and is not the next implementation after this delta. The v2.15 ingest/lanes wave is already in code and is not the next implementation after this delta. The v2.16 door/stacks/stamps wave is already in code and is not the next implementation after this delta. The v2.17 researcher-surface wave is already in code and is not the next implementation after this delta. The v2.18 extract+card wave is already in code and is not the next implementation after this delta. The v2.19 queue/duty wave is already in code and is not the next implementation after this delta. The v2.20 unpublished-delete wave is already in code and is not the next implementation after this delta. The v2.21 wave A splitter/reject wave is already in code and is not the next implementation after this delta.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: implementing console/extract/Azure, implementing C/D, merging, G2 PASS, Protocol v2.14, LLM, nurse UI, SSH wipe, hiding fragments without extract, treating Metis / Implementation engineer / Auditor as GD-03 reviewers, Vercel/Neon, new object types, GRADE English labels, relation-graph editor, huisstyle-bar-only tweaks without the bar in sections 3–7, `publish()` PASS, Blob, managed identity, app settings, rewriting freeze bytes, auto-confirming types, auto-promoting ordinary text to `recommendation`, a researcher “zwaar/licht” or “snel/langzaam” switch, reopening serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete except as already required, rewriting v2.16–v2.21 files except index/conflict pointers, creating or activating a test App Service, starting Azure test app in this protocol PR, claiming G2 PASS, taking a Cloud Shell ZIP before C and D are on the controlled SHA, live-URL ingest, ingest of a new freeze before that ZIP.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 10. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (next-implementation order after wave A; isolated test/release; recoverability; ZIP does not open publication). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later implementation of wave C (finish PR #82; do not activate), wave D (backup/restore + `--clean true` proof), the Cloud Shell ZIP, or wave B remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 11. Gates and approval effect

Approval of v2.22 establishes that the owner locked a bounded supersession of Protocol v2.21 §3 order A then B then C then D, for next-implementation order only; that waves themselves unchanged; that historical v2.21 wave definitions remain law except the A-B-C-D next-impl order superseded here; that wave A is already in code on `main` `512ffa5026d06ff804434ddf4d07a08a36c02305`; that the new order after A is wave C then wave D then one Cloud Shell / production ZIP of that controlled SHA (A+C+D) then wave B; that wave C MUST finish PR #82 faults (packaging via bash or executable; ZIP MUST be fully deployable with dependencies; git-archive-only is not enough; per-env storage via app settings; no secrets in Git; separate test vs production deploy identities); that MUST NOT activate deploy-test/deploy-production until Azure test App Service `vvn-metis-console-test` exists; that merge to `main` MUST NOT auto-deploy to a missing test app; that wave D MUST inventory `/home/data`, export/restore, and proof that `--clean true` wipes wwwroot and MUST NOT delete runtime data; that THEN one Cloud Shell / production ZIP of that controlled SHA (A+C+D), not a live-URL ingest; that ingest of a new freeze MUST be after that ZIP, not before; that live still runs pre-wave-A extract until ZIP; that wave B (G2 evidence/smoke) is AFTER that ZIP; that G2 still BLOCKED; that `publish()` still G2-BLOCKED; that ZIP does not open publication; that this protocol MUST NOT start Azure test app in this protocol PR; that this protocol MUST NOT claim G2 PASS; that MUST NOT hide fragments; that MUST NOT SSH-wipe `/home/data`; that MUST NOT rewrite v2.16–v2.21 files except index/conflict pointers; that MUST NOT implement C/D in this PR; that v2.20 unpublished-delete remains on main, not a fifth wave; that the next implementation after this protocol merges MUST be Implementation engineer wave C (finish #82, do not activate) AND wave D (backup/restore + deploy-persistence test), same kernel/repo, no G2 PASS, no Blob grant; then stop for William Cloud Shell ZIP of that SHA, then ingest; that this delta MAPS, and does NOT rewrite, existing law; that Protocol v2.16–v2.18 already forbid tiny objects, stamp-as-heading/object, truncated/trailing clauses, chrome objects, and identical `clean_text`; that Protocol v2.19 is duty-queue; that `PROTOCOL.md` is every-guideline law, not Continentie-only (Protocol v2.20); that Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain; that G2-readiness (PR #69) already pinned `azure-identity` / `azure-storage-blob` and a report-only preflight; that RBAC Storage Blob Data Contributor on `aidataservice/canonical-sources` for `vvn-metis-console` is external; that PR #82 is OPEN and MUST NOT be activated until the four faults are fixed AND `vvn-metis-console-test` exists; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged: only confirmed `recommendation` MAY `supported` / handelingsadvies; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; `publish()` remains G2-BLOCKED; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- implement wave C or wave D in this PR;
- convert G2 to PASS;
- claim G2 PASS in this protocol;
- implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob;
- start Azure test app in this protocol PR;
- create or activate a test App Service in this protocol PR;
- activate deploy-test/deploy-production before `vvn-metis-console-test` exists;
- auto-deploy a merge to `main` toward a missing test app;
- activate PR #82 before the four faults are fixed AND `vvn-metis-console-test` exists;
- take a Cloud Shell ZIP of the unfinished PR #82 line, or of A-only `main`, as the controlled A+C+D ZIP;
- treat a git-archive-only artifact as that ZIP;
- treat that ZIP as a live-URL ingest;
- ingest a new freeze before that ZIP;
- treat the ZIP as opening publication or as wave B;
- skip durable immutable storage;
- staff named reviewers;
- treat Metis, the Implementation engineer or the Auditor as GD-03 reviewers;
- write Protocol v2.14, or treat ingest date as `valid_from` / `valid_until`;
- reopen four-eyes or publish as C5;
- add a researcher “zwaar/licht” or “snel/langzaam” control;
- let the machine decide that something is “light enough to serve”;
- let Koppen heading accept bypass four-eyes if the object is high-risk or is reclassified onto a high-risk type;
- auto-confirm types;
- auto-promote ordinary text to `recommendation`;
- treat remaining unclassified as equal one-by-one researcher duty of thousands of cards;
- treat 2008 Inhoud cards as an acceptable workload;
- make `definition` / `explanation` the MVP researcher 2000-card duty for handelingsadvies;
- add page, paragraph, stamp, strength, GRADE, chrome, light/heavy, splitter, or reject as stored object types;
- invent GRADE English labels on this screen;
- keep two doors **Openen** plus **Reviewen** that both lead to object lists;
- present a page of thousands of identical `unclassified` titles, or use the type name (`unclassified`) or a kernel document id as the review-list row title;
- stretch status / checkbox / text into disconnected columns across the viewport;
- treat DOEN/OVERWEEG/NIET DOEN as Koppen rows or standalone knowledge objects;
- propose `heading` for DOEN/OVERWEEG/NIET DOEN even if the freeze wraps them in heading tags;
- emit number-only, stamp-only, or truncated-sentence objects;
- emit a trailing clause (“Eventueel …”, “Bijvoorbeeld …”, “Zoals …”) as its own knowledge object;
- emit identical `clean_text` as a second knowledge object from the same freeze because the HTML repeats samenvatting/module text;
- treat `1.1 Inleiding` and `2. Inleiding` as identical strings;
- treat “Inleiding” as chrome;
- emit kennisplatform chrome (Home, Richtlijnen, Meedenken, Kennisinstituut V&VN, Tools, Veelgestelde vragen, duplicated nav) as knowledge objects or Koppen;
- drop short real definitions or official headings;
- fuse condition into recommendation, or reopen that Protocol v2.13 forbid;
- lie in the UI by hiding stored fragments without a new extract;
- hide selected objects inside a freeze that stays in Review;
- delete a published projection or anything that has been published;
- treat SSH or a wipe of `/home/data` as the product path;
- overwrite `/home/data` on deploy;
- let `--clean true` delete runtime data;
- deploy runtime data from Git;
- strip historical Continentie evidence sentences from Protocol v2.16–v2.19;
- make the next freeze have to be Continentie;
- treat `PROTOCOL.md` as Continentie-only law;
- treat Protocol v2.20 unpublished-delete as a fifth wave;
- rewrite Protocol v2.16–v2.21 files except index/conflict pointers;
- silently rewrite published objects (there is no published projection);
- rewrite Protocol v2.13 split rules;
- reopen Protocol v2.11 freeze/locator except researcher-visible prose derived from those locators;
- reserialize or re-save freeze bytes, or bind locators to reserialized HTML;
- dump raw HTML tag soup, CSS class names or kennisplatform markup as the researcher bronpassage;
- reopen Protocol v2.12 types/projection, or Protocol v2.13 atomic objects/relations/four-eyes;
- reopen Protocol v2.15 ingest date, ingest version, or type-based lanes except as already superseded by v2.16 stamps, the v2.17 chrome rule, and the v2.19 slow-lane-unclassified-as-equal-one-object-duty reading;
- reopen Protocol v2.16 one-door, two-stack, compact-row, stamp or tiny-object rules except as already required;
- reopen Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation or compact-relation-checkbox rules except as already required;
- reopen Protocol v2.18 once-only card sentence, grammatical-continuation-split or identical-`clean_text` rules except as already required;
- reopen Protocol v2.19 review-duty or queue-presentation rules except as already required;
- reopen Protocol v2.20 every-guideline-law or unpublished-snapshot-delete rules except as already required;
- reopen Protocol v2.21 wave A / wave B / wave C / wave D definitions except the next-implementation order A then B then C then D superseded here;
- require or allow “wat een EPD MAG zeggen” or any EPD MAG slogan as Review lead copy;
- claim a single subscriber class on researcher pages;
- allow HELP_ONCE via-negativa on researcher rooms, including collapsed “Over deze console”;
- prefill Onderwerp / family on a fresh new ingest;
- expand empty-Onderwerp to class default;
- invent a locator scheme;
- treat machine classification as published type, or serve `unclassified` as `supported`;
- give advice-weight to heading, or serve headings as handelingsadvies;
- replace the v2.12 publish tuple, or let envelope `review_passes` authorize publish;
- let the uploader be the only required reviewer for type-confirm, or let AI, Grok Bot, Metis, the Implementation engineer or the Auditor count as required reviewers;
- authorize live URL-HTML, LLM in the core API, nurse-facing console, chat, hospital protocols, patient data, Vercel/Neon, or treating Azure as the knowledge model;
- start Azure, Vercel, Neon or an LLM vendor in this protocol PR;
- implement Blob, managed identity, or huisstyle-bar-only tweaks without the bar in sections 3–7;
- let G2 status depend on a stale static JSON field;
- open the publication gate because an app-setting is present;
- treat capture as publication;
- reopen or alter GD-03;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- add a care-app frontend, chatbot, EPD/ECD-UI or public website;
- put chat in the console;
- design the console for nurses;
- open the role set or allow operators to invent new role types, object types or relation types;
- allow open registration or shared login;
- store hospital protocols, adoption lists or patient data;
- authorize source binaries, secrets, confidential review artefacts or the official stylesheet PDF in Git;
- silently add a new quality metric as a protocol gate;
- authorize a mockup, Azure ZIP of v2.20, Cloud Shell now, Vercel or Neon as the next implementation;
- treat Protocol v2.14 as this file or as the next step.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
