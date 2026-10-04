# Reusing Metis domain contracts

This is a code navigation and dependency contract. Lifecycle semantics remain in
`docs/agents/lifecycle-vsa.md`; change classification and domain-first design remain
in `docs/agents/continuous-development.md`. Do not duplicate those rules here.

## Find the existing owner before editing

| Behavior | Existing owner to inspect | Relevant proof |
| --- | --- | --- |
| PDF extraction and accepted source representation | `src/docling_pdf_v1.py::extract`, `src/docling_contract_v1.py::translate` and `stored_fragments`; SDK execution in `src/docling_worker_v1.py` | `tests/test_docling_contract_v1.py` |
| Source reconstruction for subsequent review or repair | `src/operations_console_v1.py::OperationsConsole._read_source_fragments` and `_fragments_and_spec` | `tests/test_docling_contract_v1.py` |
| Canonical hashes and review snapshot identity | `src/integrity_kernel.py::compute_canonical_object_hash` and `exact_review_snapshot_hash` | `tests/test_architecture_invariants.py` |
| Candidate eligibility and admission | `src/candidate_eligibility_v1.py::assess_candidate_eligibility`; `src/admission_gate_v1.py::admit_candidate` and `apply_admission_gate` | `tests/test_v230_phase1_admission_gate.py` |
| Derived review obligations | `src/review_duty_v1.py::review_duty_for` and `review_duty_counts` | `tests/test_v219_review_duty_queue.py` |
| Readiness versus authorized publication | `src/publication_readiness_v1.py::PublicationReadinessMixin.publication_readiness` and `consider_publish`; `src/durable_publication_console_v1.py::DurablePublicationConsole._publish_locked` | `tests/test_vsa_code_boundaries_v1.py`, `tests/test_vsa_publish_document_v1.py` |
| Production serving authority | `src/azure_authoritative_publication_console_v1.py::AzureAuthoritativePublicationConsole._projection_from_authority`; composition in `src/console_asgi.py` | `tests/test_azure_blob_publication_authority_v1.py`, `tests/test_publication_registry_serving_authority_v1.py` |
| Durable workflow commits and concurrent object writes | `src/workflows/workflow_transaction_v1.py::workflow_transaction`; `src/workflows/workflow_document_concurrency_v1.py::PostgresConcurrentWorkflowDocumentStore.write_bundle`; local store boundary `src/operations_console_v1.py::OperationsConsole._commit_prepared_store` | `tests/test_workflow_transaction_v1.py`, `tests/test_workflow_postgres_concurrency.py` |

These are entry points for investigation, not an exhaustive writer/reader map.
Follow callers, mixin method resolution, runtime overrides, and supported storage
topologies for the assigned change. A function named `consider_publish` is not
permission to bypass `publish` or the durable publication boundary.

## Use the smallest appropriate workflow

1. Classify the change and rewrite risk under the existing development model.
2. Read the relevant owner and its current tests; trace the actual execution path.
3. State the named invariant or duplicated decision the change addresses. For a
   stateful change, apply the existing domain-first fields before choosing a slice.
4. Reuse the existing domain operation. If it cannot express the behavior, explain
   why before extending it. Do not add generic status setters or a second gate.
5. If adding an abstraction, give it a domain responsibility, a narrow input/output
   contract, and one observable proof. Preserve relevant route and source differences.
6. Run the dependency check and the tests appropriate to the change. Update this
   map when a listed owner moves; do not fix a failing check with a blanket exception.

The existing `.agents/skills/improve-codebase-architecture/` skill remains an
explicitly invoked survey tool. Ordinary changes use this map and the development
model; no separate personal skill installation is required.

## Enforced dependency boundaries

`python scripts/check_architecture_boundaries.py` scans every Python file under
`src/`, including imports inside functions and conditional branches.

- Only `src/docling_worker_v1.py` may import `docling` or `docling_core`. Failure
  prevented: importing the heavyweight SDK into the API process bypasses the
  bounded worker and breaks the lightweight runtime dependency contract.
- `docling_contract_v1`, `integrity_kernel`, `candidate_eligibility_v1`,
  `object_taxonomy_v1`, and `recommendation_semantics_v1` may not directly import
  HTTP frameworks/clients, database/cloud SDKs, or the listed application/storage
  adapters. Failure prevented: a reusable validation/identity contract starts
  depending on deployment, credentials, or an HTTP application to evaluate data.

The rule lists live in the checker rather than a second policy configuration.
Regression tests inject invalid dependencies and check that the scanner rejects
them. CI runs the scanner before the product test job.

This is a static direct-dependency check. It resolves ordinary and relative
imports and literal `importlib.import_module`/`__import__` calls, including common
aliases. It does not prove transitive purity, prohibit every possible reflection
mechanism, or validate state transitions. Runtime authorization, source fidelity,
transactions, recovery, and publication invariants still require their existing
domain checks and behavioral tests.

`OperationsConsole` is backend orchestration despite its name; `console_asgi.py`
is the composition root. Do not ban imports merely because a module contains
the word console. HTTP/session presentation may not become a new durable authority.
