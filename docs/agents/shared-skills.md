# Shared agent skills

Frontend creation and changes also require the separately pinned
[Impeccable integration](impeccable.md), as specified in root `AGENTS.md`.
Its canonical skill lives in `.agents/skills/impeccable/` and its independent
manifest is `config/impeccable.v1.json`.

The independent source repository is
[WilliamGomes41/plugins](https://github.com/WilliamGomes41/plugins).
Metis commits only the reviewed files listed in
`config/shared_agent_skills.v1.json`, pinned to a full commit and SHA-256 hashes.
The initial revision is `5108b719a7aa484ef1a9781f587c7bbeac793f92`.
These are selective, unmodified snapshots, not a Git submodule or a live remote
plugin installation. A new checkout works offline without the plugin repo.

## Selection and authority

| Skill | Use | Relationship to existing Metis methods |
| --- | --- | --- |
| [verify-this](../../.agents/skills/verify-this/SKILL.md) | An explicit request for a falsifiable claim and comparable baseline/treatment evidence | Reuse evidence from risk-proportional verification; do not add a duplicate mandatory verification pass |
| [make-pr-easy-to-review](../../.agents/skills/make-pr-easy-to-review/SKILL.md) | An explicit request to improve PR reviewability | Preserve the existing issue/change contract and verification requirements; history changes need the authorization described in the skill |
| [how](../../.agents/skills/how/SKILL.md) | An explicit request to explain a runtime path, such as how a passage becomes a knowledge object from extraction through review | Read-only; satisfies the tracing part of the Class B program-design gate, not the gate itself |
| [why](../../.agents/skills/why/SKILL.md) | An explicit request for the rationale behind a gate, rule or threshold | Source control, change contracts and issues are the available evidence; report other evidence categories as gaps |
| [blast-radius](../../.agents/skills/blast-radius/SKILL.md) | An explicit request to assess what a concrete change could break beyond its diff | Complements, and does not replace, the adversarial review that high rewrite risk requires |
| [show-me-your-work](../../.agents/skills/show-me-your-work/SKILL.md) | An explicit request for a decision trail during an audit or long run | The log is a working artifact and never processing evidence; existing evidence exports remain authoritative |
| [principle-explain-the-number](../../.agents/skills/principle-explain-the-number/SKILL.md) | Before reporting or acting on a measured number, such as coverage, admission or acceptance counts | Use with existing quality metrics and traces; it adds no metric |

The pstack selection supports auditing the knowledge-formation chain with the
existing instruments (`scripts/trace_recorded_formation.py`,
`scripts/replay_recorded_formation.py` and the processing evidence export).
It is pinned without `scripts/`: where `show-me-your-work` names
`scripts/log.sh`, append the row with `printf` and apply the same cell cleaning
it describes. Sibling skills that these files link to, such as
`benchmark-checklist`, `unslop` or `arena`, are not included. The Claude adapters keep upstream
`disable-model-invocation: true`, so these skills load only when named.
Model names and `pstack-models.mdc` routing in `how` and `why` do not apply;
use the session's own models, and spawn subagents only where the user or host
instructions allow it.

Shared skills add working methods, not execution, merge, deployment, or
publication authority. Follow `AGENTS.md` and the applicable existing Metis
contracts. Do not weaken checks, modify lifecycle/domain rules, or expand task
scope to satisfy a plugin workflow. User and host-level instructions still apply.
Reuse existing artifacts and choose only the relevant procedure.

Names such as `control-cli` and `control-ui` in upstream prose describe optional
tooling: use an available equivalent when sufficient. Likewise, GitHub connectors
may replace `gh` where available. Do not assume a referenced sibling plugin or
command exists, install additional tools automatically, or claim an unavailable
check ran. No plugin hooks, MCP configuration, model routing, agent definitions,
or autonomous shipping loops are included in this selection.

## Agent entry points

| Coding agent | Entry point |
| --- | --- |
| Codex and Cursor | Root `AGENTS.md` and canonical `.agents/skills/` |
| GitHub Copilot | `.github/copilot-instructions.md`, root `AGENTS.md`, and `.agents/skills/` |
| Claude Code | Root `CLAUDE.md` and `.claude/skills/` adapters linking to canonical skills |
| Other agents with repository file access | Read `AGENTS.md`, this index and the selected `SKILL.md` explicitly |

The adapters repeat only discovery metadata (including opt-in invocation) and a link, not workflow bodies.
They are plain files, so Git symlink support is unnecessary. Host settings,
versions and trust policies can still affect loading. This change makes the
same instructions available; it does not prove every host or model follows
them identically. Start a new session or reload project skills after checkout.
Repository files do not automatically register tools in hosted chat sessions
that cannot discover project skills.
`.gitattributes` keeps the pinned snapshots and adapters on LF line endings so
Windows checkouts do not invalidate their byte checksums.

## Verify or reproduce the snapshot

```sh
python scripts/sync_shared_agent_skills.py --check
```

The check is offline and does not execute plugin code. To reproduce missing
files from a local clone of the separate plugin repo:

```sh
python scripts/sync_shared_agent_skills.py --source /path/to/plugins
```

The clone must contain the pinned commit. The command reads blobs from that
commit, not the checkout's working files or latest branch, and verifies every
source hash before writing. Existing local drift is refused rather than
overwritten. The MIT notices are retained in `.agents/licenses/cursor-team-kit.txt` and
`.agents/licenses/pstack.txt`.

For an update, review the selected upstream diff, then change the commit and
file hashes in the manifest in a normal PR. Review any changed local snapshot
before replacing it, regenerate the adapters, run the integrity and focused
contract tests, and follow the normal Metis review process. The check does not
authenticate the upstream author or audit skill behavior; review remains needed.

## Format references

- [Codex project skills](https://developers.openai.com/codex/skills)
- [Cursor project skills](https://cursor.com/docs/skills)
- [GitHub Copilot project skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)
- [Claude Code project skills](https://code.claude.com/docs/en/skills)
