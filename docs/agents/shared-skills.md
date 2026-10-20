# Shared agent skills

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

The adapters repeat only discovery metadata and a link, not workflow bodies.
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
overwritten. The MIT notice is retained in `.agents/licenses/cursor-team-kit.txt`.

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
