# Changelog

All notable technical changes to V&VN Data Services are recorded here.

## [Unreleased]

### Added
- Internal operations console MVP: ingest mailbox (HTML/PDF or URL snapshot), family × class tree, named reviewers, review return-loop, local G0 identity. Served by `vvn-data-service serve-console`. Publication remains fail-closed without an immutable locator (G2).

### Changed
- Historical step, audit and repair reports moved from the repository root to `docs/history/`. The root remains the operating surface; `output/` historical artefacts are unchanged.

### Fixed
- Restored V&VN Data Services handoff/roadmap after foreign product status was written into this repository.
- Canonical store now uses the integrity-kernel object hash and exact review snapshot (closes remaining P0 dual-hash).
- CLI `serve` / `serve-api` match the Docker entrypoints.
- Inspection search uses the same answerability gate as the Product API.
- `audit-current` defaults to reviewed fixtures instead of `output/`.

## [0.1.0] - 2026-08-20

### Added
- Canonical knowledge-object pipeline with provenance and immutable hashing.
- Clinical review and four-eyes workflow for high-risk objects.
- Publication registry and fail-closed publication gates.
- Lexical, vector and hybrid retrieval.
- Protocol v2.1 Answerability/Evidence Gate and safe abstention behavior.
- External Product API v1 with tenant scopes, entitlements and usage metering.
- Generic HTML source adapter and source-neutral provenance schema v1.2.
- Repository baseline with CI, repository preflight and contribution rules.

### Known blockers
- Canonical source binary for Fractuurpreventie is not yet locally verified.
- Second real source (Continentie) awaits exact source bytes before canonical ingest.
- Independent retrieval acceptance requires a new holdout B.
- RAG/Answer API acceptance has not started.
