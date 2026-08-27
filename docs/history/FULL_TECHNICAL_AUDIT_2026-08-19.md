# V&VN Data Services - Full Technical Audit

Date: 2026-08-19
Scope: active project `/mnt/data/vvn-data-service-v0.1`, protocol-v2 implementation through hybrid retrieval/provider boundary.
Audit mode: code inspection, full pytest run, coverage run, schema validation, CLI/script execution, hash/integrity probes, configuration/repository consistency review.

## Executive verdict

**Overall status: BLOCKED for clinical publication and production deployment; suitable for continued controlled pilot development.**

The core architecture is sound: canonical approved knowledge is separated from publication state; retrieval is derived; publication is fail-closed; synthetic retrieval benchmarks preserve abstention; canonical storage is release-based; emergency unpublish exists.

However, several controls described by Protocol v2 are not yet technically complete. The most important gaps concern exact review snapshots, full-object integrity hashes, source-binary verification, object-level provenance, revise/version lifecycle, technical review, production database/runtime packaging, and independent retrieval acceptance.

## Audit evidence

- `pytest -q`: **53 passed**.
- Python compile: **PASS**.
- Coverage: **83% aggregate** for files observed by coverage; several critical CLI/subprocess paths are not reflected as direct module coverage.
- Current semantic v2 dataset: 21 objects; schema-valid with JSON Schema draft 2020-12.
- Current source manifest: canonical PDF binary unavailable, checksum null, publication explicitly blocked.
- Raw extract SHA-256 matches manifest: `06436dd88505ed106fc97f909f90c00d4d4dd79cffb1372c83aa12d10161e57a`.
- Semantic spec SHA-256: `1aaefe852976876461992f83230d18c3e5f563478951576b6098de1b63eb732f`.
- Hybrid fixture benchmark: 100% top-5 on 16 retrieve questions and 100% abstention on 6 no-answer questions; **not an independent holdout**.
- `scripts/run_protocol_v2_checks.sh`: **FAILS** because `output/v2/fractuurpreventie_page15_reviewed_v2.jsonl` does not exist.

## Severity model

- **P0** - publication safety / truth integrity blocker.
- **P1** - must fix before external pilot or Azure DEV with real content.
- **P2** - should fix before scale-out to multiple guidelines.
- **P3** - technical debt / quality improvement.

---

## Findings

### P0-01 - Review snapshot is not an exact snapshot of the reviewed object

**Status: FAIL**

`first_review_snapshot_hash()` hashes only:
- clean text;
- selected operator;
- threshold;
- unit;
- score points.

It does not hash the complete reviewable object/version. A probe showed that source page, target group, context text, and uncertainty can be changed while both `recompute_content_hash()` and `first_review_snapshot_hash()` remain unchanged.

Observed probe:

- `content_hash_same_after_noncore_tamper = True`
- `review_snapshot_same_after_noncore_tamper = True`

This conflicts with Protocol v2's rule that the snapshot identifies **exactly what the reviewer saw**.

**Required repair:** introduce a canonical immutable object hash (or review payload hash) covering every review-relevant field. Store the hash presented to the reviewer and require exact equality at approval/import/publication.

### P0-02 - `content_hash` does not protect the full canonical object

**Status: FAIL**

`recompute_content_hash()` covers object type, clean text, logic, relations, decision graph and risk. It omits, among other fields:
- source metadata and source checksum;
- document/parent identity;
- structure and source location;
- raw text;
- target group / care setting / topic;
- uncertainty;
- relevant provenance fields.

Therefore the database's same-version immutability check is based on a partial content signature rather than the full immutable canonical record.

**Required repair:** maintain two hashes:
1. `clinical_content_hash` for clinical payload comparisons;
2. `canonical_object_hash` for the entire immutable canonical object excluding only explicitly mutable release state.

Use `canonical_object_hash` for immutable-version conflict detection, review snapshots, second review, and release items.

### P0-03 - Source integrity is declarative, not verified against a binary

**Status: FAIL / known blocker**

The current manifest correctly says the PDF binary is unavailable and blocks publication. But the storage eligibility code considers a source verified when `integrity_status == verified` and the checksum merely looks like 64 hexadecimal characters.

A probe with a fabricated checksum of 64 `a` characters yielded **no eligibility errors**.

There is currently no ingestion function that computes the canonical PDF SHA-256 from the binary and binds it to the manifest/object.

**Required repair:** add immutable raw-source ingest:
`binary -> SHA-256 -> manifest record -> source_id`.
Never allow `integrity_status=verified` to be supplied as an unverified user field.

### P0-04 - Object-level source lineage is insufficient

**Status: FAIL**

Semantic objects carry the hash of the *entire* page-15 raw extract, but do not identify the precise raw block(s) supporting each object. The raw extractor calculates bounding boxes but does not persist them into raw objects. The semantic spec also lacks per-object `source_block_ids`/coordinates.

This prevents a deterministic claim such as:
`knowledge object -> raw block(s) -> exact location in canonical source`.

**Required repair:** persist block IDs + bounding boxes and require each semantic rule/object to reference one or more source fragments. For manually reconstructed operators, store an explicit signed/approved semantic rule reference.

### P0-05 - Revise lifecycle is incomplete

**Status: FAIL**

First review correctly outputs `revise`, but there is no deterministic workflow that turns an accepted correction into:
`object v1 -> revise -> new draft object v2 -> needs_review`.

There is no enforced object-version increment, correction provenance, reviewer/comment linkage, or diff artifact for the revised object.

**Required repair:** implement `create_revision` with immutable parent version, new version ID, change set/diff, correction source, author, and fresh review snapshot.

---

### P1-01 - Technical review path is missing

**Status: FAIL**

Protocol v2 creates a `document` object with `review_track=technical`. The clinical workbook explicitly cannot approve technical objects. No separate technical-review implementation exists.

As a result, once the source hash is available, the workflow still has no formal mechanism to finalise the technical document object without manual JSON mutation.

**Required repair:** implement a technical review queue/workflow with role separation, snapshot hash and audit record.

### P1-02 - Pre-publication gate is weaker than canonical import gate

**Status: PARTIAL**

`prepublication_gate_v2.py` checks metadata and review states, but does not:
- recompute content/canonical hash;
- verify first-review snapshot equality;
- verify second-review snapshot equality;
- bind object source checksum to the manifest checksum;
- validate checksum against an actual source binary.

The later canonical import catches some of these, so the final publication path remains safer than the named pre-publication gate. But the gate itself can report a misleading result.

**Required repair:** make one shared `eligibility_policy` module used by transform gate, canonical import, release creation and tests.

### P1-03 - Protocol-v2 end-to-end check script is broken

**Status: FAIL**

`./scripts/run_protocol_v2_checks.sh` exits 1 because it expects a reviewed file that does not exist. It then also fails to read the gate output.

This violates the stated reproducibility criterion even though the individual tests pass.

**Required repair:** create a single state-aware pipeline command that can explicitly return one of:
- PASS;
- BLOCKED_PENDING_REVIEW;
- BLOCKED_SOURCE_INTEGRITY;
- FAIL_TECHNICAL.

Missing review output must be a modeled state, not a missing-file exception.

### P1-04 - No dependency/environment manifest

**Status: FAIL**

There is no `pyproject.toml`, `requirements.txt`, lockfile, Dockerfile or root project README. The current tests work because the chat sandbox already contains compatible dependencies.

Current observed versions include PyMuPDF 1.26.7, jsonschema 4.26.0, openpyxl 3.1.5, numpy 2.3.5, scikit-learn 1.8.0, pytest 9.0.2.

**Required repair:** add `pyproject.toml` + locked dependency set and Docker-based reproducible runtime. Pin Python major/minor.

### P1-05 - JSON Schema `format` rules are not enforced by runtime validators

**Status: FAIL**

All runtime code instantiates `Draft202012Validator(schema)` without `FormatChecker`. A test mutation containing an invalid URI and invalid dates produced zero schema errors without the format checker.

**Required repair:** use a single validator factory with `FormatChecker()` everywhere.

### P1-06 - Pipeline policy config is not executable policy

**Status: FAIL**

`config/pipeline.v2.yaml` states rules for four-eyes review, publication, retrieval and embeddings, but no runtime code reads the file. It is documentation, not enforced configuration.

Risk classification is supplied manually by the semantic spec. If a risk field is accidentally omitted, there is no central policy that independently detects it.

**Required repair:** either remove the file as authoritative configuration or load and enforce it through a shared policy module. Add invariant checks that numerical thresholds/operators/units trigger risk classification according to policy.

### P1-07 - Review event audit trail begins too late

**Status: PARTIAL**

The canonical database logs import/publication events, but first review, second review, rejected decisions, corrections and revise events live in CSV/JSON outputs rather than an append-only lifecycle ledger.

**Required repair:** create a review-event store/ledger before canonical import, preserving reviewer, decision, timestamp, snapshot hash, comment, and correction proposal.

### P1-08 - Production PostgreSQL path is schema-only

**Status: NOT IMPLEMENTED**

The executable storage implementation is SQLite. `db/schema_v2.sql` is a PostgreSQL reference schema only. There is no PostgreSQL adapter, migration framework, integration test, transaction/concurrency test or Azure PostgreSQL deployment code yet.

**Required repair before Azure DEV:** implement the production adapter and run the same storage/publication test suite against PostgreSQL.

---

### P2-01 - Semantic specification is not formally reviewed/version-diffed

`semantic_page15_spec.v2.0.json` has `reviewed_by: null` and no machine-verifiable diff reference to v1.0. Yet it contains clinical normalization rules and operator corrections.

**Repair:** require spec review and signed/versioned diff before objects derived from it are eligible for approval.

### P2-02 - Metadata is hardcoded to this one guideline

Target group, care setting and topic are hardcoded in `semantic_transform_v2.py`. The extractor also hardcodes V&VN and first-line metadata.

**Repair:** move document metadata to the source manifest/spec and make transform generic before guideline 2-4.

### P2-03 - Decision-tree support is schema-level only

There is a synthetic JSON Schema test for `decision_graph`, but no Storyline `data.js` extractor, graph reconstruction, edge-integrity validator or real decision-tree fixture.

**Repair:** do not claim operational decision-tree support until a real exported tree is parsed and round-trip tested.

### P2-04 - Retrieval benchmark is preliminary and non-independent

Hybrid obtains 100% top-5 and 100% abstention on the current fixture, but thresholds were calibrated on the same golden set. The evaluation report itself correctly labels this non-independent.

There is no independent holdout set and no generic acceptance command that fails when defined thresholds are missed.

**Repair:** freeze v0.1 as development set, create a separately authored/reviewed holdout, define acceptance thresholds, and make the gate return non-zero on failure.

### P2-05 - Version-conflict questions are not part of the retrieval metric run

The golden set has 24 questions, but only 22 are evaluated by the retrieval evaluator. Two `fixture_only` version-conflict cases are covered indirectly by storage/projection tests, not by the same acceptance metrics.

**Repair:** build explicit acceptance scenarios for supersession and emergency-unpublish in the retrieval test harness.

### P2-06 - Publication history is reconstructable but not first-class

The current `publication_registry` stores only the active pointer. Old canonical versions and release/audit data remain, but there is no first-class publication-period history table or `asOf` query implementation.

**Repair:** add publication history/effective intervals and explicit as-of/version pinning before external consumers depend on history.

### P2-07 - Review CSV duplicate IDs can silently override

`read_reviews()` and second-review CSV parsing convert rows to dictionaries keyed by `object_id`; duplicate rows are not rejected. Last-row-wins behavior can hide conflicting reviewer input.

**Repair:** reject duplicate object IDs at import.

### P2-08 - Security identity is placeholder only

CLI `actor`, reviewer and release-owner values are plain strings. There is no authentication, RBAC, managed identity, signed event identity or database permission separation.

This is acceptable for a local PoC but not an external pilot.

### P2-09 - Audit events are not technically append-only

The SQLite/PostgreSQL schema does not prevent UPDATE/DELETE on audit rows. Application code only inserts, but the database itself does not enforce immutability.

**Repair:** production DB permissions/trigger or append-only event store.

### P2-10 - Privacy/PII gate is absent

The current public guideline data does not appear to contain patient data, but no pipeline control detects or blocks accidental patient identifiers in future work documents/examples.

**Repair:** add source classification and PII prohibition/scan before canonical import, plus legal/right-to-use metadata.

### P2-11 - Embedding secret scan is only top-level

`build_provider()` rejects secret-looking keys only at the top-level configuration. Nested parameters are not recursively scanned.

**Repair:** recursive secret-key rejection and use managed identity/environment references only.

---

### P3-01 - Legacy v0.x and v2 implementations coexist without a single authoritative entrypoint

Old schemas, transforms, storage code and readmes remain next to v2. This creates operator risk.

**Repair:** move legacy code to `archive/` or tag it deprecated; introduce one root CLI.

### P3-02 - No root README / repository conventions / CI configuration

There is no root README, `.gitignore`, CI workflow, migration policy, changelog or release discipline in the active sandbox project.

### P3-03 - Extraction is page/block based and does not persist coordinates

The extractor calculates `bbox` but discards it from raw objects. Table/image/OCR handling is deliberately limited. Fine for the current page-15 PoC, not yet robust for heterogeneous guidelines.

---

## Controls that passed audit

1. **Fail-closed current publication state:** source checksum missing -> publication remains blocked.
2. **Canonical vs publication separation:** canonical JSON is not mutated by publish/unpublish.
3. **Emergency unpublish:** tested and removes external visibility while retaining canonical data.
4. **Release atomicity:** tested for missing release items.
5. **Same object/version content conflict:** partial-content hash conflict is tested; should be upgraded to full canonical hash.
6. **Second reviewer separation:** same first/second reviewer is rejected.
7. **AI proposal separation:** proposal schema is separate and canonical transform has no AI write path.
8. **Deterministic semantic transform:** repeated transform output is byte-identical.
9. **Raw extract hash binding:** current raw extract matches the manifest SHA-256.
10. **Retrieval projection from published envelopes only:** unapproved/non-envelope data is blocked.
11. **Empty corpus abstention:** lexical/vector/hybrid all fail closed.
12. **Current synthetic no-answer set:** 6/6 abstain in lexical/vector/hybrid benchmarks.
13. **No secret values found in current committed config/code by grep.**

## Gate decision by layer

| Layer | Audit status | Decision |
|---|---|---|
| Source capture | P0 gaps | BLOCKED |
| Raw extraction | PoC adequate | CONTINUE, needs provenance upgrade |
| Semantic transform | deterministic but manually specified | CONTINUE, not publishable |
| Clinical review | design sound, snapshot/revise gaps | BLOCKED for publication |
| Four-eyes review | basic logic exists | PARTIAL |
| Pre-publication gate | weaker than intended | REPAIR |
| Canonical storage | strong PoC, partial hash weakness | CONTINUE after P0 fix |
| Publication/release | strong local PoC | CONTINUE |
| Retrieval projection | PASS for PoC | CONTINUE |
| Lexical/vector/hybrid retrieval | preliminary benchmark only | CONTINUE |
| Retrieval acceptance | no independent holdout | NOT PASSED |
| PostgreSQL/Azure runtime | not implemented | NOT READY |
| API/chatbot | not implemented | NOT STARTED |

## Recommended repair order

### Repair Gate A - integrity kernel (must be next)
1. Implement full canonical-object hash.
2. Implement exact review snapshot hash.
3. Implement source binary ingest/hash verification.
4. Add per-object source-fragment references and coordinates.
5. Centralize validator with format checking.
6. Centralize publication eligibility policy.

### Repair Gate B - review lifecycle
7. Implement technical review.
8. Implement deterministic revise -> new-version workflow.
9. Reject duplicate review rows.
10. Persist append-only review events.
11. Require reviewed semantic spec + diff.

### Repair Gate C - reproducible repository
12. Add `pyproject.toml` + lockfile.
13. Add Dockerfile and root CLI/README.
14. Fix `run_protocol_v2_checks.sh` to be state-aware.
15. Archive/deprecate v0.x runtime files.
16. Add CI running transform/hash/schema/review/storage/retrieval checks.

### Repair Gate D - scale/acceptance
17. Genericize metadata and source manifest.
18. Add real Storyline decision-tree extraction test.
19. Create independent retrieval holdout + executable acceptance thresholds.
20. Implement PostgreSQL adapter and integration tests.
21. Add audit immutability/RBAC/PII controls before Azure external pilot.

## Recommended immediate decision

**Do not continue directly to API/chatbot or Azure deployment yet.**

Continue technical work, but make the next development sprint the **Integrity Kernel + Review Lifecycle Repair**. Once P0 and P1 integrity items pass, retrieval/API development can continue without carrying unsafe assumptions into the external interface.
