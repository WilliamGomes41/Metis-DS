# Changelog

All notable technical changes to V&VN Data Services are recorded here.

## [Unreleased]

### Added
- Implementation wave A+B+C on the existing kernel (one PR against main): v2.12 unclassified default, question×type answerability, object-tuple review binding and atomic published projection; v2.11 ingest lock in code (live URL-HTML rejected; freeze HTML and hashed PDF URL accepted; `supported` requires source_locator); v2.10 Documentenhierarchie heading, waiting-task badges and Accounts room with closed roles. `publish()` remains G2-BLOCKED. No Azure/Vercel/Neon/LLM.
- Protocol v2.12.0: extraction is structure/provenance only (unclassified default; human confirms object_type); answerability is question type × object type; publish binds object_id + object_version + canonical_object_hash + confirmed_object_type + reviewer + decision; serving uses an atomically replaced published projection. Protocol-only; does not implement extract, API or console changes. Next implementation is that kernel follow-up, then G2/Azure. G2 remains the publication blocker.
- Protocol v2.11.0: uploaded HTML freeze file, reject live URL-HTML at ingest, mandatory source locators on knowledge objects, and fail-closed Product API `supported` without a locator. Now a live component of baseline v2.12.0 plus this v2.11 delta. Protocol-only; does not implement ingest rejection or API fail-closed. v2.11 kernel work remains required law and is not a supersession of v2.12 sequencing. G2 remains the publication blocker. Does not reopen GD-03.
- Protocol v2.10.0: Documentenhierarchie heading, real waiting-task badges, and Accounts room with closed role set (researcher, reviewer, publisher). Protocol-only; does not implement the UI follow-up. Next implementation is that follow-up on the now-merged v2.9 UX (PR #25). G2 remains the publication blocker.
- Console-UX-rewrite on the existing kernel: task-oriented researcher rooms, researcher vocabulary (no envelope as a UI term), visible move/promote actions, login with gebruikersnaam and `type=password`, V&VN digital stylesheet tokens (Water secondary family, system-font fallback) and the official v&vn beeldmerk PNG. Protocol v2.9.0 remains the live UX/brand law; this implements that rewrite in `src/operations_console_app.py` (PR #25). G2 remains the publication blocker.
- Protocol v2.9.0: researcher-task console UX and V&VN digital stylesheet (huisstyle) rules. Protocol-only; does not implement the UI rewrite. Next implementation is that rewrite on the existing kernel. G2 remains the publication blocker.
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
