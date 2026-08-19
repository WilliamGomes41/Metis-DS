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

## Transitional output policy

The pilot currently contains historical output artifacts because several existing regression tests reference them. New runtime state must not be added as a source-controlled dependency. A later cleanup can migrate required deterministic fixtures into `data/fixtures/` and make `output/` fully disposable.

## Releases

Application versioning follows semantic versioning where practical:

- patch: implementation repair without contract change;
- minor: backward-compatible feature or API extension;
- major: breaking external contract.

Protocol, schema and clinical knowledge versions remain independently versioned and must not be inferred from the application version.

## Branch protection target

When the GitHub remote is created, configure `main` so that merges require the CI test workflow to pass. Direct pushes can remain disabled once the first baseline is established.
