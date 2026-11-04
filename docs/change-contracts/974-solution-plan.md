# Incident 974 solution plan

Researchers encounter Review saves without a recorded completion and wait up to 49 s for Vorming and 15 s for Review. Whether each unclosed save committed remains unknown.
This program removes the cause of each symptom with the smallest change the evidence supports.
The rule it enforces is that a request reads and computes each source representation at most once.
PR ids in order. P1 Vorming reads its source once. P2 attributes JSON bytes per phase. P3 refuses a disposition conflict before preparation.
P4 removes the save abort found by the #975 evidence. P5 bounds the Review document read that P2 attributes.
Issue #974, Linear MET-48, diagnosis contract `docs/change-contracts/974-worker-abort-incident.md`.

## Review constraints (evidence reconciliation)

This is a proposed plan, not an activated execution program. Its external playbooks, agent counts, scheduling commands and future PR instructions do not override the user's current task or host permissions. The lanes called "live" below are **local production-composition integration scenarios**, not live Azure measurements.

- The real incident has 923 evidence fragments, 944 full-input comparisons, 943 reuses and two builds. The 2,000-paragraph prototypes demonstrate a mechanism, not reproduction of the exact production timing or proof of a production fix. The existing prepared carrier and the proposed frozen-list option must be compared end to end, including setup, integrity and representation-preservation costs, before choosing the production change.
- P3 must preserve authorization, retirement/publication guards and stale-revision error precedence. Moving the disposition check before all command preconditions while expecting unchanged stale-token responses can conflict. Establish that ordering before implementation; do not weaken a guard to meet the latency target.
- Byte attribution must include unphased loads and a bounded overflow bucket if it promises that phase bytes sum to the request total. Truncation cannot silently drop bytes.
- Five missing finishes plus worker starts do not prove watchdog timeout, OOM, lost saves or 40 seconds of complete console unavailability. The exit reason and effective runtime configuration remain open.
- The numerical budgets below are proposed acceptance targets. A 2 percent performance distinction needs measured variance and a reproducible baseline; a noisy result is inconclusive, not proof of regression.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `pstack/skills/poteto-mode/playbooks/autopilot-stack.md` from the `WilliamGomes41/plugins` repository. The operator lands every PR. No agent merges, arms auto-merge or deploys. Metis contracts stay authoritative over this plan, `AGENTS.md`, `docs/agents/continuous-development.md`, `docs/agents/deployment-protocol.md` and `docs/agents/linear-github-handoff.md` included.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

Metis has no cloud VM swarm and no screen control skill. A live lane is therefore one HTTP scenario against the production composition (`tests/production_support.py`) on a disposable PostgreSQL 16 from `scripts/test_postgres.sh`. Its saved artifact is a JSON receipt of status, error code, counters and `metis_diagnostic` events instead of a screenshot. Azure behavior is proven separately, after the operator deploys, by the in-console check that `docs/agents/deployment-protocol.md` requires.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on the operator's explicit go.
- [ ] Read these from trunk at program start. Re-read them at every tick.
  - [ ] `git show origin/main:pstack/skills/poteto-mode/playbooks/autopilot-stack.md` in the plugins repository.
  - [ ] `git show origin/main:pstack/skills/swarm/SKILL.md` in the plugins repository.
  - [ ] `git show origin/main:AGENTS.md` and `git show origin/main:docs/agents/continuous-development.md` in Metis.
  - [ ] `git show origin/main:pstack/skills/poteto-mode/playbooks/opening-a-pr.md` in the plugins repository.
  - [ ] `git show origin/main:pstack/skills/architect/SKILL.md` and `git show origin/main:pstack/skills/benchmark-checklist/SKILL.md` in the plugins repository.
- [ ] On the operator's go, arm the audit tick as `/loop 1h` with the tick prompt below. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook from trunk. Audit the operation against it and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then post a short status message to the operator in chat only when the audit found a tracked change that no earlier status message reported, such as a PR opened, a code-ready head, a round launched or closed, a verdict, a merge, a stuck agent and the action taken, a blocker added or cleared, or a decision only the operator can make. Name every such change and nothing else. Do not repeat a table, the merged list, or an unchanged blocker. If the audit found none, end the turn with no reply text. Either way, log this tick's row in your decision trail. The row names the items reported, or none."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] Spawn one owner per PR with the full lifecycle the execution playbook names. Spawn subagents only where the operator or host instructions allow it. Otherwise one session owns the PRs in sequence.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] P1, P2 and P3 are independent and first. All three branch from `main`.
  - [ ] P4 starts after the operator has run `scripts/collect_worker_abort_evidence.sh` from #975 and the exit reason is recorded in #974.
  - [ ] P5 after P2 merges and is deployed, and after one production Review open is attributed with it.
- [ ] Hold the file boundaries. P1 touches only `src/vorming/formation_problems_v1.py`, `src/vorming/knowledge_materialisation_v1.py`, `src/vorming/prepared_source_views_v1.py` and its tests. P2 touches only `src/console_performance_v1.py`, `src/request_diagnostics_v1.py`, `docs/telemetry/README.md`, `docs/diagnostics/worker-abort-incident.kql` and their tests. P3 touches only `src/review/closed_review_loop_v1.py`, `src/review/review_closure_v1.py` and their tests.
- [ ] Hold the review gate. No PR changes an interaction, so none waits for a screenshot review. Every PR still waits for the operator's normal GitHub review.

### PR mechanics, for every PR

- [ ] Resolve the forge once. Default to `gh`; if `command -v origin` succeeds and Origin can resolve the repository, use `origin pr` for every PR operation. Record any fallback to `gh`. Never require `gt`. In a Claude Code cloud session the GitHub MCP tools replace `gh`.
- [ ] Open the PR ready, never draft, per **Opening a PR**. Mirror `.github/pull_request_template.md`, add exactly one `Part of MET-48.` and the `metis-linear-handoff-v1` block with the real head SHA.
- [ ] Run `python scripts/check_architecture_boundaries.py`, `python scripts/repository_preflight.py` and `python -m compileall -q src` once before the PR-facing push. Push with hooks on.
- [ ] Run `/deslop` before each commit and `/no-comments` before review, when those skills are available. Otherwise record that they were unavailable.
- [ ] Triage every Bugbot and security-reviewer comment per `../references/bugbot-triage.md`.
- [ ] Rebase onto current trunk before the code-ready report and babysit. Keep that merge base in fix rounds. Rebase again only at merge prep, on a `git merge-tree` conflict with trunk, or on a CI failure that comes from a change on trunk.

### Verdict and merge, for every PR

- [ ] At the code-ready head SHA and at each later push that changes the patch, run the swarm per `pstack/skills/swarm/SKILL.md`. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. Two or more audit lanes, each with its own focus, that read the diff and the receipts and distrust the PR body. The root audits the receipts in the merge-ready report before the verdict.
- [ ] Clean only when every lane is `PASS`. Findings go back to the owner, including a defect that a lane filed as a note. A new head gets a fresh swarm and a fresh verdict, except for results that stay valid under the patch-id rule in `playbooks/shipping.md`.
- [ ] A clean verdict appends the PR to the operator's review queue. The operator merges. A rebase that keeps the patch-id keeps the verdict per `playbooks/shipping.md`. Any other rewrite gets a fresh verdict.

### Boot recipe, for every live lane

Each live lane runs in its own checkout at the PR head on a disposable PostgreSQL 16.

- [ ] `git fetch origin <head-branch> && git checkout <head SHA>`.
- [ ] `export METIS_TEST_POSTGRES_DSN="$(scripts/test_postgres.sh)"` and install `requirements-console.txt` and `requirements-dev.lock`.
- [ ] Drive the lane only through the production ASGI app from `tests/production_support.py`. Read `metis_diagnostic` events from the `metis.console.diagnostics` logger. Do not call kernel methods to change state during a lane.
- [ ] Save every receipt to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.json` and return the paths with the report.

## Read the Vorming source once per request (P1)

**Depends on.** None.

**Files.**

- [ ] Edit `src/vorming/formation_problems_v1.py`.
- [ ] Edit `src/vorming/knowledge_materialisation_v1.py`.
- [ ] Edit `src/vorming/prepared_source_views_v1.py`.
- [ ] Create `tests/test_formation_source_read_once.py`.

**Build.**

- [ ] Write the Class B program-design gate in the PR body. The existing mechanism is `collect` reading `stored_extraction(envelope)` as a mutable list. The change freezes that list once. No durable state mutates. The problem report, actions and problem ids stay identical.
- [ ] In `collect`, wrap the stored extraction once with the existing `freeze` and pass that one object to every consumer.
  - [ ] Keep the `extraction_record` that `ExtractedFragments` carries, because `decision_graph_v1.py` and `prepared_source_views_v1.py` read it. A unit case asserts it survives freezing.
- [ ] In `preserve_fragments`, return a `FrozenList` unchanged, as it already does for `SourceFragments`.
- [ ] In `_read_source_blocks`, reuse the scope entry when the input is the same `FrozenList` object as the entry's input, before the deep comparison. Keep the deep comparison for every mutable input.
- [ ] Do not add a second reader of the prepared source views. Appendix B records why.

**You see.**

- [ ] `request_finished` for `GET /source-selection?document=...` on the 2,000 paragraph fixture reports `source_reconstruction_built` of at most 2 and `source_input_compared` of at most 2, and the phase `source_reconstruction` stays under 1,000 ms inclusive.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_formation_source_read_once.py` gains a case that the problem report from a frozen input equals the report from the trunk mutable input, literal ids included. Run `python -m pytest -q tests/test_formation_source_read_once.py`.
- [ ] The same file gains a case that an in-place edit of a mutable input still selects a new entry, so mutation detection is kept. Run the same command.
- [ ] Existing source reuse and instrumentation suites stay green. Run `python -m pytest -q tests/test_navigation_source_reuse.py tests/test_a1_instrumentation.py tests/test_source_dispatch_hardening.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `inherit-parent` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Open `GET /source-selection?document=<sid>` for the 2,000 paragraph fixture at trunk and head. Save `regression.json`. Pass when the problem ids and status lines are identical and head reports `source_reconstruction_built` of at most 2.
- [ ] Lane 2. Open a document with formation rejections. Save `rejections.json`. Pass when every rejection from trunk appears with the same id and action URL.
- [ ] Lane 3. Open a document whose processing is running. Save `running.json`. Pass when the progress line and the 5 s refresh script are present and the status is 200.
- [ ] Lane 4. Open the overview without a document. Save `overview.json`. Pass when no `source_reconstruction` phase occurs.
- [ ] Lane 5. Open as a reviewer who is not named. Save `not-named.json`. Pass when the error code equals trunk's `reviewer_not_named_on_snapshot`.
- [ ] Lane 6. Open a decision tree class document. Save `boom.json`. Pass when the status is 200 and the output equals trunk.
- [ ] Lane 7. Open a legacy document without a stored extraction. Save `legacy.json`. Pass when the output equals trunk and no exception is recorded.
- [ ] Lane 8. Open `task=disposition` for the same document. Save `disposition.json`. Pass when the output equals trunk.
- [ ] Lane 9. Open the same document twice in a row. Save `twice.json`. Pass when both requests report the same counters, so nothing is cached across requests.
- [ ] Lane 10. Open the same document from two concurrent clients. Save `concurrent.json`. Pass when both return 200 with identical problem ids.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Inclusive ms of the phase `source_reconstruction` and total `elapsed_ms` for `GET /source-selection?document=<sid>` on the 2,000 paragraph fixture.
- [ ] Probe. Five interleaved runs at trunk and head with `evidence/974-design/prototype_source_reads.py` adapted to the HTTP route, vetted with the benchmark-checklist skill.
- [ ] Baseline. Record the trunk value first. The prototype measured 26 to 29 ms per validator read, about 25 s for 945 reads.
- [ ] Rule. Head `source_reconstruction` must be at most 1,000 ms and at most 10 percent of trunk. A head value above either number fails.

**Review gate.** None. P1 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator merges P1, then deploys it per `docs/agents/deployment-protocol.md` and records `deployment_verified` plus one production Vorming open in #974.

## Attribute database JSON bytes to the phase that read them (P2)

**Depends on.** None.

**Files.**

- [ ] Edit `src/console_performance_v1.py`.
- [ ] Edit `src/request_diagnostics_v1.py`.
- [ ] Edit `docs/telemetry/README.md`.
- [ ] Edit `docs/diagnostics/worker-abort-incident.kql`.
- [ ] Edit `tests/test_request_diagnostics.py`.

**Build.**

- [ ] In `JsonBytesLoader.load`, report the byte count to the request evidence as well as to the existing total.
- [ ] In `RequestEvidence`, add the bytes to the innermost active phase path, reserving bounded buckets for unphased and overflow bytes under the existing `MAX_TREE_NODES`, and emit the map as `db_json_bytes_by_phase` in `request_finished`.
- [ ] Project the new field in the `slow_reads` query and document it in the telemetry README. No SQL text, ids or values enter telemetry.

**You see.**

- [ ] `request_finished` for `GET /review?document=<sid>` contains `db_json_bytes_by_phase` whose values sum to `db.db_json_bytes`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_request_diagnostics.py` gains a case where a phase loads a 1,000,000 byte JSON value and the map attributes exactly 1,000,000 bytes to that phase. Run `python -m pytest -q tests/test_request_diagnostics.py tests/test_a1_instrumentation.py tests/test_telemetry_quality_v1.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `inherit-parent` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Open `GET /review?document=<sid>` at trunk and head. Save `regression.json`. Pass when `db_json_bytes` matches within 1 percent and head adds `db_json_bytes_by_phase`.
- [ ] Lane 2. Open the same page on the 2,000 paragraph fixture. Save `review-document.json`. Pass when the map names `review_render/source_views_read_records` and `document_load` and sums to the total.
- [ ] Lane 3. Open `GET /source-selection?document=<sid>`. Save `formation.json`. Pass when the map sums to the total.
- [ ] Lane 4. Post a Review save. Save `save.json`. Pass when the map sums to the total and the status equals trunk.
- [ ] Lane 5. Open a page that reads no JSON. Save `no-json.json`. Pass when the map is empty and the total is 0.
- [ ] Lane 6. Force more phase paths than `MAX_TREE_NODES`. Save `truncated.json`. Pass when the map is bounded, truncation is explicit, and the sum including unphased/overflow buckets still equals the request total.
- [ ] Lane 7. Raise a ConsoleError mid-request. Save `error.json`. Pass when the map is still emitted with the error code.
- [ ] Lane 8. Read the emitted event text. Save `privacy.json`. Pass when no snapshot id, object id or SQL text appears.
- [ ] Lane 9. Run two concurrent requests. Save `concurrent.json`. Pass when each map sums to its own total.
- [ ] Lane 10. Run the `slow_reads` KQL against the receipts converted to log lines. Save `kql.json`. Pass when the new column is projected.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Median `elapsed_ms` of `GET /review?document=<sid>` on the 2,000 paragraph fixture.
- [ ] Probe. Ten interleaved runs at trunk and head, vetted with the benchmark-checklist skill.
- [ ] Baseline. Record the trunk median first. The prototype measured 1,943 ms and 24,072,517 JSON bytes.
- [ ] Rule. Head median may exceed trunk by at most 2 percent. More fails.

**Review gate.** None. P2 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator merges and deploys P2, then records one attributed production Review open in #974.

## Refuse a disposition conflict before command preparation (P3)

**Depends on.** None.

**Files.**

- [ ] Edit `src/review/closed_review_loop_v1.py`.
- [ ] Edit `src/review/review_closure_v1.py`.
- [ ] Create `tests/test_review_disposition_precheck.py`.

**Build.**

- [ ] Confirm the console MRO order of `review_object` and record it in the PR body.
- [ ] Extract the existing `ALLOWED_FINAL_BY_SUITABILITY` check into one pure function in `closed_review_loop_v1.py` with the same error code and the same `later` exemption.
- [ ] Call that function in `ReviewClosure.review_object` before `execute_review_command`, and keep the existing call inside the command. One rule, one owner function.
- [ ] Leave `support_relation_required` inside the command, because it reads data.

**You see.**

- [ ] `POST /review` with `suitability=geen_kenniseenheid` and an approve decision returns 400 with `review_disposition_conflict`, no `store_transaction` phase and `elapsed_ms` under 300 on the fixture.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_review_disposition_precheck.py` gains a table case for every suitability and decision pair, each asserting the literal outcome of trunk's table. Run `python -m pytest -q tests/test_review_disposition_precheck.py tests/test_review_save_chain.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `inherit-parent` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Post `geen_kenniseenheid` with approve at trunk and head. Save `regression.json`. Pass when both return 400 `review_disposition_conflict` and head has no `store_transaction` phase.
- [ ] Lane 2. Post `mist_context` with approve. Save `mist-context.json`. Pass when head returns the same 400 code without preparation.
- [ ] Lane 3. Post `ja` with approve. Save `allowed.json`. Pass when the save persists exactly as on trunk.
- [ ] Lane 4. Post `alleen_onderbouwing` with approve and no inbound support. Save `support.json`. Pass when the code is `support_relation_required` as on trunk.
- [ ] Lane 5. Post a `later` decision with a suitability. Save `later.json`. Pass when it is deferred as on trunk.
- [ ] Lane 6. Post a conflict and read `workflow.review_events`. Save `no-write.json`. Pass when the event count is unchanged.
- [ ] Lane 7. Post a conflict with a stale revision token. Save `stale.json`. Pass when the response code equals trunk's for the same request.
- [ ] Lane 8. Post revise with `samenvoegen`. Save `revise.json`. Pass when the revision path behaves as on trunk.
- [ ] Lane 9. Post an unknown suitability value. Save `unknown.json`. Pass when the code equals trunk's `suitability_required`.
- [ ] Lane 10. Post a conflict through the MCP review route if it exists. Save `mcp.json`. Pass when the same code is returned without preparation, or the lane records that no such route exists.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. `elapsed_ms` and `db_queries` of a conflicting `POST /review` on the 2,000 paragraph fixture.
- [ ] Probe. Ten interleaved runs at trunk and head.
- [ ] Baseline. Record the trunk value first. Production showed 3.87 s.
- [ ] Rule. Head must be at most 300 ms and use at most one fifth of trunk's queries. More fails.

**Review gate.** None. P3 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator merges P3.

## Remove the cause of the aborted Review saves (P4)

**Depends on.** The #975 evidence run, with the exit reason recorded in #974.

**Files.**

- [ ] Edit the module that holds the frame named by `worker_lifecycle.json`, or the command input reader if the evidence shows a memory kill.
- [ ] Create `tests/test_review_save_event_loop.py`.

**Build.**

- [ ] Reproduce first. Run `POST /review` on a fixture with the production fragment count while an asyncio probe in the same loop records the largest gap between 50 ms ticks.
- [ ] If the evidence shows `WORKER TIMEOUT` with a stack, remove or shrink the work in the deepest Metis frame that held the GIL. Apply the mantras in order, do not do it, do not do it again, do it less.
- [ ] If the evidence shows a memory kill, bound the command inputs to the affected objects and their lineage, using the existing windowed readers.
- [ ] If the evidence shows neither, stop and record the gap in #974. Do not ship a guess.
- [ ] Do not add or raise a gunicorn `--timeout`. That hides the stall and keeps the single worker blocked.

**You see.**

- [ ] The probe reports a largest event-loop gap under 1,000 ms during the save, and `request_finished` is recorded for every save.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_review_save_event_loop.py` fails at trunk with the measured gap and passes at head. Run `python -m pytest -q tests/test_review_save_event_loop.py tests/test_review_save_chain.py tests/test_prepared_review_batches.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `inherit-parent` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Save one decision on the large fixture at trunk and head. Save `regression.json`. Pass when head records `request_finished` and the probe gap is under 1,000 ms, and the stored event equals trunk's.
- [ ] Lane 2. Save five decisions in a row. Save `five.json`. Pass when all five finish and all five events are stored.
- [ ] Lane 3. Save while another client opens Review. Save `parallel-read.json`. Pass when the read is served before the save finishes.
- [ ] Lane 4. Save with a stale revision. Save `stale.json`. Pass when the code is the same 409 or 400 as trunk and nothing is written.
- [ ] Lane 5. Save a revise decision. Save `revise.json`. Pass when the revision is stored as on trunk.
- [ ] Lane 6. Save a batch confirm. Save `batch.json`. Pass when the batch hold stays under the existing 250 ms limit.
- [ ] Lane 7. Save the last open passage. Save `last.json`. Pass when the redirect target equals trunk.
- [ ] Lane 8. Kill the worker after COMMIT in a test hook. Save `after-commit.json`. Pass when the exact test command/interaction has its expected committed decision, binding and ledger evidence in PostgreSQL. The diagnostic window script remains observational (`not_determined`).
- [ ] Lane 9. Kill the worker before COMMIT in a test hook. Save `before-commit.json`. Pass when the exact test command has no committed mutation or ledger event after connection cleanup; compare the stored before/after state, not just a wall-clock window.
- [ ] Lane 10. Run the save under a 1 GB address space limit. Save `memory.json`. Pass when the save finishes.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Largest event-loop gap and `elapsed_ms` of `POST /review` on the large fixture.
- [ ] Probe. Ten interleaved runs at trunk and head with the asyncio probe.
- [ ] Baseline. Record the trunk gap first.
- [ ] Rule. Head gap must be under 1,000 ms and `elapsed_ms` must not exceed trunk. Either miss fails.

**Review gate.** None. P4 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator merges and deploys P4, then reruns the #975 collection for one working day and records zero aborted saves in #974.

## Bound the Review document read (P5)

**Depends on.** P2 merged and deployed, plus one attributed production Review open.

**Files.**

- [ ] Edit the reader named by the largest entry of `db_json_bytes_by_phase` in production, expected `review_render/source_views_read_records` or `document_load`.
- [ ] Create `tests/test_review_document_read_budget.py`.

**Build.**

- [ ] If the source views read dominates, render the document page from the existing card facts in `workflow.review_object_facts`, or read the source views windowed by the visible objects with the existing `references(objects)` path.
- [ ] If the envelope read dominates, read the metadata columns needed for authorization and class instead of `console._envelope`.
- [ ] Keep every authorization and fail-closed check of the current path.

**You see.**

- [ ] `GET /review?document=<sid>` on the 2,000 paragraph fixture reads at most 2,000,000 JSON bytes.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_review_document_read_budget.py` asserts the byte budget and the literal rendered card list against trunk. Run `python -m pytest -q tests/test_review_document_read_budget.py tests/test_review_workboard_queue_links_v1.py tests/test_review_direct_workspace_v1.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `inherit-parent` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Open `GET /review?document=<sid>` at trunk and head. Save `regression.json`. Pass when the card list is identical and head reads at most 2,000,000 JSON bytes.
- [ ] Lane 2. Open as a reviewer who is not named. Save `not-named.json`. Pass when the redirect equals trunk.
- [ ] Lane 3. Open with `task=batch`. Save `batch.json`. Pass when the output equals trunk.
- [ ] Lane 4. Open with an object. Save `object.json`. Pass when the passage read stays within its existing budget.
- [ ] Lane 5. Open with `after=<object>`. Save `after.json`. Pass when the next object equals trunk.
- [ ] Lane 6. Open a decision tree class document. Save `boom.json`. Pass when the output equals trunk.
- [ ] Lane 7. Open a document with a corrupt source root. Save `corrupt.json`. Pass when it fails closed with trunk's code.
- [ ] Lane 8. Open with `q` and `page`. Save `paged.json`. Pass when the links equal trunk.
- [ ] Lane 9. Open as a non-reviewer. Save `overview.json`. Pass when the overview equals trunk.
- [ ] Lane 10. Open twice. Save `twice.json`. Pass when both reads stay within budget.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. `db_json_bytes` and median `elapsed_ms` of `GET /review?document=<sid>` on the 2,000 paragraph fixture.
- [ ] Probe. Ten interleaved runs at trunk and head.
- [ ] Baseline. Record the trunk value first. The prototype measured 24,072,517 bytes and 1,943 ms.
- [ ] Rule. Head must read at most 2,000,000 bytes and take at most half of trunk's median. Either miss fails.

**Review gate.** None. P5 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator merges and deploys P5 and records one production Review open in #974.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names, and post the session handoff on MET-48.

## Appendix A. Prototype evidence

Both prototypes ran on 2026-11-04 on branch `ccr-fc816d1f-mljiu0` at main `1f9deea`, Python 3.13 and PostgreSQL 16, with an ingested HTML document of 2,000 paragraphs.

`evidence/974-design/prototype_source_reads.py` compared three ways to read the full source view through `_read_source_blocks`.

| Variant | Per read | One-time cost | Extra JSON read | 945 reads |
|---|---|---|---|---|
| Trunk, mutable list | 26 to 29 ms | none | none | about 25 to 27 s |
| A, prepared carrier | 0.002 ms | 535 to 617 ms | about 6.3 MB of source views | about 0.6 s |
| B, frozen list, identity reuse | about 0 after the first | one reconstruction, about 0.6 s, plus 27 to 32 ms freeze | none | about 0.6 s |

The trunk number demonstrates comparable repeated-comparison cost on this synthetic fixture; it does not reproduce the real 923-fragment incident timing. The envelope plus carrier read measured 15,225,370 JSON bytes. The envelope alone measured 8,952,657.

`evidence/974-design/prototype_review_open_bytes.py` opened `GET /review?document=<sid>`. It read 24,072,517 JSON bytes in 15 queries and took 1,943 ms. The largest phases were `review_render` at 1,705 ms, of which `source_views_read_records` took 963 ms and `source_accountability` 454 ms, and `document_load` at 149 ms.

Unproven. The exit reason of the aborted saves, which P4 needs. Whether production bytes split like the fixture, which P5 needs. KQL from #975 has not run against the live workspace.

## Appendix B. Alternatives rejected

- P1 option A, reading the prepared source carrier in Vorming. It is as fast as B, but adds about 6.3 MB of JSON to every Vorming open, which is the cost P5 removes from Review.
- P1 option, passing precomputed blocks through every validator. It threads one parameter through many call sites and repeats a decision that the reconstruction scope already owns.
- P1 option, weakening the deep comparison to identity for every input. It drops mutation detection for mutable inputs.
- P4 option, raising the gunicorn timeout or adding workers. Both hide the stall. A second worker is a topology decision for the operator, not a fix.
- P3 option, validating at the HTTP route only. Other callers of `review_object` would still prepare first.

## Appendix C. Risks

- P1. A consumer of the frozen list that mutates it now raises `source_views_carrier_immutable`. Review already passes immutable carriers to the same validators, which lowers the risk. Lane 1 and the unit suite watch for it.
- P1. Freezing an `ExtractedFragments` list must not drop its `extraction_record`. The nested build box and its unit case guard it.
- P2. Attribution runs in the JSON loader on every load. The perf rule bounds the overhead at 2 percent.
- P3. A duplicate rule would drift. The single pure function prevents that.
- P4. The fix depends on evidence that may be missing because of retention or diagnostic settings. The plan stops instead of guessing.
- P5. Card facts may lack a field the document page needs. The literal card list comparison in lane 1 catches it.
- Effective worker count and timeout must be checked in the runtime. A worker restart can interrupt other requests; the scope and duration of console unavailability are not established by the five missing finishes.

## Appendix D. Links and reading list

- Issue https://github.com/WilliamGomes41/Metis-DS/issues/974 and PR https://github.com/WilliamGomes41/Metis-DS/pull/975.
- `docs/change-contracts/974-worker-abort-incident.md` and `docs/diagnostics/worker-abort-incident.md`.
- `docs/agents/abstraction-boundaries.md` before P1 and P5. `pstack/skills/how/SKILL.md` for P1, P4 and P5. `pstack/skills/interrogate/SKILL.md` for P4.
- The decision trail per `pstack/skills/show-me-your-work/SKILL.md` stays local unless the operator asks for it.
