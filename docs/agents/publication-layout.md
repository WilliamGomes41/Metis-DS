# Publication code navigation (#897)

Change class: C. Rewrite risk: none. This package groups existing code for
discoverability; it introduces no domain, component, authority, or schema.

## Inventory and caller trace

All paths below are relative to `src/publication/`.

| Modules | Existing responsibility and callers |
| --- | --- |
| `publication_readiness_v1.py` | Read-only readiness mixin used by `OperationsConsole`, document status, review and selection views. |
| `publish_authorization_v1.py` | Exact-object approval bindings used by review, workflow persistence, publication and recovery. |
| `publish_refusal_audit_v1.py`, `publication_refusal_store_v1.py` | Publication refusal recording and retention; called by the console, durable publish boundary, audit export and retention script. |
| `durable_publication_console_v1.py`, `azure_authoritative_publication_console_v1.py` | Existing console inheritance and locked publish/source-verification boundary; instantiated by `console_asgi.py`. |
| `canonical_publication_postgres_v1.py` | Existing canonical publication store and registry; used by console composition, Product API, compiled knowledge and workflow/recovery adapters. |
| `published_projection_v1.py` | Published JSONL projection used by console and Product API; remains derived from the registry. |
| `publish_readiness_ui_v1.py` | Publication and withdrawal routes installed by `console_asgi.py`; existing HTTP paths remain unchanged. |
| `publication_evidence_v1.py` | Operational publication evidence from existing publish boundaries; read by the incident-export script. |
| `publication_chain_recovery_v1.py`, `publication_chain_recovery_guard_v1.py` | Existing publication backup, integrity and guarded restore; composed by the workflow recovery adapter. |
| `legacy_canonical_recovery_v1.py` | Legacy-release proof and recovery through the existing publication store; used by `scripts/publication_chain_recovery.py`. |
| `prepublication_gate_v3.py`, `eligibility_policy.py` | Pre-publication evaluation and its publication-only eligibility policy; used by `src.cli` and the gate CLI. |
| `canonical_store.py` | Legacy SQLite pilot publication kernel and CLI; production remains PostgreSQL. |

Shared composition (`console_asgi.py`, `operations_console_v1.py`,
`operations_console_app.py`), source stores (`g2_source_store.py`), integrity
(`integrity_kernel.py`), runtime inventory and generic audit stores remain in
place. `product_source_authority_v1.py` verifies source bytes on the serving path;
`compiled_knowledge_v1.py`, `serving_relations_v1.py` and `retrieval/` remain shared
serving/retrieval code. `workflows/workflow_chain_recovery_v1.py` composes recovery
for all workflow state and stays with workflows. `protocol_approval_manifest.py`
records protocol-document approvals rather than knowledge publication.

## Compatibility and proof

Repository imports and live source-path checks use `src.publication`. The package
is explicitly included in the distribution. Existing operator scripts, the
`vvn-data-service` entry point and HTTP routes keep their names. The historical
`python -m src.canonical_store` and `python -m src.prepublication_gate_v3` CLI
entry points delegate to the moved implementation. New module entry points also
work. Internal Python import locations move; no serialized Python module identity
is used by the publication JSON/SQL/backup formats. Stored schema, hashes, backup
format identifiers and source locators are unchanged. Historical evidence and
protocol records retain their original source paths.
The shared rollback-test child selects the module layout of its checkout,
including the pinned pre-package publication, review and settings paths.

Import/packaged-install checks detect missing modules and circular dependencies;
CLI checks detect broken supported entry points. Existing publication,
authorization/refusal, serving/withdrawal and real PostgreSQL backup/recovery
tests prove the affected behavior. Run the repository preflights, architecture
checks, compilation and full suite before submitting the PR. These checks do not
claim a deployment or production exercise.
