# Emil Kowalski design-engineering skills for Metis frontend work

Promise: agents doing Metis frontend work have three reviewed interaction-craft
procedures available next to the mandatory Impeccable workflow, and one read-only procedure for deciding where motion belongs. Change class: B
(agent workflow only). Rewrite risk: none. No application or lifecycle behavior
is changed by this installation.

## Selection

The source is [emilkowalski/skills](https://github.com/emilkowalski/skills)
(MIT), the pack presented on <https://aiforui.dev/skills>. Metis commits an
unmodified snapshot of four skills at commit
`715c1807e08c497cfd1dc4feb450a2a3300ef2a9`; `config/emil_design_skills.v1.json`
pins every file by SHA-256 and the notice is `.agents/licenses/emil-skills-MIT.txt`.

| Skill | Use in Metis |
| --- | --- |
| [emil-design-eng](../../.agents/skills/emil-design-eng/SKILL.md) | Interaction detail on a UI change: press and hover feedback, focus, when motion helps and when it must be absent |
| [break-ui](../../.agents/skills/break-ui/SKILL.md) | Stress a console screen with realistic worst-case data: long guideline titles, a count of exactly one, empty lists, missing optional fields |
| [find-animation-opportunities](../../.agents/skills/find-animation-opportunities/SKILL.md) | Read-only sweep for the few places where motion helps, with the rejected places named; first applied in `docs/change-contracts/console-reveal-motion.md` |
| [mobile-native](../../.agents/skills/mobile-native/SKILL.md) | Phone behavior of the console: sticky hover, input zoom, tap targets, viewport height |

The console is server-rendered HTML from Python with plain CSS and a little
vanilla JavaScript. The other skills in the pack target stacks Metis does not
have and are deliberately not installed: React Motion animation building and
auditing (`animate`, `choreograph`, `improve-animations`, `review-animations`,
`remove-animations`, `animation-performance`,
`animation-vocabulary`), gesture and sheet interactions (`gestures`,
`apple-design`), Expo and Swift (`animate-expo`, `write-swift`), the Sonner
React toast library (`ask-sonner`), and library choice or variant pickers
(`pick-ui-library`, `prototype`). Add one only when the console gains the
surface it is for.

## Relationship to Impeccable and Metis contracts

[Impeccable](impeccable.md) remains the mandatory frontend workflow and owns
context loading, playbook selection, the craft floor and the detector. These
skills add a second opinion on interaction detail; they do not replace it.
Where they disagree, existing Metis brand tokens in `assets/brand/console.css`
and the Impeccable craft floor win.

- The React, Motion and Tailwind snippets in `emil-design-eng` are
  illustrations. Apply the principle in plain CSS; do not add a frontend
  framework or animation library to follow a skill.
- The console is a daily work tool. Motion stays limited to short feedback on
  press, hover and focus, and respects `prefers-reduced-motion`.
- `break-ui` asks for a "Demo data / Worst case" toggle. Do not add that toggle
  to the console. Enter worst-case data through the existing boundary: a test
  fixture or a disposable local console, never production data.
- `mobile-native` tells you to test on real hardware. Report an emulated
  viewport as emulated; do not claim a device check that did not run.
- `find-animation-opportunities` reports and never edits. Its hand-off names
  `improve-animations`, which is not installed: implement an accepted row as a
  normal Metis change with its own change contract.
- Each skill opens with a fixed "Initial Response" for a bare invocation. Inside
  a Metis task with a concrete target, proceed with the task.

The skills add working methods, not execution, merge, deployment or publication
authority. Domain contracts, change classification and verification
requirements in `AGENTS.md` are unchanged.

## Discovery

Codex reads `.agents/skills/`. Claude Code and Cursor have small adapters in
`.claude/skills/` and `.cursor/skills/` that repeat only the upstream name and
description and link to the canonical file. Reload project skills or start a
new session after checkout.

The upstream installer (`npx skills@latest add emilkowalski/skills`) was not
used: it installs the whole pack unpinned. This follows the same reviewed,
pinned snapshot convention as the other Metis skills.

## Verify and update

```sh
python -m pytest -q tests/test_emil_design_skills_install.py
```

For an update, review the upstream diff of the selected skills, replace the
snapshot and the commit and hashes in the manifest together in a normal PR, and
regenerate the adapters only when upstream name or description changed. Do not
edit vendored skill text locally. The check does not authenticate the upstream
author or audit skill behavior; review remains needed.
