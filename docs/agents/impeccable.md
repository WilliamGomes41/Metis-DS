# Impeccable for Metis frontend work

Promise: agents load Impeccable for every frontend creation or change, without
the user having to request it by name. Change class: B (agent workflow only).
Rewrite risk: none. No application or lifecycle behavior is changed.

## Installation and discovery

The canonical skill is [Impeccable](../../.agents/skills/impeccable/SKILL.md).
It is an unmodified, project-local snapshot of `pbakaus/impeccable` version
4.8.0, commit `02523aec3e4c4580102d996d1b6a71fbe062e03f`.
`config/impeccable.v1.json` pins the installed files and SHA-256 hashes.
Apache-2.0 and third-party notices are in `.agents/licenses/impeccable-*`.

Codex discovers `.agents/skills/impeccable`; Cursor and Claude have small local
adapters pointing to that same canonical skill. Existing Copilot and Claude
instructions already require root `AGENTS.md`, which owns the mandatory trigger.
Reload project skills or start a new agent session after checkout. A repository
instruction cannot guarantee compliance by a host that does not read it.

The upstream CLI could not reach its bundle server in this environment, so this
uses the upstream-documented manual GitHub installation. Automatic edit hooks
were not installed or activated. The mandatory trigger in `AGENTS.md` is active
as a repository instruction, independent of hook support or host trust settings.

## Use on every frontend task

1. Read the canonical skill and load its context once per session from the repo
   root. Keep the engine cache local and out of source control:

   ```sh
   IMPECCABLE_HOME="$PWD/.impeccable/cache" \
     .agents/skills/impeccable/scripts/impeccable context --target src/settings/metis_dictionary_ui.py
   ```

   Replace the target with the actual file or route. The launcher verifies the
   pinned engine checksum before downloading/executing a missing engine.
2. Follow the relevant playbook and read `reference/craft-floor.md` immediately
   before UI edits. Preserve `assets/brand/console.css` tokens and brand rules;
   missing `PRODUCT.md` or `DESIGN.md` does not make Metis a greenfield product.
   Do not fetch licensed fonts from a public CDN.
3. Verify the changed UI at relevant desktop/mobile widths and apply the
   existing risk-proportional repository checks. Run the relevant Impeccable
   audit/detector when the engine is available. Report checks actually run.

If the engine is unavailable, report that context loading did not run, read
existing product/design context and the vendored playbooks directly, and
continue the authorized work. Do not claim a detector or rendered check passed.
Preserve host permissions and repository domain boundaries when upstream
guidance suggests extra tools, subagents, hooks or publication.

## Verify and update

```sh
python -m pytest -q tests/test_impeccable_install.py
```

Review upstream changes before updating the canonical snapshot and its pinned
manifest together. Retain notices and executable launchers; do not modify
vendored skill text locally. The adapters need changing only when their link or
base-directory instruction changes. The separate shared-agent-skills manifest
continues to own its existing snapshots; this install does not replace it.
