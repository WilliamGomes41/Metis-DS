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
| `db/` | Database schemas/migrations | yes |
| `examples/` | Safe client examples | yes |
| `scripts/` | Build, audit and repository tooling | yes |
| `output/` | Historical pilot artifacts and generated outputs | transitional |
| `output/runtime/` | Local runtime state | no |
| `sources/private/` | Canonical source binaries if mounted locally | no |

## Runtime output policy

Automated tests use reviewed deterministic fixtures under `data/fixtures/` and must not depend on `output/`. The `output/` directory contains transitional historical pilot artefacts only; it is not an authoritative baseline, fixture store or acceptance-evidence store. New runtime state must remain untracked and must not become a source-controlled test dependency.

## Releases

Application versioning follows semantic versioning where practical:

- patch: implementation repair without contract change;
- minor: backward-compatible feature or API extension;
- major: breaking external contract.

Protocol, schema and clinical knowledge versions remain independently versioned and must not be inferred from the application version.

## Branch protection target

The authoritative private remote is `WilliamGomes41/VENVN-DS`, with `main` as its default branch. Changes are handled procedurally through feature branches and pull requests while enforceable protection is unavailable under the current repository plan. Gate G1 remains `BLOCKED` until `main` enforces required CI checks and rejects direct pushes through GitHub branch protection or an equivalent ruleset.
