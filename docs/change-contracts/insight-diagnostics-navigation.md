# Diagnostics in Inzicht

Change class: B
Promise: Diagnostics, checks, report history and evidence downloads are reached through Inzicht; task pages retain actionable status and one document-specific diagnosis link.
Proof: Navigate from a completed/blocked source to its Inzicht diagnosis, verify authorized processing/passage/evidence views and downloads, legacy redirects with query context, and absence of diagnostic panels on task/configuration pages.
Touches lifecycle invariants: no
Rewrite risk: none

This conversation explicitly authorizes implementation; no GitHub implementation issue was assigned. The direct user instruction governs this repository-only change.

## Existing mechanism and boundary

`create_console_app` installs source selection, Inzicht, quality and comparison routes; `console_asgi.build_app` also installs publication UI and review signals. `insight_v1` owns the shared diagnostic tabs and document dashboard. Existing processing status, source-selection authorization, quality_view/report store, passage diagnostics, evidence collectors, and comparison commands remain the owners. HTML renderers and compatibility GET redirects move; command semantics and persisted state do not.

The new document diagnosis reads `processing_status` under its existing authorization. Passage diagnostics, review burden and passage exports remain limited to named reviewers with the reviewer role. Source trace, blockage and publication evidence retain their existing independent authorization. Publishers can reach their existing publication-evidence function through the document dashboard without receiving processing details, passage counts or passage exports. Researcher access to processing diagnosis does not grant passage-export access. Quality reports retain their cohort, report identity and history. Recovery authorization remains the existing kernel command; only its return URL changes.

Console-local state is disposable tab, view, filter and document selection. There is no new durable state, lifecycle or authority. Existing quality/comparison/check actions retain their current writes and rules. No lifecycle, publication, review, source identity, or storage contract changes.

## Presentation changes

- Inzicht Documenten links to one diagnosis: Verwerking, Passages en brondekking, Bewijs en downloads.
- Kwaliteit shows graphs or the existing table/history within the same tab.
- Checks and review signals use Inzicht addresses; comparison GETs move, POST commands remain compatible.
- Configuration pages contain configuration only. Work pages show necessary task status and one diagnosis link, not diagnostic panels/download menus.
- Retired GET addresses redirect to their canonical destination with document, attempt, format, report, and filters preserved. Downloads retain content, filenames and authorization.

## Verification and rollback

Verify the above for an assigned reviewer, a researcher, a publisher, an outsider reviewer and an anonymous caller; verify evidence scope and no mutation from navigation. Check comparison actions, report history and redirects.

The workspace sandbox forbids sending on local socketpairs (`PermissionError: Operation not permitted`), which stalls asyncio's thread wakeups for both TestClient and an asynchronous ASGI transport. HTTP tests were therefore run with a temporary runner outside the repository that schedules an asyncio loop timer; it changes neither application/test assertions nor route/backend implementations. This exercised the installed ASGI middleware, redirects, login and domain methods, not just direct render calls. CI can run the same tests normally without this environment-specific timer.

Rollback is a code revert; no data migration is required. Do not remove source context, review obligations, publication blockers, retained evidence or role checks as navigation cleanup.

## Local verification, 2026-10-19

- Targeted HTTP/domain regression run across 26 affected test files: **294 passed, 36 skipped**. This includes the installed application, task-to-diagnosis navigation, reviewer/researcher/publisher separation, evidence exports, compatibility redirects, quality history, comparison commands, source-read reuse and unchanged domain objects/revisions/ledger during navigation. A full-suite run was subsequently attempted with a 180-second limit: it did not complete, and failures were observed before timeout. This is not a full-suite pass; the PR remains draft for CI/review.
- Repository preflight, release-control preflight against `origin/main`, architecture boundary checks, Python compilation, JavaScript syntax validation and `git diff --check`: **PASS**.
- The HTTP run used the temporary asyncio timer described above. There is no production deployment or live browser acceptance claim.
- Publication is through a dedicated review branch and pull request. No merge or deployment is part of this change.

Review follow-up: Bronselectie keeps "Poging technisch geslaagd / Volledige bronverwerking" as task status, because a technically successful partial attempt is the reason to resume. The diagnosis link is shown only to accounts that can open the diagnosis. The publisher document list requires a current publisher role. Characterization goldens were re-recorded for the intended navigation changes only.

The PR is based on the current GitHub main tree. The upstream incomplete-formation guidance is retained, and its new unverified-PDF-page message is moved into the central Inzicht diagnosis instead of being discarded with the retired page.
