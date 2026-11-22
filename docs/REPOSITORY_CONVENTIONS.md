# Repository conventions

## Repository role

This repository is the authoritative source for application code, schemas, deterministic transforms, tests, safe fixtures, configuration templates and technical documentation.

It is **not** the authoritative store for canonical clinical source binaries, production secrets, runtime databases or externally supplied reviewer workbooks.

## Directory contract

| Path | Purpose | Source controlled |
|---|---|---|
| `src/` | Application and pipeline code | yes |
| `schemas/` | Versioned data contracts | yes |
| `config/` | Safe configuration and templates | yes |
| `data/` | Specs, manifests, golden/holdout definitions and safe fixtures | yes |
| `tests/` | Automated regression tests | yes |
| `docs/` | Protocol and technical documentation | yes |
| `docs/history/` | Historical reports and inert source snapshots; not runtime or steering documents | yes |
| `db/` | Database schemas/migrations | yes |
| `examples/` | Safe client examples | yes |
| `scripts/` | Build, audit and repository tooling | yes |
| `output/` | Historical pilot artifacts and generated outputs | transitional |
| `output/runtime/` | Local runtime state | no |
| `sources/private/` | Canonical source binaries if mounted locally | no |

## Documentation layout

The repository root is the operating surface: `PROTOCOL.md`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `SECURITY.md`, plus code, config and build files. The steering hierarchy remains `PROTOCOL.md → acceptatietests → code`. Open work is tracked in [GitHub Issues](https://github.com/WilliamGomes41/Metis-DS/issues). Current progress is read from merged code, tests, CI and commit history on `main`. `docs/history/` holds one-off step, audit and repair writeups; those files do not add a steering layer and must not be treated as current steering documents.

## Runtime output policy

Automated tests use reviewed deterministic fixtures under `data/fixtures/` and must not depend on `output/`. The `output/` directory contains transitional historical pilot artefacts only; it is not an authoritative baseline, fixture store or acceptance-evidence store. New runtime state must remain untracked under `output/runtime/` and must not become a source-controlled test dependency.

## Releases

Application versioning follows semantic versioning where practical:

- patch: implementation repair without contract change;
- minor: backward-compatible feature or API extension;
- major: breaking external contract.

Protocol, schema and clinical knowledge versions remain independently versioned and must not be inferred from the application version.

## Repository and branch protection

The authoritative remote is [WilliamGomes41/Metis-DS](https://github.com/WilliamGomes41/Metis-DS), with `main` as its default branch.

**G1-doelchecks** zijn `test` en `handoff-contract`.

**Tijdelijke G1-checks** zijn `test (3.12)` en `test (3.13)`. Ze geven de
uitslag van `test` door tijdens de overstap.

Changes go through feature branches and pull requests. Gate G1 protects
against force-pushes and branch deletion and requires a pull request with
successful checks and resolved review threads. A fresh native ruleset readback
establishes which checks GitHub currently enforces.

The strengthening plan for `handoff-contract` and resolved review threads is in
[#1087 — native merge policy](change-contracts/1087-native-merge-policy.md).
The snapshot validator and test-check cutover are in
[#1135 — one test check](change-contracts/1135-single-required-test.md).
