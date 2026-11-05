# Knowledge object statechart program plan

Metis treats a knowledge object (KO) as one claim with its context, its supporting evidence and its provenance.
Today the lifecycle of a KO is implicit in nine fields that about forty writers change independently.
This program makes the lifecycle one derived statechart, routes every change through one transition table, and removes the parallel ways of working.
The rule it enforces is one authority per fact and one way to move a KO from Kandidaat to Gepubliceerd.
Reviewers, publishers and the Athena consumer read the same state.
PRs in order are KO-1, KO-2, KO-3, KO-4, KO-5 and KO-6. KO-6 is destructive and runs only on explicit operator approval with a tested backup.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `pstack/skills/poteto-mode/playbooks/autopilot-stack.md`. The operator merges every PR and deploys. KO-2, KO-3 and KO-4 change an interaction and stop at merge-ready for the operator's review. KO-6 additionally stops before execution for the operator's written approval of the data migration.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

Governance in this repository overrides pstack where they differ. Class A with `Rewrite risk: high` per `docs/agents/continuous-development.md` and `docs/agents/lifecycle-vsa.md`. The chart is not a source of truth per `docs/agents/statechart-integration.md`. No PR adds a stored lifecycle status.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on the operator's explicit go.
- [ ] Record the operator's answers to the three product decisions in Appendix C before KO-3 and KO-4 start.
  - [ ] Is supporting evidence mandatory per object type, and does an explicit "niet van toepassing" close it.
  - [ ] Is publication per object or per document (#991).
  - [ ] Is the Athena package derived on read or stored as an aggregate.
- [ ] Read these from trunk at program start. Re-read them at every tick.
  - [ ] `git show origin/main:pstack/skills/poteto-mode/playbooks/autopilot-stack.md`
  - [ ] `git show origin/main:pstack/skills/swarm/SKILL.md`
  - [ ] `git show origin/main:cursor-team-kit/skills/control-ui/SKILL.md`
  - [ ] `git show origin/main:pstack/skills/poteto-mode/playbooks/opening-a-pr.md`
  - [ ] `git show origin/main:pstack/skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md`
  - [ ] `git show origin/main:pstack/skills/principle-model-the-domain/SKILL.md`
  - [ ] In Metis-DS, `git show origin/main:docs/agents/continuous-development.md` and `git show origin/main:docs/agents/lifecycle-vsa.md`
- [ ] On the operator's go, arm the audit tick as `/loop 1h` with the tick prompt below. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook from trunk. Audit the operation against it and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then post a short status message to the operator in chat only when the audit found a tracked change that no earlier status message reported, such as a PR opened, a code-ready head, a round launched or closed, a verdict, a merge, a stuck agent and the action taken, a blocker added or cleared, or a decision only the operator can make. Name every such change and nothing else. Do not repeat a table, the merged list, or an unchanged blocker. If the audit found none, end the turn with no reply text. Either way, log this tick's row in your decision trail. The row names the items reported, or none."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] Spawn one owner per PR with the full lifecycle the execution playbook names.
- [ ] Follow this dependency graph. The program stacks, so a child bases on its parent branch.
  - [ ] KO-1 is first. It branches from `main`.
  - [ ] KO-2 and KO-3 after KO-1. They are independent of each other.
  - [ ] KO-4 after KO-2 and KO-3.
  - [ ] KO-5 after KO-4 is merged and deployed, and after the KO-1 inventory shows zero legacy `revise` rows in production.
  - [ ] KO-6 after KO-5 has run in production for one full review week without a rollback.
- [ ] Hold the file boundaries.
  - [ ] KO-1 touches only `src/review/knowledge_object_state_v1.py`, `scripts/ko_state_inventory.py`, `tests/test_ko_state_*.py` and `evidence/ko-1/**`.
  - [ ] KO-2 touches only the review card renderers and existing post-save response/navigation, `src/review/ko_receipt_ui_v1.py`, `src/review/review_cockpit_v1.py`, `src/review/review_workboard_v1.py`, `static/console.css` and their tests.
  - [ ] KO-3 touches only `src/publication/publication_readiness_v1.py`, `src/publication/publish_readiness_ui_v1.py`, `src/retrieval/retrieval_projection_v2.py`, `src/workflows/workflow_badge_counts_postgres_v1.py` and their tests.
  - [ ] KO-4 touches only `src/review/ko_transitions_v1.py`, the command methods it replaces, and their tests.
  - [ ] KO-5 only deletes code, rewrites stale contract rows, and updates the tests that pinned deleted paths.
  - [ ] KO-6 touches only `db/migrations/`, `scripts/ko_contract_migration.py`, `evidence/ko-6/**` and its tests.
- [ ] Hold the review gate. KO-2, KO-3 and KO-4 change an interaction. They wait for the operator's review in chat with screenshots and a video before merge.
- [ ] Hold the destructive gate. KO-6 never executes its migration in any shared database without the operator's written approval and a restore drill receipt.

### PR mechanics, for every PR

- [ ] Resolve the forge once. Default to `gh`; if `command -v origin` succeeds and Origin can resolve the repository, use `origin pr` for every PR operation. Record any fallback to `gh`. Never require `gt`. In this cloud session the GitHub MCP tools stand in for `gh`.
- [ ] Open the PR ready, never draft, per **Opening a PR**. Use the run's built-in PR tool when it has one, else `origin pr create --status open --base <base-branch>` or `gh pr create --base <base-branch>` according to the resolved forge. A stack child targets its parent branch.
- [ ] Write the PR body with the change-contract header from `docs/agents/continuous-development.md`, exactly one `Part of MET-X` line, and the `metis-linear-handoff-v1` block with the real head SHA, per `docs/agents/linear-github-handoff.md`.
- [ ] Run the repo's lint and typecheck once before the PR-facing push. Run `python scripts/check_architecture_boundaries.py`. Push with hooks on.
- [ ] Put the release-control markers `scope/belofte`, `slop`, `releasebewijs`, and `opslag` where state is read or written, in every changed test file.
- [ ] Run `/deslop` before each commit and `/no-comments` before review.
- [ ] Triage every Bugbot, Codex and security-reviewer comment per `../references/bugbot-triage.md`.
- [ ] Rebase onto current trunk before the code-ready report and babysit. Keep that merge base in fix rounds. Rebase again only at merge prep, on a `git merge-tree` conflict with trunk, or on a CI failure that comes from a change on trunk.
- [ ] Never skip PostgreSQL tests. Never raise the gunicorn timeout as a fix.

### Verdict and merge, for every PR

- [ ] At the code-ready head SHA and at each later push that changes the patch, run the swarm per `pstack/skills/swarm/SKILL.md`. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. Two or more audit lanes, each with its own focus, that read the diff and the receipts and distrust the PR body. The root audits the receipts in the merge-ready report before the verdict.
- [ ] One audit lane is the adversarial review required by `docs/agents/continuous-development.md`. It tries alternate writers and readers, inheritance and override paths, the Azure and local PostgreSQL topologies, stale envelope projections, duplicate authority, partial cutover, two workers, restart, recovery, rollback and failed cutover.
- [ ] Clean only when every lane is `PASS`. Findings go back to the owner, including a defect that a lane filed as a note. A new head gets a fresh swarm and a fresh verdict, except for results that stay valid under the patch-id rule in `playbooks/shipping.md`.
- [ ] A clean verdict appends the PR to the one linear stack on `main`. No owner merges. The operator lands the stack bottom-up. The patch-id rule in `playbooks/shipping.md` decides which verdicts survive a rebase.

### Boot recipe, for every live lane

Each live lane runs on its own cloud VM at the PR head. Drive through `control-ui` from `cursor-team-kit`.

- [ ] `git fetch origin <head-branch> && git checkout <head SHA>`.
- [ ] Start a throwaway PostgreSQL 16 with `scripts/test_postgres.sh`, apply `db/schema_v2.sql` and `db/migrations/*.sql`, then start the browser fixture for the lane (`tests/browser_knowledge_context_fixture.py` or `tests/browser_formation_repair_fixture.py`) or `python -m src.cli serve-console` after `console-account`. Wait until `/login` answers 200.
- [ ] Deliver input only through the control skill's commands. Read-only diagnostics are `/browser-manifest`, `/browser-review-events`, `scripts/ko_state_inventory.py --counts-only` and `psql` `SELECT` statements.
- [ ] Use only fixture data. Production exports stay local to the operator, and only counts leave them.
- [ ] Save every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png` and return the paths with the report.

## Derive one KO state from the nine fields (KO-1)

**Depends on.** None.

**Files.**

- [ ] Create `src/review/knowledge_object_state_v1.py`.
- [ ] Create `scripts/ko_state_inventory.py`.
- [ ] Create `tests/test_ko_state_derivation.py`.
- [ ] Create `tests/test_ko_state_derivation_postgres.py`.
- [ ] Create `evidence/ko-1/README.md`.

**Build.**

- [ ] Add `KO_STATES`, the eleven states Kandidaat, Context open, Bewijs open, Samengesteld, In review, Tweede review, Goedgekeurd, Gepubliceerd, Vervangen, Ingetrokken and Afgewezen, as a closed tuple in `knowledge_object_state_v1.py`.
- [ ] Add `derive_ko_state(obj, *, bindings, duty, accountability, release)` that returns `{"state", "reasons", "invalid"}` and never writes. It reads `admission_of`, `passage_register_of`, `review_passage`, `review_stage`, `object_review_bindings`, `definitive_review_disposition` and `document_release_serving_status`, the existing classifiers listed in Appendix D.
- [ ] Add `INVALID_CODES`, one code per forbidden combination. Start with approved without a valid binding, approved with register `not_yet_assessed`, persisted legacy `revise`, second-review mirror approved without a second binding, an approval outside `ALLOWED_FINAL_BY_SUITABILITY`, a register that disagrees with the reviewed suitability, and an invalid disposition. `superseded` without `superseded_by` is not invalid, because same-source reprocessing retires a removed candidate that way by design. Published while not approved needs the per-object registry and lands in KO-3.
- [ ] Add `FINAL_VALIDATION_STATUSES` and `RETIRED_VALIDATION_STATUSES` as the single definition of the duplicated sets in `operations_console_app.py`, `review_duty_v1.py`, `source_containers_v1.py`, `deterministic_review_repair_v1.py` and `workflow_badge_counts_postgres_v1.py`. Do not migrate those callers yet.
- [ ] Add `scripts/ko_state_inventory.py`, a read-only PostgreSQL script that prints counts per state and per invalid code. It prints no object ids, titles or text.
- [ ] Document the field-to-state table in `evidence/ko-1/README.md`, one row per state with the guard expression.

**You see.**

- [ ] `python scripts/ko_state_inventory.py --counts-only` on the fixture database prints one line per state and a line `invalid_total=<n>`, and exits 0.
- [ ] Every fixture KO maps to exactly one state. The script exits 2 with `ko_state_unclassified=<n>` when one does not.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_ko_state_derivation.py` gains one case per state and one case per invalid code, built from the shapes the writers in Appendix D actually produce. Run `python -m pytest tests/test_ko_state_derivation.py -q`.
- [ ] `tests/test_ko_state_derivation_postgres.py` runs ingest, review approve, second review, publish, withdraw and supersede through the real console and asserts the derived state after each command. Run `scripts/test_postgres.sh python -m pytest tests/test_ko_state_derivation_postgres.py -q`.
- [ ] The full suite stays green. Run `scripts/test_postgres.sh python -m pytest -q -x`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.7-xhigh-fast` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Approve one fixture KO through the review card at trunk and head. Trunk lacks the derivation, so record that and gate that the head card and the stored payload are byte-identical to trunk and the inventory reports Goedgekeurd. Save `ko1-regression.png`. Pass when the payload hashes match and the inventory line reads `Goedgekeurd=1`.
- [ ] Lane 2. Ingest the knowledge-context fixture and run the inventory. Save `ko1-ingest.png`. Pass when every object is in Kandidaat, Context open, Bewijs open, Samengesteld or In review and `ko_state_unclassified=0`.
- [ ] Lane 3. Choose "mist context" on a card. Save `ko1-context.png`. Pass when the inventory moves that object to Context open.
- [ ] Lane 4. Approve a high-risk object once. Save `ko1-second-review.png`. Pass when the inventory reports Tweede review for it.
- [ ] Lane 5. Complete the second review. Save `ko1-approved.png`. Pass when the inventory reports Goedgekeurd.
- [ ] Lane 6. Publish the document. Save `ko1-published.png`. Pass when the inventory reports Gepubliceerd for every approved object.
- [ ] Lane 7. Withdraw the release. Save `ko1-withdrawn.png`. Pass when the inventory reports Ingetrokken.
- [ ] Lane 8. Merge two candidates through the repair route. Save `ko1-superseded.png`. Pass when the merge target reports Vervangen.
- [ ] Lane 9. Reject a candidate. Save `ko1-rejected.png`. Pass when the inventory reports Afgewezen.
- [ ] Lane 10. Restart the console between lanes 4 and 5. Save `ko1-restart.png`. Pass when the inventory output before and after the restart is identical.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Review card server time p95 at trunk and head, and the inventory wall time for one document of 900 fragments as the diff-added work.
- [ ] Probe. `evidence/974-p4b/run_p4b.sh` for the review card, interleaved trunk, head, trunk, head, five rounds. `time python scripts/ko_state_inventory.py --counts-only` on the same database.
- [ ] Baseline. Record the trunk review card p95 first.
- [ ] Rule. Head p95 above trunk p95 by more than 5 percent fails, since KO-1 adds no work to the card. The inventory above 10 seconds for one document fails.

**Review gate.** None. KO-1 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends KO-1 to the stack and the operator lands it bottom-up.
- [ ] The operator runs the inventory in production after deploy and posts counts only on the program issue. Those counts decide KO-5's start.

## Show a clear review card, then a receipt after a successful save (KO-2)

**Depends on.** KO-1.

**Interaction.** Clear review card → review and save → receipt of the saved result. This follows William's correction: the bonnetje is the overview after the action, showing what the reviewer did and how the result is organised in the kernel. It is not placed before approval.

**Files.**

- [ ] Edit `src/operations_console_app.py` (review card renderer and existing post-save response/navigation only).
- [ ] Edit `src/review/review_cockpit_v1.py`.
- [ ] Edit `src/review/review_workboard_v1.py`.
- [ ] Edit `static/console.css`.
- [ ] Create `src/review/ko_receipt_ui_v1.py`.
- [ ] Create `tests/test_ko_receipt_ui.py`.
- [ ] Edit `tests/browser_review_disposition_check.cjs`.
- [ ] Reuse the existing save result and authorised read boundary; follow the existing response owner where the route delegates navigation.

**Build.**

- [ ] Render the derived state on the review card header, from `derive_ko_state`, in Dutch, with the reasons as a short list. Before saving, the card provides the source and context needed to review, without a receipt.
- [ ] Add `render_ko_receipt` in `ko_receipt_ui_v1.py`. Render it only after the existing command has successfully saved. It identifies the action and the exact saved object version, and shows how its claim, context, evidence and provenance are organised in the kernel.
- [ ] Derive the receipt from the durable result of that action through the existing authorised readers. Posted form values or a success flag alone are not evidence of a saved decision. A later change must not be silently presented as the result of this action.
- [ ] Present the receipt within the existing post-save navigation, without a new form, confirmation click, separate approval step, stored receipt, status or write authority. An initial review card has no successful-action receipt.
- [ ] On validation refusal, conflict, rollback or an unconfirmed save outcome, preserve the existing error/recovery flow and show no successful receipt. Display only what was saved: opening a repair form is not a completed correction; a first approval is not a completed second review or publication.
- [ ] Replace the workboard's own status labels with the derived state. Remove the workboard's local "final" set in favour of `FINAL_VALIDATION_STATUSES`.
- [ ] Run Impeccable in Operate mode per `docs/agents/impeccable.md` for the header and the post-save receipt.

**You see.**

- [ ] Before saving, a KO in review shows the state "In review" and a clear review card, without a receipt.
- [ ] After successful storage, "Dit heb je gedaan" shows the actual action, saved version and organisation of the result. Approval may be labelled "Dit heb je goedgekeurd" only when that approval was saved.
- [ ] The next passage or overview remains reachable through the existing flow; there is no extra confirmation step.
- [ ] Approving still writes the same review event and binding as trunk. A required second review or publication is shown as pending when it has not happened.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_ko_receipt_ui.py` gains a case per state header and cases for receipt absence before saving, receipt contents matching the exact durable action/version, and no successful receipt on validation refusal, stale conflict, rollback or unconfirmed outcome. It also proves that subsequent changes and another object's result cannot be presented as this action's receipt. Run `scripts/test_postgres.sh python -m pytest tests/test_ko_receipt_ui.py -q`.
- [ ] `tests/characterization/` review room suites still pass with updated snapshots limited to the state header and receipt at the existing post-save destination. Run `scripts/test_postgres.sh python -m pytest tests/characterization -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.7-xhigh-fast` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Open the first fixture KO at trunk and head: head has no receipt before saving. Approve on both, then read the head receipt and reopen the saved object. Save `ko2-regression.png`. Pass when the event and binding match trunk, the receipt matches the saved action/version and organisation, and no extra confirmation is required.
- [ ] Lane 2. Open a card in Context open. Submit a stale revision and then a validation-refused action. Save `ko2-context.png`. Pass when the card names the missing context, the existing errors remain visible, and neither failure shows a successful receipt.
- [ ] Lane 3. Approve a high-risk object once, then open it as the independent second reviewer and complete the second review. Save `ko2-second.png`. Pass when the first receipt reports the saved first approval with second review pending, and the second receipt reports only the successfully saved independent decision.
- [ ] Lane 4. Reopen the saved approved version and compare it with the receipt, then repeat the action using an old revision. Save `ko2-approved.png`. Pass when the saved result matches, no approval button is offered for completed work, and the refused stale action does not produce a new successful receipt.
- [ ] Lane 5. At 375 px width, review and save a fixture KO. Save `ko2-mobile.png`. Pass when both card and subsequent receipt have no horizontal scroll and the receipt rows stack.
- [ ] Lane 6. With JavaScript disabled, review and save a fixture KO. Save `ko2-nojs.png`. Pass when the card renders without a receipt before the save, approval posts, and the receipt appears only after successful storage.
- [ ] Lane 7. Use the keyboard only to review, save and read the receipt. Save `ko2-keyboard.png`. Pass when focus is visible, the saved outcome is accessible and continuation needs no extra confirmation.
- [ ] Lane 8. Open the workboard. Save `ko2-workboard.png`. Pass when every row shows a state from `KO_STATES` and none shows a legacy label.
- [ ] Lane 9. Open a recommendation without evidence. Save `ko2-no-evidence.png`. Pass when the review card names the missing evidence without a receipt. A refusal has no successful receipt; any permitted saved action reports the actual outcome and does not invent evidence.
- [ ] Lane 10. In dark mode, review, save and read the receipt. Save `ko2-dark.png`. Pass when both the card and post-save receipt meet WCAG AA contrast per an axe run.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Review card server time p95, the complete save → existing post-save destination time p95, and PostgreSQL bytes read for each path, at trunk and head.
- [ ] Probe. `evidence/974-p4b/run_p4b.sh` for the existing read baseline, plus the same fixture through save and its post-save destination, interleaved trunk and head, five rounds each.
- [ ] Baseline. Record trunk p95 and bytes for both paths first.
- [ ] Rule. Head p95 or bytes above the corresponding trunk value by more than 10 percent fails. Measure the whole save/navigation action so receipt cost cannot be hidden in a redirect.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1, 2, 3 and 5 screenshots into `evidence/ko-2/ko-2-review-<slug>.png`, including the card before saving, the receipt after success and an error without a successful receipt.
- [ ] Record a 30 to 60 second video of opening the card, reviewing and saving, reading the resulting receipt, then continuing through the existing navigation. Save it as `evidence/ko-2/ko-2-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends KO-2 to the stack and the operator lands it bottom-up.

## Derive publication readiness and the package from the KO state (KO-3)

**Depends on.** KO-1 and the operator's answers on per-object publication and the stored or derived package.

**Files.**

- [ ] Edit `src/publication/publication_readiness_v1.py`.
- [ ] Edit `src/publication/publish_readiness_ui_v1.py`.
- [ ] Edit `src/retrieval/retrieval_projection_v2.py`.
- [ ] Edit `src/workflows/workflow_badge_counts_postgres_v1.py`.
- [ ] Create `tests/test_ko_publication_readiness_postgres.py`.

**Build.**

- [ ] Compute `REVIEW_WORK_INCOMPLETE`, `SOURCE_PASSAGE_REVIEW_INCOMPLETE`, `REVIEW_REPAIR_INCOMPLETE` and `REVIEW_DISPOSITION_INCONSISTENT` from `derive_ko_state` per object. The blocker codes and the publish refusal audit stay unchanged.
- [ ] Make `retrieval_projection_v2.publication_errors` include only KOs in Goedgekeurd and read nothing else.
- [ ] Add the invalid code `published_not_approved` to `knowledge_object_state_v1.INVALID_CODES`, read from the per-object registry.
- [ ] Replace the SQL copy of the final set in `workflow_badge_counts_postgres_v1.py` with a value generated from `FINAL_VALIDATION_STATUSES`, and pin equality with a test.
- [ ] Show per object on the readiness page which state blocks it, per the per-object decision. If the operator chose per document, show the same list without a per-object publish action.

**You see.**

- [ ] The readiness page lists each blocking KO with its state and one reason.
- [ ] A document whose KOs are all Goedgekeurd, Afgewezen or Vervangen shows "Klaar om te publiceren".

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_ko_publication_readiness_postgres.py` asserts identical blocker sets at trunk semantics and head for every fixture document, plus one case per KO state. Run `scripts/test_postgres.sh python -m pytest tests/test_ko_publication_readiness_postgres.py tests/test_vsa_publication_readiness_v1.py tests/test_t12_publication_readiness_authority.py -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.7-xhigh-fast` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Open the readiness page of a half-reviewed document at trunk and head. Save `ko3-regression.png`. Pass when both refuse publication with the same blocker codes.
- [ ] Lane 2. Finish all reviews and open readiness. Save `ko3-ready.png`. Pass when the page reads "Klaar om te publiceren".
- [ ] Lane 3. Publish. Save `ko3-published.png`. Pass when only Goedgekeurd KOs appear in the retrieval projection count.
- [ ] Lane 4. Leave one KO in Tweede review. Save `ko3-second-open.png`. Pass when that KO is listed with state Tweede review and publish is refused.
- [ ] Lane 5. Leave one passage not assessed. Save `ko3-passage-open.png`. Pass when the source passage blocker names it.
- [ ] Lane 6. Create a disposition conflict via the fixture. Save `ko3-conflict.png`. Pass when `REVIEW_DISPOSITION_INCONSISTENT` is shown and publish is refused.
- [ ] Lane 7. Compare badge counts with the readiness page. Save `ko3-badges.png`. Pass when the counts agree.
- [ ] Lane 8. Withdraw after publish. Save `ko3-withdraw.png`. Pass when the readiness page and the inventory both report Ingetrokken.
- [ ] Lane 9. Open the readiness page at 375 px. Save `ko3-mobile.png`. Pass when there is no horizontal scroll.
- [ ] Lane 10. Restart the console during a refused publish. Save `ko3-restart.png`. Pass when the refusal audit row exists once and the page shows the same blockers after restart.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. `consider_publish` wall time and the readiness page server time for a 900-fragment document, at trunk and head.
- [ ] Probe. A timed `consider_publish` loop in `tests/test_ko_publication_readiness_postgres.py::test_timing_probe`, interleaved trunk and head, five rounds.
- [ ] Baseline. Record the trunk time first.
- [ ] Rule. Head above trunk by more than 10 percent fails.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1, 2, 4 and 6 screenshots into `evidence/ko-3/ko-3-review-<slug>.png`.
- [ ] Record a 30 to 60 second video from a refused readiness page to a successful publish, on a lane VM. Save it as `evidence/ko-3/ko-3-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends KO-3 to the stack and the operator lands it bottom-up.

## Route every KO change through one transition table (KO-4)

**Depends on.** KO-2, KO-3, the operator's answer on mandatory evidence (given), and #942 for the source-context commands.

**Files.**

- [ ] Create `src/review/ko_transitions_v1.py`.
- [ ] Edit `src/review/review_workflow_v3.py`.
- [ ] Edit `src/review/closed_review_loop_v1.py`.
- [ ] Edit `src/review/deterministic_review_repair_v1.py`.
- [ ] Edit `src/review/source_context_review_v1.py`.
- [ ] Edit `src/operations_console_v1.py` (`review_object`, `approve_second_review`, `correct_object`, `confirm_object_type` only).
- [ ] Create `tests/test_ko_transitions_postgres.py`.

**Build.**

- [ ] Define `TRANSITIONS`, a table of `(from_state, event, to_state, guard)` that matches the statechart in the KO statechart document. Correction is an event that creates a new revision that starts as Kandidaat, never a stored `revise`. The derived state of that revision then follows the guards.
- [ ] Add `apply_ko_event(console, object_id, event, payload)` that derives the current state, checks the table and the guard, then calls the existing writer. It raises one refusal type with the state and event in Dutch.
- [ ] Route `review_object`, `approve_second_review`, `correct_object`, `confirm_object_type`, `resolve_support_relation`, `_supersede_merge_targets` and the source-context commands through `apply_ko_event`.
- [ ] Express `ALLOWED_FINAL_BY_SUITABILITY`, `require_allowed_review_disposition` and `without_closed_follow_up` as guards in the table and delete their ad-hoc call sites.
- [ ] Add the Bewijs open guard per the operator's answer. A recommendation leaves Bewijs open only with linked evidence, or with an explicit "niet van toepassing" if the operator allowed it.
- [ ] Stop writing `validation_status="revise"`. A correction writes `needs_review` on the new revision, as `revise_object` already does.

**You see.**

- [ ] An approve on a KO in Bewijs open is refused with "Dit kennisobject heeft nog geen onderbouwing" and no event or binding is written.
- [ ] A correction shows the new revision in its derived state, never Goedgekeurd, and the old revision as history.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_ko_transitions_postgres.py` enumerates every `(state, event)` pair and asserts either the table's target or the refusal, with no write on refusal. Run `scripts/test_postgres.sh python -m pytest tests/test_ko_transitions_postgres.py -q`.
- [ ] The P3, P4c and P4d suites pass unchanged in behaviour. Run `scripts/test_postgres.sh python -m pytest tests/test_review_disposition_choices.py tests/test_review_disposition_precheck.py tests/test_review_closure_v1.py tests/test_deterministic_review_repair_v1.py -q`.
- [ ] `grep -rn "\"revise\"" src/review src/operations_console_v1.py` finds no writer.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.7-xhigh-fast` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run the review disposition browser check at trunk and head. Save `ko4-regression.png`. Pass when the offered choices per suitability are identical.
- [ ] Lane 2. Try to approve a recommendation without evidence. Save `ko4-bewijs-open.png`. Pass when the refusal text shows and `/browser-review-events` count is unchanged.
- [ ] Lane 3. Link evidence, then approve. Save `ko4-bewijs-closed.png`. Pass when the state moves to Goedgekeurd or Tweede review per risk.
- [ ] Lane 4. Choose "goedkeuren na correctie". Save `ko4-correction.png`. Pass when a new revision exists in an open state before review and no row has `revise`.
- [ ] Lane 5. Post a forged approve for a "geen kenniseenheid" suitability with curl. Save `ko4-forged.png`. Pass when the response is a refusal and nothing is written.
- [ ] Lane 6. Submit two approvals for the same KO from two browser contexts at once. Save `ko4-concurrent.png`. Pass when exactly one binding is written and the other gets the stale-revision message.
- [ ] Lane 7. Run a second review as the same reviewer. Save `ko4-four-eyes.png`. Pass when it is refused.
- [ ] Lane 8. Merge two candidates. Save `ko4-merge.png`. Pass when the target is Vervangen with `superseded_by` set.
- [ ] Lane 9. Confirm source context that rejects a source. Save `ko4-source-context.png`. Pass when dependants return to an open state before review and their bindings are invalid.
- [ ] Lane 10. Kill the worker in the middle of an approve and restart. Save `ko4-restart.png`. Pass when the KO is either fully approved or untouched, never half.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Review save time p95 for approve and for revise, at trunk and head.
- [ ] Probe. `evidence/974-p4b/run_p4b.sh` save probes, interleaved trunk and head, five rounds.
- [ ] Baseline. Record the trunk p95 first.
- [ ] Rule. Head above trunk by more than 10 percent fails. Any save above the gunicorn timeout fails outright.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 2, 3, 4 and 6 screenshots into `evidence/ko-4/ko-4-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the refused approve, linking evidence and the successful approve, on a lane VM. Save it as `evidence/ko-4/ko-4-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends KO-4 to the stack and the operator lands it bottom-up.

## Delete the parallel ways of working (KO-5)

**Depends on.** KO-4 in production, and a production inventory with `legacy_revise=0`.

**Files.**

- [ ] Delete `migrate_legacy_revise_to_review` in `src/review/review_closure_v1.py` and its startup call in `src/console_asgi.py`.
- [ ] Delete the disabled `apply_reviews` CLI in `src/review/review_workflow_v3.py`.
- [ ] Delete `_local_release_serving_status` in `src/documents/document_status_v1.py`.
- [ ] Delete the `canonical_publication_store is None` fallback in `src/workflows/workflow_badge_counts_postgres_v1.py`.
- [ ] Delete the SQLite pilot `src/publication/canonical_store.py` and its CLI entries, after `grep` shows no runtime import.
- [ ] Edit every reader of `governance.second_review`, `governance.publication_status`, envelope `review_passes` and `clinical_rereview_required` to read the derived state or the bindings instead.
- [ ] Edit the stale topology rows in `docs/change-contracts/knowledge-context-foundation.md`, `source-accountability-recovery.md`, `bounded-model-processing.md`, `source-containers.md` and `recoverable-formation.md`.

**Build.**

- [ ] Remove each listed path in its own commit, callers first, per the migrate-callers-then-delete principle.
- [ ] Stop writing the four mirror fields. Readers already ignore them, so stored values become inert. Do not strip stored values here.
- [ ] Add `tests/test_ko_single_way.py`, an architecture test that fails when a module outside `ko_transitions_v1.py` writes `validation_status` or when a duplicate final set appears.

**You see.**

- [ ] `rg -n "migrate_legacy_revise_to_review|_local_release_serving_status|canonical_store import" src` prints nothing.
- [ ] Console startup logs no legacy migration line.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_ko_single_way.py` passes and fails on a planted second writer. Run `python -m pytest tests/test_ko_single_way.py -q`.
- [ ] Tests that pinned deleted paths are deleted with the path, each listed in the PR body with the reason. Run `scripts/test_postgres.sh python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.7-xhigh-fast` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run ingest, review, second review and publish at trunk and head. Save `ko5-regression.png`. Pass when the inventory counts and the published object count are identical.
- [ ] Lane 2. Start the console on a database copy that still holds the mirror fields. Save `ko5-old-data.png`. Pass when startup succeeds and every state matches the KO-4 inventory.
- [ ] Lane 3. Open the second-review workboard. Save `ko5-second-board.png`. Pass when the list equals the bindings-derived Tweede review set.
- [ ] Lane 4. Open document status for a published document. Save `ko5-doc-status.png`. Pass when it shows the PostgreSQL registry status.
- [ ] Lane 5. Open badge counts. Save `ko5-badges.png`. Pass when they equal the inventory.
- [ ] Lane 6. Reextract an unpublished document. Save `ko5-reextract.png`. Pass when removed candidates are Vervangen and the rest are in an open state before review.
- [ ] Lane 7. Query the MCP read tools for approved objects. Save `ko5-mcp.png`. Pass when the result set equals Goedgekeurd plus Gepubliceerd.
- [ ] Lane 8. Query the product API. Save `ko5-api.png`. Pass when only Gepubliceerd objects are served.
- [ ] Lane 9. Restart with two workers. Save `ko5-two-workers.png`. Pass when both serve identical states.
- [ ] Lane 10. Roll back to the KO-4 image on the same database. Save `ko5-rollback.png`. Pass when KO-4 starts and the inventory is unchanged.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Console cold start time and review card p95, at trunk and head.
- [ ] Probe. Ten interleaved cold starts and `evidence/974-p4b/run_p4b.sh`, trunk and head.
- [ ] Baseline. Record trunk first.
- [ ] Rule. Head slower than trunk on either metric by more than 5 percent fails. Deleted code may not add work.

**Review gate.** None. KO-5 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends KO-5 to the stack and the operator lands it bottom-up.

## Strip the inert fields from stored data with approval (KO-6)

**Depends on.** KO-5 in production for one review week without rollback, and the operator's written approval on the program issue.

**Files.**

- [ ] Create `db/migrations/0NN_ko_contract_strip_mirrors.sql`.
- [ ] Create `scripts/ko_contract_migration.py`.
- [ ] Create `tests/test_ko_contract_migration_postgres.py`.
- [ ] Create `evidence/ko-6/README.md`.

**Build.**

- [ ] Remove `governance.second_review`, `governance.publication_status`, envelope `review_passes` and `clinical_rereview_required` from stored payloads, and rewrite any remaining `revise` row to `needs_review`.
- [ ] Make the script dry-run by default. It prints counts per field, and a payload hash before and after for the canonical part, which must not change because governance is outside the canonical hash.
- [ ] Refuse to run with `--apply` unless a `pg_dump` file and a restore-drill receipt from the same day are passed.

**You see.**

- [ ] The dry run prints `would_strip=<n>` per field and `canonical_hash_changes=0`.
- [ ] After `--apply` the inventory is identical to before.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_ko_contract_migration_postgres.py` covers dry-run, apply, idempotent second apply, refusal without backup, and restore from the dump. Run `scripts/test_postgres.sh python -m pytest tests/test_ko_contract_migration_postgres.py -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.7-xhigh-fast` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run the full review and publish scenario on a database before and after the migration. Save `ko6-regression.png`. Pass when inventory, published count and retrieval output are identical.
- [ ] Lane 2. Dry run. Save `ko6-dry-run.png`. Pass when counts print and no row changes.
- [ ] Lane 3. Apply without a backup. Save `ko6-no-backup.png`. Pass when the script refuses.
- [ ] Lane 4. Apply with backup and receipt. Save `ko6-apply.png`. Pass when the strip counts equal the dry run.
- [ ] Lane 5. Apply twice. Save `ko6-idempotent.png`. Pass when the second run strips zero.
- [ ] Lane 6. Restore the dump into a fresh database. Save `ko6-restore.png`. Pass when the KO-5 image starts on it and the inventory matches.
- [ ] Lane 7. Kill the script mid-apply. Save `ko6-interrupted.png`. Pass when a rerun completes and no payload is half-stripped.
- [ ] Lane 8. Open a published card after apply. Save `ko6-published-card.png`. Pass when it renders as before.
- [ ] Lane 9. Serve the product API after apply. Save `ko6-api.png`. Pass when responses are byte-identical to before.
- [ ] Lane 10. Verify the publication chain. Save `ko6-chain.png`. Pass when the chain verification script reports no break.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Migration wall time and lock wait time on a production-sized copy, and review card p95 before and after.
- [ ] Probe. The script with `--apply` on a restored copy, and `evidence/974-p4b/run_p4b.sh` before and after, interleaved.
- [ ] Baseline. Record the before p95 first.
- [ ] Rule. Any lock held above 5 seconds fails. Review card p95 worse after than before fails.

**Review gate.** None. KO-6 is not review-gated as an interaction, but it holds the destructive gate in the program checklist.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator lands KO-6, takes the backup, runs the restore drill and runs `--apply` in production. No agent runs it.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] The production inventory shows `invalid_total=0` and `ko_state_unclassified=0`. The operator posts the counts on the program issue.
- [ ] Reply to the operator with the stack root and tip, a one-line verdict per PR, and anything parked with the reason.

## Appendix A. Prototype evidence

No prototype ran before this plan. Three questions stay unproven.

1. How many stored KOs fall into an invalid combination today. KO-1 answers it with counts from production, run by the operator.
2. Whether every current KO maps to exactly one of the eleven states. KO-1 makes an unmapped KO a hard error, so the answer arrives before any reader moves.
3. Whether the statechart is free of dead ends under retry and concurrency. A bounded TLA+ check would answer it, but the statechart skill is not installed in the pinned plugins fork. See Appendix C.

Measured facts this plan relies on come from the read-only map of 5 November 2026 on trunk `49b7f60`. There are 9 implicit state fields, about 480 references in `src`, about 40 writers of `validation_status`, and two startup flows that mutate KO state.

## Appendix B. Alternatives rejected

**Rebuild the KO model from scratch.** It loses the published history, the review ledger and the bindings, which are the evidence the advisors asked for. It is a big-bang replacement, which `continuous-development.md` forbids by default.

**Store the state as a new column.** It creates a second authority next to bindings, register and registry. `statechart-integration.md` forbids a stored status for a diagram, and divergence would be undetectable.

**Keep the ad-hoc guards and only add the receipt.** It leaves P3, P4c and P4d as separate rule sets, which is the parallel way of working the operator asked to remove.

**Delete the mirror fields in the same PR that stops reading them.** It removes rollback. Behaviour cutover and destructive removal stay separate per `continuous-development.md`.

## Appendix C. Risks

- KO-1. The derivation may disagree with `definitive_review_disposition` on edge cases. The owner pins both in the same test and treats any disagreement as a finding, not a tolerance.
- KO-2. Receipt rendering can slow the post-save response, and state presentation can slow the card. The #974 worker timeouts make both relevant: measure card reads and the complete save/navigation action; the perf rule holds each at 10 percent.
- KO-3. The per-object decision is open. Without it KO-3 builds per-document readiness only.
- KO-4. The Bewijs open guard can block existing recommendations that have no linked evidence. The owner reports the KO-1 production count before KO-4 merges, and the operator decides whether existing KOs are grandfathered.
- KO-4. Two workers can race on one KO. Lane 6 and the revision CAS cover it.
- KO-5. A reader of a mirror field may be missed. The architecture test and the adversarial audit lane hunt for it.
- KO-6. The migration is destructive. Only the operator runs it, after a backup and a restore drill.
- Program. The swarm worker model and `control-ui` are not available in this cloud session. Lanes then run as Playwright scripts beside `tests/browser_review_disposition_check.cjs`, each still saving its screenshot and stating its pass predicate.
- Program. The statechart skill is absent from the pinned plugins fork. Installing it follows `docs/agents/statechart-integration.md` as its own Class C change and is not a dependency of KO-1.

Work that runs beside this program, so no PR builds a second way.

- #990 is the product acceptance for the review card and the receipt after a successful save. KO-2 builds the state header and post-save overview of the exact durable action/version and its kernel organisation; KO-4 builds the three questions as transition guards. No extra form or confirmation step is added. Nobody changes this flow for #990 outside KO-2 and KO-4.
- #991 owns the per-object publish action and its contract. KO-3 only derives readiness per object and adds no publish action.
- #992 measures the Athena package, which stays derived on read.
- #942 owns the single writer for source roles. KO-4 routes the source-context commands through `apply_ko_event` only on top of that writer, so the source-context part of KO-4 waits for #942.
- #952 owns the evidence and transaction boundary for review and publication decisions. KO-4 calls the existing writers inside that boundary and adds no transaction of its own.
- #986 records the definition and the review measure. Its open items do not block KO-1 to KO-3.

Product decisions recorded by the operator.

| Decision | Answer | Date |
|---|---|---|
| Supporting evidence mandatory per type, and does "niet van toepassing" close it | Mandatory for every type. An explicit, recorded "niet van toepassing" closes it. | 2026-11-05 |
| Publication per object or per document (#991) | Per object. | 2026-11-05 |
| Package derived on read or stored aggregate | Derived on read. No new storage or authority. | 2026-11-05 |

The operator gave the go for KO-1 on 2026-11-05. KO-2 onward wait for KO-1 to merge.

## Appendix D. Links and reading list

- Read before editing. `docs/agents/continuous-development.md`, `docs/agents/lifecycle-vsa.md`, `docs/agents/statechart-integration.md`, `docs/agents/linear-github-handoff.md`, `docs/agents/postgres-tests.md`, `docs/change-contracts/d6b-postgres-only-runtime.md`.
- The KO definition and the statechart live in the Claude Docs "Wat is een kennisobject en wat beoordeel je?" and "Kennisobject als statechart".
- Existing classifiers to reuse. `review_disposition_v1.definitive_review_disposition`, `knowledge_path_v1.candidate_lifecycle`, `review_duty_v1.review_stage`, `source_containers_v1.source_accountability`, `passage_register_v1.PASSAGE_REGISTER_STATUSES`, `admission_gate_v1.admission_of`, `publish_authorization_v1.still_matches`, `durable_publication_console_v1.document_release_serving_status`, `revision_workflow.revise_object`.
- Authorities that stay. Bindings in `workflow.publish_authorizations` own approval. `metadata.review_passage` owns the disposition. `publication_registry` owns serving. `metadata.admission` and `passage_register` with `source=extract` stay derived projections.
- Writers of `validation_status` are listed in the program issue's authority map.
- KO-1 and KO-4 owners run `pstack/skills/how/SKILL.md` before building and `pstack/skills/interrogate/SKILL.md` on their own diff. Every owner keeps a trail per `pstack/skills/show-me-your-work/SKILL.md`.
