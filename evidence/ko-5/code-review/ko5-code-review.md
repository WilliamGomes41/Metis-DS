# Independent KO-5 code/adversarial review

**PASS within code-review scope at final candidate 988e844f428b907e60658e9f2df7ccec498ae912 (runtime source byte-identical to independently reviewed 545b9e4790f9b36e47f0dc3710deb9c01dc9258c). KO5-CODE-01 is closed with executed red/green evidence. No open demonstrated material defect.** This is not merge/deployment authorization. Overall closure still requires separately owned exact-head CI, native lifecycle, actual old-image rollback and performance receipts.

## Target and boundaries

Initial review: runtime 44de81337eeff3d83ebca651d088b678e8c7d9a6 in /workspace/Metis-ko5-verify against base 07db5080666f0428a454f5a705e50825a4fc5506. Also inspected docs extension fe16972238450005b632a9a1abd161a64b0397cb through git show.

Reopened review: complete 44de..545b9e diff, immutable /workspace/Metis-ko5-verify-fixed, confirmed exact HEAD. No source edits, deployments, external writes, production metadata or additional agents. Read AGENTS, continuous-development, lifecycle VSA and KO5 contract; applied repository dispatcher, code-quality-review and risk-proportional-verification. Class A/high rewrite risk.

## Closed finding KO5-CODE-01 — P2 kernel task-count API returned phantom tree work

Original locations: src/workflows/workflow_badge_counts_postgres_v1.py:72 and src/operations_console_v1.py:1043 at 44de. Both counted any non-document needs_review/revise row, including closed contextual headings.

Native proof /workspace/ko5-native-evidence/phantom-tree44de.json shows published ordinary snapshot snap-26800737fd3dfb67-5006c854 with review/source closure complete, zero first/second/repair duties, no unresolved passages, and four used_as_context headings still needs_review. Fully ready unpublished high-risk snapshot snap-1d875240a6a8d120-e6090523 similarly has publication_ready=true, no duties/blockers and one contextual heading triggering the predicate. At least two of three observed tree contributions were phantom work. The initial PASS was withdrawn when this evidence arrived.

Precision correction: this was an erroneous kernel waiting_task_counts API result. It was not an observed rendered navigation badge. src/operations_console_app.py:845 _nav builds plain links and does not consume waiting_task_counts; repository search finds only the two implementations, and the existing V212 test explicitly requires no automatic navigation badges. Earlier wording implying users actually saw this count rendered is withdrawn.

545b9e retires the obsolete Documenten/global-review counter in both implementations. The response retains tree:0 for every role. The existing personal Review projection remains responsible for real assigned work, and its counting code is unchanged. This is consistent with Documenten being a catalogue rather than a second Review queue. It adds no reader, query, SQL rule classifier, global materialization, readiness call or new queue. Existing clinical storage/serialization remains inert.

Independent executed closure proof:

- Corrected-head focused suite: new real fixture in legacy and compact modes, aggregate constant-round-trip test, and existing V212 no-automatic-navigation-badges test: **5 passed** (4.94s).
- Copied the new regression outside either source tree to /workspace/ko5-review-tests/test_fixed_badge.py and ran it against 44de: **2 failed**, both at tree 1 != 0.
- Adapted only that isolated review copy to bypass the initial open-work tree assertion, allowing the actual closed-work trap to execute. Against 44de both legacy/compact cases reached curation_ready/review_complete/source_passage_review_complete/publication_ready=true with retained used_as_context headings, then failed tree 1 != 0: **2 failed** (2.07s). Failure was a domain assertion, not setup/import failure.
- Ran that same isolated closed-work probe against 545b9e: **2 passed** (2.31s), proceeding through actual canonical publication as well. The test also proves open assigned Review count remains positive before closure, becomes zero after closure, all roles get tree:0, forged review_passes/true clinical mirror cannot change outcomes, and readiness/publication gates are not invoked by counting.

This demonstrates closure of the actual counterexample, including ready unpublished and published states, without hiding legitimate work in the existing Review queue.

## Other reviewed boundaries

These initial-review checks remain unaffected by the narrow 545 runtime delta (only tree counting changed):

- Missing/None bindings including boom no longer authorize from second-review mirrors. Exact version/hash/type/domain and unique-human approval matching remain the owner.
- Removing mirror publication sealing retains historical content/identity/lineage guards. The locked canonical release-history storage boundary remains; native direct/base/MRO and published immutability tests passed.
- Review-pass envelope merge retirement retains unchanged-envelope validation, object CAS, append order, frontier/current validation, binding authorization locking and document revision increment.
- Processing/resume guard retirement retains actual bindings, human terminal decisions, reviewed passage-register evidence and source role/context evidence. Actual retry/concurrency tests passed.
- Second approval adds exact authorization/audit without mirror completion synchronization. New successor compatibility shape is reconstructed by the revision owners; schema and stale-mirror successor tests passed.
- Canonical-store absence fails closed for lifecycle and badge registry readers; envelope serving fallback is gone.
- Source-role writers remain separate and #942 remains open. No claim of completed source-context consolidation.
- Inventory now marks removed SQLite pilot/wrapper and obsolete review/migration symbols LEGACY-REMOVED, drops obsolete direct CLI status and related callers. The active private review transformer remains identified. Docs describe inactive tree compatibility slot and unchanged Review ownership.

## Initial executed evidence retained with bounds

Environment: /workspace/.venvs/metis-ds/bin/python, actual PostgreSQL17 server 127.0.0.1:55440, disposable fixture databases. scripts/test_postgres.sh passed before initial and corrected-head PG execution. An initial system-Python preflight lacked psycopg and was corrected; one initial pytest command had a nonexistent filename and ran no tests, not counted.

1. At 44de: test_ko_single_way.py, test_revision_frontier_store_v1.py, test_console_badge_counts_postgres_v1.py: **41 passed** (16.69s).
2. At 44de: test_published_working_revision_immutable_2b_postgres.py, test_d5_3a_binding_aware_review_duty.py, test_prepared_source_resolution.py, test_workflow_postgres_concurrency.py, test_processing_retry_postgres.py, test_t12_publication_readiness_authority.py: **56 passed** (39.34s).
3. Independent /workspace/ko5-review-tests/test_adversary.py at 44de: **2 passed** (2.02s). Let the first real merge policy call complete, then refused on the second: physical objects/bindings/envelope and events unchanged, event buffer/active review state reset. Restored extra authorization-contract blocker after complete native review and proved readiness refused.

These are 99 initial passing tests, not 99 tests rerun at 545. The focused corrected-head suite and independent red/green probes above cover the changed boundary. No skips. Deprecation and unknown-marker warnings only.

## Test deletion assessment and remaining limits

SQLite/CLI and blocked public JSONL tests are obsolete with their APIs; hash callers moved to integrity_kernel. Native refusal/hash/tuple/history checks remain. The earlier nonblocking observation about three non-SQLite D-SEC-3 tests is resolved at final commit 988e844f428b907e60658e9f2df7ccec498ae912. Independently compared the complete restored D-SEC-3 section with base 07db5080: byte-identical. The final commit changes only that test file; git diff --exit-code 545b9e..988e844 -- src succeeded with no runtime changes. Extracted the final test artifact outside the source tree (/workspace/ko5-review-tests/test_restored_security.py) and independently ran all three restored tests against the source-identical 545 runtime using actual PostgreSQL fixtures: 3 passed in 1.49s, no skips. This verifies permanent coverage is restored without pilot helpers or imports; it is not a broad full-suite rerun at final head.

No separate old-image driver, complete lifecycle closure, Azure adapter exercise, PG16 run, full CI or performance benchmark was performed in this review; those remain separate required receipts. PASS is bounded to this source/adversarial review and its executed evidence.



## Subsequent auto-review follow-up — active offline prepublication CLI (not covered by prior PASS)

A later GitHub auto-review identified an additional active caller boundary. Independent source tracing confirms src/cli.py:10 imports the offline evaluate function; cmd_prepublish at68 and cmd_audit_current at79 call it without bindings/review_path. The standalone wrapper src/prepublication_gate_v3.py remains executable. Its evaluate at src/publication/prepublication_gate_v3.py:23 calls publication_errors with no bindings. At src/publication/eligibility_policy.py:30, exact_current_approver_ids(obj, bindings or ()) must therefore return empty and append object_tuple_required for every nonexcluded object. This is a deterministic reachable failure of the advertised offline publication verdict. The tests at test_protocol_v2.py:125 only check existing BLOCKED input and do not expose lost PASS.

The gate is declared ACTIVE-RUNTIME/direct_cli at lifecycle inventory208, documented in publication-layout22/39, called by CLI prepublish and audit-current, and audit-current is called from both integrity/protocol scripts. It is not a zero-caller dead module. No ASGI/console/publication writer imports this offline gate: supported native readiness uses its separate existing publish_authorization_contract owner.

Do not infer missing authority from governance mirrors, treat supplied standalone JSON bindings as durable truth, or preserve a misleading PASS verdict by dropping the binding check. The smallest coherent choices are explicit retirement of this obsolete file-based verdict and its active command/audit projection, or a real snapshot command through the configured production-console readiness owner. Retirement must be caller-visible and include callers/inventory/current documentation, rather than silently disabling a gate. Native publication authorization must remain unchanged.

Current publication-layout also still promises the deleted SQLite wrapper, and infrastructure_manifest.v1.json:114/284 calls SQLite the executable/reference runtime, with removed canonical_store paths127/297. These are current-topology claims requiring correction; frozen protocol history should remain historical.

This follow-up is independently grounded source/caller evidence, not another broad verification pass. Prior PASS applies only to the stated reviewed boundaries and is insufficient to close this newly identified CLI boundary. Owner correction and exact-candidate follow-up evidence are pending.


## Root follow-up: offline verdict retirement, 28024ef3
Independent source diff/caller review: src.cli prepublish dispatcher/parser/import and both offline gate entrypoints/eligibility owner removed together. audit-current retains its existing schema/hash/source-fragment/parent integrity loop and existing status meaning; publication_gate/publication_blocker_count projection removed. Active publication-layout and infrastructure manifest now describe existing PostgreSQL implementation, without asserting live Azure provisioning. Native console/ASGI readiness owner unchanged. Removed offline-only test does not remove the independent D-SEC-3 assertions restored earlier.
Executed five actual subprocess cases from test_ko_single_way.py -k offline_: 5 passed,18deselected,0.56s, no skips. CLI command is refused, both deleted module entrypoints fail visibly, no output verdict file; intact audit PASS, unstamped altered content BLOCKED. Command cwd was owner worktree at28024, then only uncommitted fixture diffs and later unrelated review-command fix; no CLI/test runtime edits occurred during that invocation. Detached28024 source snapshot created at /workspace/Metis-ko5-final-verify. This is bounded CLI proof, not a fresh complete native/browser/performance verdict. New prepared m2 race fix and remaining CI failures still pending independent final review.

## Root independent final-runtime review, 9cf97451
Clean detached /workspace/Metis-ko5-final-verify at9cf974518d2e82939247f47e0f0ba59172131346. Independently reviewed complete545→9cf delta: CLI retirement above, preserved three D-SEC-3 tests, stronger m2 prepared-command refusal using the already-read preparation/locked document counters; no additional query or token format. m2 remains objectset token; this closes the demonstrated intervening binding-only race during preparation, not a new claim about a standalone binding change before the command begins. Generation checks, unconditional semantic duplicate behavior, W1 preparation and objectset comparison remain.
Executed exact-candidate real PostgreSQL17 proof: test_review_command_freshness_v1 same-version binding race all3generation/m2/unconditional variants, T11 legacy history plus actual canonical-native writer seal with physical no-write assertion, D5 pinned629 code rollback durable+Azure, entire23-case single-way suite:29passed35.95s,0skips. D5 exception is bounded to ONE target successor envelope: current review_passes must be unchanged from before; old code must produce exactly one actual approval-matching actor/object/passed/time tick before excluding only that expected inert tick. All other exported durable/product state stays in the exact comparison. Root independently computed the old545 failing raw recursive difference to prove this scope; no blanket mirror normalizer or relaxed lifecycle assertion.
The prior attempted accept-successor mirror-only test change was rejected by automatic approval review and never executed. Safer implemented proof preserves rejection at actual durable canonical release authority and proves physical state unchanged; no production seal guard relaxed. A separate obsolete-method caller in test_published_working_revision_immutable_v1 was found by root old545shard0 after this29run; owner updating that test only while preserving restart/revise/refusal assertions. Full CI/fresh automatic review remain mandatory and pending.

Root additional final test-artifact verification: both complete restart modules at clean7a81614c (src byte-identical9cf) independently20passed17.30s,no skips. Removed migrator calls now assert APIabsence while preserving canonical rejection and complete historical objects across actualstartup; selected source closure/action/objectfacts remain identical for revise too. Fresh actualKO4sameDBold-second-review mutation on9cf also passed; detailed independent REPORT-9cf.md. Final performance protocol on9cf passed, all raw metrics independently recomputed and actual ordinary DOM confirmed. Full final CI/automatic review still pending.
