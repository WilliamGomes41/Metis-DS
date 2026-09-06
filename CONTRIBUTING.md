# Contributing

## Branches

- `main`: protected baseline; only tested changes should land here.
- `feature/<short-name>`: new functionality.
- `fix/<short-name>`: defect repair.
- `protocol/<short-name>`: schema, governance or protocol changes.

## Required checks before merge

```bash
python scripts/repository_preflight.py
python scripts/release_control_preflight.py
python -m compileall -q src
pytest -q
```

`scripts/release_control_preflight.py` names the Metis skill checks (`scope/belofte`, `opslag`, `beschikbaarheid`, `toegang`, `kwaliteit`, `metrics`, `slop`, `releasebewijs`) as `required` or `n.v.t.` from changed paths. CI must run this mapping after `repository_preflight.py` and must fail when a `required` category has no matching test marker or evidence path. Do not drop that step from `.github/workflows/ci.yml`; the skill names the checks so they cannot be forgotten. Product categories (`opslag`–`metrics`) stay `n.v.t.` until a product path is in the diff. Markers and `# release-control-evidence:` comments are metadata pointing at those concrete checks; they are not live-release evidence.

## Commit convention

Use short imperative messages, for example:

- `feat: add HTML source locator support`
- `fix: block relation-level false positives`
- `test: add numeric constraint regression`
- `docs: update protocol v2.1 delta`
- `chore: establish repository baseline`

## Documentation

Keep the repository root as the operating surface. Historical step, audit and repair writeups belong in `docs/history/`, not the root. Do not add another steering layer; the hierarchy remains `PROTOCOL.md → ROADMAP.md → tests → code`. Read current progress from merged code, tests, CI and commit history on `main`.

## Safety rules

Do not commit:

- API keys, passwords or connection strings;
- real tenant secrets;
- local SQLite/runtime state;
- canonical PDF/DOCX source binaries;
- reviewer spreadsheets;
- private keys or certificates.

Canonical source binaries belong in the controlled source store (Azure Blob Storage in the target architecture), not in Git.
