# Metis — agent instructions

## Goal

Metis turns source documents into traceable knowledge for human review, controlled publication and retrieval.
Follow the existing hierarchy: [PROTOCOL.md](PROTOCOL.md) → acceptance tests → code. Track open work and missing evidence in [GitHub Issues](https://github.com/WilliamGomes41/Metis-DS/issues).

## Where to look

- `src/`: application and pipeline; `tests/` and `data/fixtures/`: checks and safe examples; `db/migrations/`: schema changes; `docs/`: contracts and runbooks.
- Before implementation, follow the [execution contract](docs/agents/execution-contract.md) and [Metis Engineer profile](.github/agents/metis-engineer.agent.md): one explicitly assigned, executable `ready-for-agent` issue.
- Classify as Class A, Class B or Class C and state `Rewrite risk: none | high` under [continuous development](docs/agents/continuous-development.md). Use the lightest process that safely proves the promise.
- For shared extraction/review/retrieval/semantic/persistence or cross-layer Class B behavior, follow the [program-design gate](docs/agents/continuous-development.md#class-b-program-design-gate). For Class B changes creating or mutating durable domain state, apply the [Stateful Class B domain-first overlay](docs/agents/continuous-development.md#stateful-class-b-domain-first-overlay) before VSA.
- Class A issues MUST also follow `docs/agents/lifecycle-vsa.md` in full. Read the [lifecycle contract](docs/agents/lifecycle-vsa.md) before implementation; high rewrite risk requires its existing mitigation and adversarial review.
- Before extraction, pre-review formation (including providers, selection/evidence binding and Admission), review, publication or persistence work, read the [domain owner and proof map](docs/agents/abstraction-boundaries.md), including its single-candidate-creator rule. Reuse those operations instead of adding parallel authorities.
- Read [domain context](docs/agents/domain.md) for the affected area. Use the [GitHub tracker](docs/agents/issue-tracker.md), [triage labels](docs/agents/triage-labels.md) and [GitHub–Linear handoff](docs/agents/linear-github-handoff.md); GitHub is the source of truth, Linear the workboard.

## Verify

Run the required repository checks and the tests appropriate to the change; the normal sequence is:

```sh
python scripts/repository_preflight.py
python scripts/release_control_preflight.py --base origin/main
python -m compileall -q src tests
python scripts/check_architecture_boundaries.py
python -m pytest -q tests/test_architecture_invariants.py
python -m pytest -q
```

For console/PostgreSQL tests, first run `bash scripts/test_postgres.sh`; never count PostgreSQL skips as passing proof.
For setup and test-database configuration, use [STACK_SETUP_BASELINE.md](docs/STACK_SETUP_BASELINE.md).

## Done means evidence

Report the actual check results and tested commit, remaining uncertainty and next step. For UI changes, add rendered/browser evidence at relevant widths.
A missing or failed required check is not PASS. Do not weaken or delete tests to hide a regression; justify actual contract changes.
Record evidence and the session handoff under the [GitHub–Linear contract](docs/agents/linear-github-handoff.md). A merge alone does not prove deployment or acceptance.

## Stop and surface the decision

Stop before implementation when required domain, authority, lifecycle, migration, recovery or rewrite-risk decisions are missing, or the change exceeds its assigned scope; follow the [execution contract](docs/agents/execution-contract.md).
Do not merge your own PR. Production, Azure, permission or secret changes require the existing explicitly approved scope.
Every console deployment MUST follow `docs/agents/deployment-protocol.md`; read the [deployment protocol](docs/agents/deployment-protocol.md) before proposing or executing deployment steps.

## Skills

For complex or multi-phase work, read [skill-dispatcher](.agents/skills/skill-dispatcher/SKILL.md) before substantive work. For bug repairs, normally select `diagnosing-bugs` and `risk-proportional-verification` from the available catalog.
Read the selected skill before using it; choose only what the task needs. Skills grant no extra authority. Report missing tools and continue independently executable work without claiming the missing capability ran.

| Skill / collection | When to use |
| --- | --- |
| [Impeccable](.agents/skills/impeccable/SKILL.md) | Agents MUST read and apply it for every frontend creation or change without the user naming it. Follow the [Metis integration](docs/agents/impeccable.md). |
| [pstack (Poteto)](docs/agents/shared-skills.md) | Explicit requests for how/why, impact or a decision trail; use `principle-explain-the-number` before reporting or acting on measured numbers. |
| [Emil Kowalski](docs/agents/emil-design-skills.md) | Relevant interaction detail, worst-case data or phone behavior; motion-opportunity analysis is read-only. Complements mandatory Impeccable. |
| [Stitch](https://github.com/WilliamGomes41/stitch-skills) | Compare variants before implementing new screens or substantial redesigns. Requires an installed plugin and MCP/account connection; see the [shared skill index](docs/agents/shared-skills.md#external-stitch-plugin). |
| [Matt Pocock](.agents/skills/improve-codebase-architecture/SKILL.md) | Only on an explicit request for an architecture survey; do not start unsolicited scans or refactors. |
