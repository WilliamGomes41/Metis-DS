## Agent skills

### Issue tracker

Issues live in this repo’s GitHub Issues (`gh` CLI). See `docs/agents/issue-tracker.md`.

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

### Lifecycle VSA contract

Class A issues MUST also follow `docs/agents/lifecycle-vsa.md` in full. Class A includes changes to logical document/version lineage, source snapshot immutability, review closure required for publication, publication readiness semantics, canonical releases, serving authority/active serving set, supersession, withdrawal, published-state migration/reconciliation, or restart/recovery of lifecycle state.

For Class A, the lifecycle transition MUST be specified before code changes. A technical component, status, page, database column, helper, or migration is not by itself a vertical slice. Published work is immutable; successor work must be modeled as a new WorkingRevision or SourceSnapshot; serving authority remains the publication registry; restart/recovery and a black-box lifecycle proof are part of Definition of Done.

A Class A high-risk rewrite MUST additionally map every relevant authority, writer, reader, runtime/storage topology, compatibility path, cutover, rollback/recovery path, and adversarial bypass scenario before implementation. Green CI alone is not sufficient evidence that the rewrite surface is complete.

If `docs/agents/lifecycle-vsa.md` requires a lifecycle, identity, authority, supersession, withdrawal, migration, recovery, or rewrite-risk decision that the assigned issue does not define, the agent MUST stop and surface the missing decision instead of making an assumption.

### Improve codebase architecture

Periodic architecture survey (mattpocock). Skill files: `.agents/skills/improve-codebase-architecture/`. Invoke explicitly — do not auto-run. Companion vocabulary skills (`codebase-design`, `grilling`) live upstream at https://github.com/mattpocock/skills.
