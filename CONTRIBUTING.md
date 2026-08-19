# Contributing

## Branches

- `main`: protected baseline; only tested changes should land here.
- `feature/<short-name>`: new functionality.
- `fix/<short-name>`: defect repair.
- `protocol/<short-name>`: schema, governance or protocol changes.

## Required checks before merge

```bash
python scripts/repository_preflight.py
python -m compileall -q src
pytest -q
```

## Commit convention

Use short imperative messages, for example:

- `feat: add HTML source locator support`
- `fix: block relation-level false positives`
- `test: add numeric constraint regression`
- `docs: update protocol v2.1 delta`
- `chore: establish repository baseline`

## Safety rules

Do not commit:

- API keys, passwords or connection strings;
- real tenant secrets;
- local SQLite/runtime state;
- canonical PDF/DOCX source binaries;
- reviewer spreadsheets;
- private keys or certificates.

Canonical source binaries belong in the controlled source store (Azure Blob Storage in the target architecture), not in Git.
