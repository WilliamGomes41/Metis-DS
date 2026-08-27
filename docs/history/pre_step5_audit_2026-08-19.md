# Pre-step-5 technical audit - 2026-08-19

## Verdict
Do not start production step 5 yet. The pilot logic is sound, but the pipeline is not fully reproducible and the expert-review workbook is not yet connected to the validation code.

## Passed checks
- All Python source files compile.
- Semantic output contains 20 unique objects.
- All 20 objects validate against JSON Schema v0.2.
- All parent references resolve within the semantic dataset.
- All semantic content hashes are consistent.
- All 20 objects remain `needs_review`.
- Validation gate was tested with simulated approve/reject/revise decisions.
- Approved objects pass the storage gate.
- Unapproved objects are rejected by retrieval-record generation.

## Blocking findings

### A1 - Missing reproducibility inputs - BLOCKER
Referenced but absent from the project directory:
- `data/raw/VVN-RL-Osteoporose-1.3.pdf`
- `data/semantic_page15_spec.json`

Consequence: steps 2 and 3 cannot be rerun end-to-end from the current project package.

Required fix: restore/persist the raw source and semantic spec (or replace the spec with a reproducible transform from source extraction).

### A2 - Step 3 is partially manual - BLOCKER for scaling
`semantic_transform.py` transforms a pre-authored semantic specification. It does not derive the semantic structure directly from the raw PDF objects.

Consequence: the current result proves the target representation, but not yet a scalable semantic extraction pipeline.

Required fix: preserve explicit provenance from each semantic object back to raw block IDs/source coordinates, and define how semantic specs are generated/reviewed.

### A3 - Confirmed semantic transcription discrepancy - BLOCKER before approval
The semantic dataset contains:
`Roken en/of alcohol > 3 eenheden per dag` (`operator=gt`).
The current official V&VN Kennisplatform source states:
`Roken en/of alcohol >= 3 eenheden per dag`.

Consequence: one machine-readable threshold is incorrect. This validates the need for source-grounded review and means the current validation workbook must not be treated as final until corrected/reissued.

Required fix: correct the source-grounded spec/output to `>= 3`, rerun semantic output and regenerate the expert workbook.

### A4 - Expert Excel is not machine-ingestible - BLOCKER
`validation_workflow.py` reads a semicolon-delimited CSV with internal column names such as `review_decision` and `review_comment`.
The expert workbook uses Dutch display columns such as `Beoordeling*`, `Voorgestelde correctie`, and `Toelichting / reden`.

Consequence: the returned expert Excel cannot currently be fed directly into the validation workflow.

Required fix: add an XLSX review importer/adapter, or make `validation_workflow.py` read the workbook directly. The importer should map reviewer/date and proposed corrections explicitly.

## Important non-blocking findings

### A5 - Claimed automated tests are not persisted
No `test_*.py` files are present, although README files state that automated tests exist/pass.

Required fix: create a committed pytest suite for schema validation, parent integrity, review decisions, storage gate, and retrieval gate.

### A6 - Missing step-5 configuration file
`docs/history/STEP5_PREP_README.md` references `config/step5.yaml`, but the file/directory is absent.

Required fix: create the config file or remove the claim from documentation.

### A7 - Storage gate does not revalidate the full object
`storage_prepare.py` checks approval, reviewer/date, and IDs but does not validate against JSON Schema, check content hashes, or parent references.

Required fix: add schema/integrity validation before authoritative storage.

### A8 - Revision flow is incomplete
A `revise` decision stays pending, but proposed corrections from the Excel workbook are not applied or preserved by `validation_workflow.py`.

Required fix: create an explicit revision queue and require re-review after content changes.

### A9 - Provenance can be stronger
Semantic objects point to page 15 but do not currently retain source bounding boxes or raw-object IDs from step 2.

Required fix: add `derived_from_object_ids` and/or source coordinates for auditability.

## Step-by-step audit status

| Step | Status | Audit conclusion |
|---|---|---|
| 1 - schema/extraction rules | PASS WITH IMPROVEMENTS | Sound pilot schema; compound clinical logic/provenance can be strengthened. |
| 2 - PDF extraction | PASS, NOT REPRODUCIBLE FROM PACKAGE | Code/output valid; raw PDF is absent. |
| 3 - semantic structuring | CONDITIONAL / BLOCKED | Output structurally valid, but source spec is missing, process is partly manual, and one threshold discrepancy was found. |
| 4 - expert validation gate | LOGIC PASS / INTEGRATION BLOCKED | Gate works in simulation; expert XLSX is not connected to the script. |
| 5 preparation | PARTIAL PASS | Gate/retrieval skeleton works; tests/config/storage integrity checks need completion. |

## Gate to start step 5
Start step 5 only after A1, A3 and A4 are resolved. Resolve A5-A8 before calling the pilot reproducible or production-ready.
