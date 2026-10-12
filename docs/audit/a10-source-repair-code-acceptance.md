# A10 source repair after disposable cache loss

Implementation issue: #609. Acceptance/progress: #560.
Change class: B. Rewrite risk: none. No migration, merge or deployment.

## Findings and scope

Inspected base: `293a69a7e5660e0f222dab3856c59b6494b0c7b9`.
The historical catalog bug is already corrected there: `source_fragment_catalog`
uses `_verified_source_bytes` and `_read_source_fragments`, without formation.
The remaining defect was acceptance of changed existing locator/mapping during
source repair. The installed `/review/resolve` returned 303 and created a new
revision for both synthetic invalid inputs before this patch.

The patch extends the existing catalog's reference checks to locator/page/bbox
and checks proposal-selected mapping against `resolve_source_selection`.
It preserves the existing legacy mapping-version rule. It deliberately does not
require the old object's text to match the proposed correction: repairing text
remains possible. It reuses `_assert_source_work_unchanged` inside the existing
repair transaction to fence preparation against changed source context.
No resolver, creator, status authority, authorization rule or store is added.

## Domain/context contract

| Rule/context | Existing owner/storage | Lifetime and failure rule |
| --- | --- | --- |
| Snapshot/source/document/version/checksum/immutable locator | Existing source envelope and immutable source store | Durable identity; verified immutable bytes determine the source. Cache path is replaceable. |
| Local cache bytes | `OperationsConsole._verified_source_bytes` | Disposable; recovery verifies checksum and changes only cache files. |
| Accepted extraction and fragment mapping | `stored_extraction`, `stored_fragments`, `_read_source_fragments` | Persisted representation wins; corruption blocks, absence selects the supported native historical route. |
| Original/catalog/units | `open_source_passage`, `source_fragment_catalog`, `source_units` | Read only; no model, candidate formation, review/publication or envelope write. |
| Explicit repair and permission | `submit_review_resolution`, `_preflight_structured_repair`, `OperationsConsole.correct_object` | Existing reviewer/named-reviewer and expected revision checks; new proposal requires review. |
| Repair/review/bindings/provenance/evidence | `_atomic_snapshot_mutation`, `_reprocessing_transaction`, `workflow_transaction`, `_commit_prepared_store` | All succeed or roll back. Audit is evidence, never a parallel workflow authority. |
| Stale work/source mapping | Existing expected revision and `_assert_source_work_unchanged` | Reject; preserve winner. No published revision is reopened. |

Aggregate: existing WorkingRevision over one SourceSnapshot. Reads leave durable
state unchanged. A valid explicit repair creates a new object revision with
source-bound provenance, `revision_created`, `review_audit_evidence` and
`needs_review`; source identity and publication state remain unchanged.
Duplicate stale submissions conflict. Failure before or during commit preserves
the prior complete durable object/review/evidence state. Cache files may remain
after a failed command; they confer no domain authority.

Production composition: `console_asgi.build_app` installs the repair and closed
review routes after selecting the workflow console. Local, native complete
PostgreSQL and Azure complete workflow consoles inherit the same catalog/repair
methods. Semantic processing binding installs only the existing mutation
strategy; it does not override this catalog. This is composition inspection,
not an observation of the deployed application.

## Executable evidence

`tests/test_a10_source_cache_repair.py` calls the real composition root and
installed HTTP routes with synthetic isolated sources. It compares complete
catalogs/units, history, source envelope, bindings, revision and audit events.
Both original-first and repair-screen-first cases remove only the old cache and
use a different cacheroot, keeping the old path absent.

Covered representation paths: proposal-selected HTML and PDF with retained
extraction; historical HTML with and without retained extraction; historical
native PDF; retained Docling extraction and historical Docling processing-record
extraction; PDF decision-unit reconstruction; JSON decision-tree freeze.
The Docling producer output is synthetic and translated through the production
contract; these tests prove retained-representation reuse, not Docling model
quality or a real OCR conversion.

The Azure Blob network transport is a disk-backed test transport. The actual
`AzureBlobSourceStore` locator parsing and checksum verification execute. Native
PostgreSQL uses the existing identity/document/review/remaining adapters and
transaction binding. No live Azure resource is contacted. The canonical
publication adapter is not invoked by this unpublished repair slice.

Negative evidence: missing/corrupt immutable bytes with empty cache; missing and
hash-changed fragment references; changed locator or selected mapping; stale
revision; source-context change after preparation; late audit exception; native
SQL statement failure on object revision and deferred SQL audit failure at
commit. Fresh-runtime reads check for complete rollback; a subprocess verifies
retained units and durable state after cache loss and process restart.

Historical execution: the cache-move/original-first/selected-HTML probe runs on
`e6503b92` and fails with `freeze_bytes_missing` in the old catalog, after ingest
and initial source-unit reads succeed. That is executable historical evidence,
not a simulated catalog. Earlier `45ac215a` lacks the retained-extraction fixture
contract and failed setup; that attempt is not counted as red/green evidence.

## Boundaries of acceptance

Code inspection, isolated executed evidence and production acceptance are
separate. The deployed revision, Azure credentials/network behavior and a real
user's production repair remain unverified. #560 must stay open with deployment
and production completion unchecked. Full-suite skips and pre-existing failures
must be reported separately from A10 results.

## Executed verification, 12 October 2026

Tested code/test revision: `224468f6330b55474cdf568b61ccb481e6880690`.
The subsequent documentation commit records results without changing product
code or tests. Python 3.12.14; native PostgreSQL 16.15 on isolated loopback.
This root-only execution environment required a local UID/file-ownership shim
for PostgreSQL startup; SQL adapters, constraints, transactions and commit
failures remain native. CI uses its existing standard PostgreSQL 16 service
and Python 3.12/3.13 matrix; CI results are not claimed here.

| Command/check | Executed result |
| --- | --- |
| `METIS_TEST_POSTGRES_DSN=<isolated test database> python -m pytest -q tests/test_a10_source_cache_repair.py --junitxml=<scratch evidence>` | **60 passed; zero skips, errors or failures.** Valid HTML/PDF selections deliberately shorten the passage, rather than merely repeating unchanged text. |
| Same negative locator/mapping/preparation probes on base `293a69a7`, separately for local and native PostgreSQL | **3 expected failures on each backend**: HTTP 303 silently accepts the invalid/stale input. All three are green in the patched 60-case probe. |
| Historical original-first/selected-HTML cache-move probe on `e6503b92` | **Expected `freeze_bytes_missing` failure** in the old catalog. Same probe green on current/patched code. |
| Native PostgreSQL supporting tests: `tests/test_a09_source_repair.py tests/test_deterministic_review_repair_v1.py tests/test_review_closure_v1.py tests/test_v3_proposal_repairs.py tests/test_selected_source_context_closure.py` | **98 passed; zero skips.** These exercise existing overlapping revision writers and repair/re-review contracts. |
| `tests/test_deterministic_review_repair_v1.py tests/test_source_bound_continuation_repair.py tests/test_decision_release_source_repair.py tests/test_docling_contract_v1.py tests/test_architecture_invariants.py` | **67 passed, 6 skipped** before native supplemental execution; skips require their separate native test environment. |
| `python -m pytest -q tests/test_architecture_invariants.py` | **6 passed.** |
| `python scripts/repository_preflight.py` | **PASS.** |
| `python scripts/release_control_preflight.py --base origin/main` | **PASS on committed diff**, with concrete test evidence metadata. |
| `python -m compileall -q src` | **PASS.** |
| `python scripts/check_architecture_boundaries.py` | **PASS.** |
| `python -m pytest -q` on final code/test revision | **3454 passed, 410 skipped, 4 failed** in 284.91 seconds. No full-suite success claim. |

The four final full-suite failures were independently reproduced on unchanged
base `293a69a7`: `test_parent_process_death_terminates_transport_worker` and the
three `test_security_harden_wave3.py` HTTPS-SNI/redirect SSRF tests. Their cause
and production impact are outside A10 and are not resolved by this PR. Most
full-suite skips require PostgreSQL/Docling/external environments; the dedicated
A10 and supporting native repair runs above do not skip their storage cases.
An initial full run caught two incorrect decision-PDF test expectations: the
existing decision-unit contract retains a newline between source lines. The
fixture expectations were corrected to preserve that contract; product behavior
was not relaxed. Only the final full-run totals above describe the final tests.

Production method-binding inspection confirms the Azure and non-Azure complete
PostgreSQL classes share `source_fragment_catalog`, `source_units`,
`submit_review_resolution`, `_verified_source_bytes` and `_read_source_fragments`.
It does not prove the deployed revision or physical Azure transport.

Surface review: **APPROVE WITH NOTES** for this A10 diff. The product extension is
21 lines in the existing owner, without a new helper/authority/store. The mapping
comparison uses the existing resolver and retains its historical version rule;
the text-repair permission is preserved. Catalog and repair orchestration already
have high branching, so locality is preferable to spreading this bounded check
over new abstractions. No unrelated refactor was added. Engineering evidence
supports A10 review within the isolated tested compositions; overall release/CI
readiness remains open because of the four reproduced baseline failures and
unverified production conditions.
