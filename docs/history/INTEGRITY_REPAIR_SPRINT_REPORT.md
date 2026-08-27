# V&VN Data Services - Integrity Kernel & Review Lifecycle Repair Sprint

Date: 2026-08-19

## Gate decision

Technical repair sprint: **PASS**.

Clinical publication of the current Fractuurpreventie dataset: **BLOCKED by design**.

The codebase no longer has the five P0 integrity gaps identified in the full technical audit. The remaining blockers are external/current-state blockers: the canonical PDF binary has not been locally supplied and hashed; the legacy page-15 extraction did not retain coordinates; clinical and technical review are not complete; high-risk objects still require second review.

## P0 repairs completed

1. **Full canonical-object hash**
   - `canonical_object_hash` covers identity, version, source, structure, content, logic, relations, decision graph, risk, uncertainty and transformation provenance.
   - Mutable governance state is intentionally excluded.
   - `content_hash` is retained as a backward-compatible alias of the canonical-object hash.

2. **Exact review snapshot**
   - First and second review bind to the exact `canonical_object_hash`.
   - Any change to a reviewable field invalidates approval.
   - Tests include source page, target group, context and uncertainty tampering.

3. **Real source-binary verification**
   - A source is verified only when the registry points to a real local binary and its SHA-256 is recomputed successfully.
   - A manually entered 64-character checksum is insufficient.
   - `source-register` and `source-bind` CLI commands implement the verified-source path.

4. **Exact source-fragment provenance**
   - Semantic spec v2.1 contains explicit raw-fragment references.
   - Fragment hashes are checked against the raw extraction.
   - New PDF extraction v2 preserves bounding-box coordinates and full fragment hashes.
   - Legacy page-15 fragments are marked `not_captured_legacy_extract`; publication is blocked until they are re-extracted with coordinates.

5. **Revise creates a new version**
   - Explicit revision patches create a new immutable object version.
   - Review state is reset to `needs_review`.
   - Previous object version, revision reason and patch hash are retained in provenance.

## Additional repairs completed

- Central schema validation with JSON Schema FormatChecker.
- Single fail-closed publication eligibility policy.
- Separate clinical and technical review tracks.
- Strict four-eyes review for high-risk objects.
- Hash-chained append-only review ledger.
- Legacy-review reconciliation workflow for the already-issued expert workbook.
- Protocol v2.1 semantic specification with explicit raw lineage.
- Knowledge Object Schema v1.1.
- Raw Fragment Schema v1.0.
- Coordinate-preserving PDF extractor v2.
- Authoritative `vvn-data-service` CLI.
- Pinned runtime and development dependencies.
- Dockerfile and GitHub Actions CI definition.
- Deterministic integrity sprint runner.

## Verification results

- Python compile: PASS
- Deterministic semantic transform: PASS (two independent runs are byte-identical)
- Test suite: **66 passed**
- Aggregate test coverage: **83%**
- Installed CLI smoke test: PASS
- Current canonical object integrity audit: PASS
- Current publication gate: BLOCKED

## Current publication blockers

The real current dataset has 21 objects and 0 eligible objects.

Expected blockers include:

- canonical source binary not in verified source registry;
- source checksum not yet SHA-256 verified from the actual PDF;
- 20 legacy page-15 objects lack retained PDF coordinates;
- first review not complete;
- 12 high-risk objects require second review;
- technical review of the document object not complete;
- document-source uncertainty remains until the canonical binary is verified.

These are valid fail-closed states, not code failures.

## What happens when the official PDF is supplied

1. `vvn-data-service source-register` computes the PDF SHA-256 from the binary.
2. `vvn-data-service source-bind` creates a verified source manifest.
3. `extract_pdf_v2` re-extracts page 15 with exact bounding boxes.
4. The semantic spec is rebound to the new coordinate-preserving fragment IDs/hashes.
5. Semantic objects are regenerated deterministically.
6. Clinical and technical review queues are generated with exact canonical-object hashes.
7. High-risk objects receive second review.
8. `vvn-data-service prepublish` must return PASS before canonical storage/publication is allowed.

## Reproducibility command

```bash
./scripts/run_integrity_sprint.sh
```

The script compiles source code, performs the semantic transform twice and compares byte output, runs the complete test suite, and runs the current integrity/publication audit.

## Known infrastructure limitation of this execution environment

The Dockerfile was created, but Docker is not installed in the current sandbox, so the container image could not be built here. The Python package and installed CLI were tested successfully in the current runtime.
