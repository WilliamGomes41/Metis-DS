## Agent skills

Voor consoletests eerst `scripts/test_postgres.sh`; nooit PG-tests overslaan.

### Skill selection

For complex or multi-phase work, read and apply [skill-dispatcher](.agents/skills/skill-dispatcher/SKILL.md) before substantive work, and reconsider the route when the task phase, scope, or material risk changes. Use the current available skill catalog and read the selected skills before applying them. Briefly state the selected skills and their purpose; do not require the user to remember skill names.

For bug repairs, normally select `diagnosing-bugs` and `risk-proportional-verification`. Add domain design, workflow-context preservation, or code-surface review when the affected behavior warrants them. Explicitly requested skills and mandatory skill prerequisites remain applicable. Keep simple tasks proportionate, resolve renamed skills through the current catalog, and respect archived and explicit-only restrictions.

The dispatcher selects working methods; it grants no execution, deployment, messaging, or merge permission and does not replace this repository's development or lifecycle contracts. If a required skill is unavailable, report the limitation and continue independent work without claiming that skill was applied.

### Frontend design — Impeccable (mandatory)

For every task that creates or changes frontend, agents MUST read and apply
[Impeccable](.agents/skills/impeccable/SKILL.md) before designing or editing UI.
This includes pages, layouts, components, HTML/CSS, client-side interactions,
responsive behavior, accessibility and user-facing UX copy. Apply it without
requiring the user to name the skill. Backend-only work does not trigger it.
Follow [the project integration](docs/agents/impeccable.md) for launcher setup,
existing brand constraints, verification and an unavailable-engine fallback.
Preserve Metis domain contracts and existing verification requirements; a design
workflow grants no deployment, publication or additional execution authority.

### Shared plugin skills

The reviewed, pinned shared workflows and agent entry points are listed in
[shared-skills](docs/agents/shared-skills.md). The canonical files are in
`.agents/skills/`; Claude adapters reference those same procedures. Use the
selection triggers in that index and reuse existing verification evidence.
Shared skills add working methods, not execution, merge, deployment, or
publication authority. Existing Metis contracts remain authoritative within
this repository; user and host-level instructions still apply.

### Test PostgreSQL

PostgreSQL tests need a server; never treat their skip as a pass. `pytest` starts a disposable one through `scripts/test_postgres.sh` when `METIS_TEST_POSTGRES_DSN` is unset and PostgreSQL 16 is installed. Cloud agents (Codex, Cursor) install it with `scripts/agent_env_setup.sh`. See the test-PostgreSQL section of `docs/STACK_SETUP_BASELINE.md`.

### Issue tracker

Issues live in this repo’s GitHub Issues (`gh` CLI). See `docs/agents/issue-tracker.md`. What agents record in GitHub versus Linear, and the session handoff format: `docs/agents/linear-github-handoff.md`.

### Triage labels

Canonical roles map 1:1 to tracker labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.

### Execution contract

`ready-for-agent` marks a ticket as executable but does not start work automatically. Repository coding runs use the `Metis Engineer` profile in `.github/agents/metis-engineer.agent.md` and follow `docs/agents/execution-contract.md`.

### Continuous development model

Every implementation issue MUST first follow `docs/agents/continuous-development.md`, be classified as Class A (lifecycle core), Class B (normal product behavior), or Class C (cosmetic/documentation/non-semantic maintenance), and state `Rewrite risk: none | high`. Apply the lightest process that safely proves the promise. Do not apply lifecycle-grade governance to Class B/C work that does not alter lifecycle semantics.

Any change that materially replaces or redefines a durable authority, persisted identity/schema semantics, a shared mutation/read boundary, a lifecycle/publication/retrieval kernel, or a migration/cutover that affects restart/recovery is `Rewrite risk: high` regardless of diff size. High-risk work MUST complete the mitigation fields, staged-migration/rollback rules, and adversarial review in `docs/agents/continuous-development.md` before merge.

If a Class B/C implementation reveals that a lifecycle invariant, identity, authority, supersession, withdrawal, migration, or recovery rule must change, STOP and reclassify before continuing. If rewrite risk changes from `none` to `high` during implementation, STOP and rescope before adding more code.

### Class B program-design gate

Before implementing a Class B change that alters shared extraction, review, retrieval, semantic, persistence, or cross-layer behavior, the agent MUST trace the existing execution path and state:

- the existing mechanism and authority;
- the intended behavioral change;
- the affected functions, types, and call path;
- which state may mutate and which state must remain unchanged;
- behavior that must remain unchanged;
- the smallest observable proof of the change.

The agent MUST map the requested behavior onto the existing program structure before editing production code. If the current mechanism, ownership boundary, or call path is not established, investigate first instead of patching. This gate is a lightweight design check for Class B work and MUST NOT be expanded into lifecycle-grade paperwork when lifecycle semantics are unchanged.

For Class B work that creates or mutates durable domain state, apply the `Stateful Class B domain-first overlay` in `docs/agents/continuous-development.md` before VSA. That document owns the criteria and escalation rule.

### Lifecycle VSA contract

Class A issues MUST also follow `docs/agents/lifecycle-vsa.md` in full. Class A includes changes to logical document/version lineage, source snapshot immutability, review closure required for publication, publication readiness semantics, canonical releases, serving authority/active serving set, supersession, withdrawal, published-state migration/reconciliation, or restart/recovery of lifecycle state.

For Class A, the lifecycle transition MUST be specified before code changes. A technical component, status, page, database column, helper, or migration is not by itself a vertical slice. Published work is immutable; successor work must be modeled as a new WorkingRevision or SourceSnapshot; serving authority remains the publication registry; restart/recovery and a black-box lifecycle proof are part of Definition of Done.

A Class A high-risk rewrite MUST additionally map every relevant authority, writer, reader, runtime/storage topology, compatibility path, cutover, rollback/recovery path, and adversarial bypass scenario before implementation. Green CI alone is not sufficient evidence that the rewrite surface is complete.

If `docs/agents/lifecycle-vsa.md` requires a lifecycle, identity, authority, supersession, withdrawal, migration, recovery, or rewrite-risk decision that the assigned issue does not define, the agent MUST stop and surface the missing decision instead of making an assumption.

### Reuse existing domain contracts

Before changing extraction, review, publication, or persistence, read the relevant owner and proof in `docs/agents/abstraction-boundaries.md`. Reuse the named domain operation instead of adding a parallel gate, status writer, or authority. Add an abstraction only when it enforces a named invariant or removes demonstrated duplication. Keep runtime decisions in code, not in agent instructions.

Run `python scripts/check_architecture_boundaries.py` before opening a PR. CI rejects Docling SDK imports outside the worker and infrastructure/HTTP dependencies in the selected SDK-independent contract modules. This is a bounded dependency check, not proof of lifecycle correctness; existing behavioral and lifecycle tests remain required.

### Hard invariant: one deterministic candidate creator before human review

Until human review, deterministic materialisation MUST be the sole KnowledgeCandidate creator. Reuse `src/vorming/knowledge_materialisation_v1.py::materialise_knowledge_candidates`; no provider, selection, evidence-binding, transformation, Admission, retry, or recovery path may introduce a second candidate creator.

- Providers and selection/evidence-binding code MUST return proposals, validated source references, assessments, or failure findings. They MUST NOT independently assign candidate identity, reconstruct canonical candidate text, or create an alternative candidate/source mapping.
- Deterministic materialisation alone owns candidate text, candidate identity, and the candidate's source mapping. Transformation and Admission MAY validate, project, enrich non-authoritative metadata, or reject its output; they MUST NOT independently create, rewrite, split, merge, or silently repair a candidate. A necessary selection correction MUST return through the existing selection and deterministic materialisation path.
- Rejection MUST preserve source work and recovery findings under the existing persistence contracts. It MUST NOT trigger a fallback candidate creator.
- Changes touching these paths MUST prove that evidence binding preserves materialised candidate text, identity, and source mapping, and that every supported pre-review route uses the same creator. Existing source reconstruction remains the owner of the source representation; it is not a second candidate creator.
- Human review permissions remain governed by the existing review/revision contracts. This pre-review invariant grants no additional review or publication authority. An apparent need to violate the invariant MUST be surfaced as a domain-design conflict before implementation; agents MUST NOT weaken or bypass it autonomously.

### Improve codebase architecture

Periodic architecture survey (mattpocock). Skill files: `.agents/skills/improve-codebase-architecture/`. Invoke explicitly — do not auto-run. Companion vocabulary skills (`codebase-design`, `grilling`) live upstream at https://github.com/mattpocock/skills.
