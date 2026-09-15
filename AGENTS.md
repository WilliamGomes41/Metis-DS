## Agent skills

### Issue tracker

Issues live in this repo’s GitHub Issues (`gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical roles map 1:1 to tracker labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.

### Execution contract

`ready-for-agent` marks a ticket as executable but does not start work automatically. Repository coding runs use the `Metis Engineer` profile in `.github/agents/metis-engineer.agent.md` and follow `docs/agents/execution-contract.md`.

### Lifecycle VSA contract

Any issue that changes ingest, document/version identity, review, repair, readiness, publication, serving, migration, reconciliation, recovery, supersession, withdrawal, or UI/API lifecycle state MUST also follow `docs/agents/lifecycle-vsa.md`.

For those issues, the lifecycle transition MUST be specified before code changes. A technical component, status, page, database column, helper, or migration is not by itself a vertical slice. Published work is immutable; successor work must be modeled as a new WorkingRevision or SourceSnapshot; serving authority remains the publication registry; restart/recovery and a black-box lifecycle proof are part of Definition of Done.

If `docs/agents/lifecycle-vsa.md` requires a lifecycle, identity, authority, supersession, withdrawal, migration, or recovery decision that the assigned issue does not define, the agent MUST stop and surface the missing decision instead of making an assumption.

### Improve codebase architecture

Periodic architecture survey (mattpocock). Skill files: `.agents/skills/improve-codebase-architecture/`. Invoke explicitly — do not auto-run. Companion vocabulary skills (`codebase-design`, `grilling`) live upstream at https://github.com/mattpocock/skills.
