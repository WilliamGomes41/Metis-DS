Change class: A
Promise: Reviewers/publishers can oversee all review work and safely add, replace or archive participants without deleting source work, losing other reviewers' valid evidence or bypassing required independent review.
Proof: HTTP overview/filter/read-only authorization plus local/native PostgreSQL add/archive/replace/restart/publication race and rollback chain.
Touches lifecycle invariants: yes
Rewrite risk: high

User explicitly approved the domain proposal and requested implementation in GitHub. No merge or deployment.

Lifecycle entity: Existing WorkingRevision with versioned review policy, participation history and exact object/graph review evidence.
Lifecycle transition: Given an unpublished revision, an authorized participant command atomically changes current participation/requirements and records history; unrelated exact approvals remain valid, a replacement must personally approve, archived required duty remains open until replaced.
Initial durable state: Existing local/native workflow revision with legacy or explicit-review-v1 policy and potentially existing approvals.
Trigger: Authenticated add_optional, add_required, replace, archive or self-escalation command with command ID, expected revision and reason.
Authorization: Assigned reviewer may add another optional reviewer. Publisher may add required, replace/archive and self-assign; self-assignment requires reviewer role. All target active participants must be enabled human reviewers. Legacy activation requires publisher.
Validation: Open unpublished revision; current revision; unique active identities; primary replaced atomically; archived required duty retained; replacement cannot duplicate another active/required identity; no reduction of requirements through these commands.
Mutable entities: Working envelope policy/history, nonclinical governance projection, document revision used for CAS, affected actor's current approval eligibility and command audit.
Immutable entities: Source bytes; canonical clinical payload/hash and object version for unchanged passages; original decisions/authors; published work/releases and registry.
Workflow state before: Processing/in_review/ready or technically blocked but unpublished.
Workflow state after: Readiness recalculated from current requirements; unfilled archived required duty blocks publication; no new approval manufactured.
Release state before: Prior release may exist and be active.
Release state after: Unchanged by participation commands.
Serving state before: Existing publication registry decides serving.
Serving state after: Unchanged until separate authorized publication.
Expected API result: Result with current membership/revision; no mutation by outsider, replay returns prior result; stale/conflicting replay rejected.
Expected UI result: My/all and theme filters; authorized read-only trajectory details with participants, passages/graph/history; controls according to role; reason required and archive/replacement effects visible.
Failure result: No partial membership/object/audit writes; prior state retained; stale worker cannot overwrite new membership.
Restart result: Same assignments, archived history, evidence eligibility and readiness on independent runtime.
Recovery result: Existing workflow backup/recovery retains envelope/object governance/audit; no identity transfer or recreated decision.
Legacy-data result: No startup/backfill or published mutation. Publisher explicitly activates managed participation; original named reviewers remain obligations, existing legacy independence floor retained, historical evidence stays bound to exact tuples.
Required black-box scenario: Ingest/review -> optional add retains other evidence -> required reviewer unavailable -> archive blocks -> replace -> replacement personally approves passages/graph -> publish -> restart; existing earlier release/history unchanged.
Explicit non-goals: Account deletion, production data changes, new roles, autonomous requirement waivers, merge/deployment, new source extraction algorithms.

Rewrite target: Participant administration and its authorization/readiness boundary, with opt-in managed-review-v2 semantics.
Why local patching is insufficient: Existing policy command invalidates every object and graph approval and requires existing assignment even for publisher; buttons alone cannot preserve work or recover absent reviewers.
Current authority/writer/reader map: Workflow documents envelope owns current policy and history; object governance stores checked projection. Immutable metadata remains original review basis. OperationsConsole commands and decision review commands are writers through existing local atomic store/native shared transaction; graph/primary/second/source-context/batch/reextract/class-change writers retain same guards. ReviewDuty, four_eyes, publish authorization, readiness, SQL badge fallback, UI/MCP/export and canonical graph release read projections; canonical registry remains sole serving authority. Startup/reconcile does not create participation decisions.
Supported runtime topologies: Local file-backed compatibility and native workflow/canonical PostgreSQL with independent runtime instances; production immutable sources remain Azure. No new stores or topology changes.
Persisted-state impact: Additive managed policy in envelope and governance projection; archived participation history; immutable review_basis for existing graph target. Governance excluded from canonical content hash by existing kernel. Schema accepts bounded new governance field; no SQL migration.
Compatibility/migration plan: Explicit command activates v2 only on unpublished work; retain v1 and absent-policy readers. v1 metadata stays hash-bound unchanged as historical basis, v2 governance projection must exactly match envelope before publication; compare objects and basis on transition. No approval rebinding or changed reviewer attribution.
Rollback/recovery plan: Before activation code rollback possible; after managed records exist keep compatible reader, disable new administration or restore consistent backup under controlled recovery. Old binaries must not operate on managed records. No destructive migration.
Cutover trigger: Explicit authorized participant command with reason on one current work revision after tests pass.
Cleanup/decommission criteria: No v1/legacy deletion in this change; any later removal separately authorized/proven.
Failure blast radius: One unpublished working revision; previous serving release untouched.
Adversarial proof matrix: Direct endpoints/commands, outsider and publisher-only assessment, archived/blocked users, unchanged approvals, archived required approval cannot satisfy vacancy, re-add does not resurrect past participation, duplicate/replay conflict, stale update, concurrent publish, late extraction, native rollback after writes, restart, published immutable, SQL badges, source/hash and graph change still invalidate evidence, generic policy editor cannot bypass managed requirements.


Verification (2026-10-01)

- Base: main 2d607f5200fab0770a912e1efa1c8837d42392c4; branch review-participation-management.
- Full pytest suite: 2438 passed, 5 dependency warnings in 165.44 seconds on Python 3.12.14 and native PostgreSQL 17.11. METIS_TEST_POSTGRES_DSN pointed to an isolated local synthetic test database.
- New lifecycle coverage: tests/test_review_participation_management.py; existing graph/native concurrency/read-path tests updated for the new authorized contract.
- Repository preflight, compilation and Product API backward compatibility passed. Release-control mapping is checked again against the committed diff.
- Separate adversarial review checked the obsolete policy mutation entry points, direct endpoint authorization, required archived vacancies, evidence identity, re-add behavior, published immutability and shared native transaction boundary. Those scenarios have command/HTTP/native regression coverage.
- Browser rendering was not visually verified: the browser-engine download failed at the environment proxy. HTTP tests cover filters, read-only access and participant forms.
- No SQL migration, production processing, merge or deployment. Issue creation was rejected by automatic approval review because the user had not authorized creating an issue; the execution contract is recorded in this file and the PR instead.

Operational compatibility

Existing v1 and legacy records stay readable. Participation changes explicitly opt unpublished records into managed-review-v2. Generic change_review_policy commands now reject with managed_participation_command_required; clients must use manage_review_participation with command ID, expected revision and reason. After activation, keep a compatible binary or restore a consistent backup; an older binary must not write managed records.

UX completion scope (2026-10-01)

This follow-up is Class B, rewrite risk none: presentation/navigation only, with no new durable transition or authority. Existing participation commands remain the sole writer and authorization boundary. The UI reads accounts, envelope policy and bindings, offers only choices allowed by those existing rules, translates labels/errors and restores navigation. Source, identities, approvals, history and command semantics remain unchanged. Proof: rendered-form choices and forged-request rejection, readable detail/history labels and links, followed by browser actions on synthetic data.

UX completion evidence

- Full local suite: 2441 passed, 5 dependency warnings, 166.52 seconds; targeted participation/workspace/workboard tests: 33 passed. Native PostgreSQL enabled.
- Browser download blocker resolved by using installed Chromium 151 through agent-browser. Local synthetic data only. Verified all/theme selection, read-only trajectory, publisher required add/archive/replace, reviewer optional add, reason validation, permitted dropdown choices, specific primary-archive rejection and return navigation.
- Desktop and 390px viewport screenshots inspected: readable labels/history and no horizontal overflow on the narrow trajectory. Browser JavaScript error log empty. Authentication through local test accounts; no production or Entra browser test.
- Display-only changes: Dutch lifecycle/status/action/error labels, numbered passage references, standard navigation and return links. Candidate lists use existing reviewer availability validation and existing membership rules; the command service remains authoritative for forged or stale requests.
- Repository preflight, compilation, API compatibility and diff whitespace checks passed. The prior visual-verification limitation above records the earlier attempt; it is resolved by this follow-up.
