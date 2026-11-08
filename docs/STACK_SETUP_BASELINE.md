# V&VN Data Services — Stack and setup baseline

**Status:** working technical inventory
**Date:** 2026-08-24
**Storage-route refresh:** 2026-11-08, KO-5 (#1012); repository implementation only, no provisioning or deployment assertion.
**Scope:** current repository baseline and infrastructure dependencies visible in code/protocol
**Purpose:** make setup, vendor, account, persistence and cost dependencies visible before they become implementation blockers or budget surprises.

This document is descriptive, not a vendor commitment. The approved normative baseline is Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.11.0 remains an approved component of that baseline. Protocol v2.10.0 remains an approved component of that baseline. Protocol v2.9.0 remains an approved component of that baseline.

## 1. Current architecture in one view

```text
GitHub repository WilliamGomes41/VENVN-DS + GitHub Actions
        (MAY be public during the declared MVP period; G1 protection follows)
        |
        v
Python 3.12/3.13 application
FastAPI + Uvicorn Product API
        |
        +--> local/derived retrieval files
        +--> local char-TFIDF retrieval provider
        +--> PostgreSQL canonical/publication store and serving registry
        +--> local SQLite usage ledger
        +--> in-process rate limiter
        +--> locally mounted canonical source binaries
        +--> operations console (FastAPI HTML; PostgreSQL workflow/identity/review state)

External/Azure operation still requires explicit hosting, capacity and operational
configuration; this repository inventory does not assert that resources are provisioned.
```

The G0 local operations console MVP is implemented in this repository (`vvn-data-service serve-console`). Protocol v2.6 authorizes that internal operations console as scope. Protocol v2.7 keeps those console rules and records: No LLM in the MVP; the Product API is object-level retrieve-and-abstain and MUST NOT generate prose. Protocol v2.8 keeps those rules and records: do not build a mockup; Continentie bron 2 enters through that console; local `sources/private/` is the G0 stand-in until G0 Azure DEV; the Product API already exists and MUST NOT be rebuilt first; RAG on kennisplatform HTML is not the product. Protocol v2.9 adds researcher-task UX and V&VN digital stylesheet rules; that rewrite is now in code (PR #25), including the official beeldmerk. Protocol v2.10 adds Documentenhierarchie (UI heading; kernel remains family × class), waiting-task badges, and an Accounts room (publisher as MVP identity admin; closed role set); that follow-up remains required and is not the next implementation after Protocol v2.12. Protocol v2.11 requires official first-wave HTML as an uploaded freeze file, rejects live URL-HTML at ingest, requires source locators on knowledge objects, and fail-closes Product API `supported` without a locator; that kernel work is not implemented in this protocol change. Protocol v2.12 adds object-type default unclassified, answerability as question type × object type, publish binding to the object tuple, and serving from an atomically replaced published projection; that follow-up is not implemented in this protocol change. Azure/G2 stay out of this delta. The Product API contains no LLM/generation layer. Vercel, Neon and a hosted LLM are therefore **not** current V&VN Data Services requirements. No identity vendor is selected. No Vercel, Neon, or LLM vendor.

## 2. Dependency inventory

| Capability | Current implementation | Target / production implication | Required by | Cost/setup exposure | Status |
|---|---|---|---|---|---|
| Authoritative code | GitHub repository `WilliamGomes41/VENVN-DS` (public during the declared MVP period under Protocol v2.5) | After MVP restore private hosting or an organization plan that can protect a private default branch | G1 | Current free personal plan cannot protect a private default branch (403); public MVP is the accepted workaround | **Implemented:** G1 technical protection is ON |
| CI | GitHub Actions, Python 3.12/3.13; isolated Playwright 1.58.2 + Chromium review checks on 3.12 | Continue clean lockfile install, preflight, compile and tests; browser tooling is ephemeral and uses only synthetic fixtures | G1 | Existing GitHub usage; browser checks add runner minutes and package downloads, no hosted service or product runtime dependency; monitor quota/plan | Implemented |
| Runtime language | Python `>=3.12,<3.14` | Pin supported runtime in deployed container | G1/G8 | No separate service cost | Implemented |
| Packaging/runtime image | Docker, `python:3.13-slim` | A managed Azure container/web runtime must be selected before Azure DEV | G8 | **New hosting cost likely** | Decision open |
| Container image registry | None required locally | May be needed depending selected Azure deployment route | G8 | Possible registry/storage cost | Decision open; do not assume ACR until runtime is chosen |
| Product API | FastAPI + Uvicorn | Externally reachable machine-to-machine API | G8 | Included in runtime; network/ingress may add cost | Implemented locally |
| Canonical source binaries | Local file supplied to source registry; binaries excluded from Git. Local `sources/private/` is the G0 Local substitute and is explicitly not production. Azure Blob `aidataservice` / private container `canonical-sources` (West Europe) is the G2 store; locator `azure://aidataservice/canonical-sources/{sha256}/{filename}`; adapter in `src/g2_source_store.py`; runtime SDK `azure-identity==1.25.3` and `azure-storage-blob==12.30.1` required; container empty as of 2026-09-01; G2 remains BLOCKED; `publish()` remains fail-closed | Controlled immutable source store on **Azure Blob Storage**. Console ingest (Protocol v2.6) requires this store | G2/G8 / console ingest | Existing V&VN Azure subscription; storage cost after first source | Adapter exists; SDK in runtime deps; Blob store provisioned empty; G2 BLOCKED; G0 Azure DEV remains BLOCKED |
| Internal operations console UI | Implemented locally: FastAPI HTML console in this repository (`vvn-data-service serve-console`; ingest, family tree, review return-loop; publish room fail-closed without G2). Not a care-app frontend, chatbot, EPD/ECD UI or public website. Chat is not a room. Primary users are guideline researchers, not nurses | Keep the in-repo HTML console for G0 Local. Azure host **TBD**; Vercel is not required. Local `sources/private/` is the G0 stand-in | Protocol v2.6 / v2.8; G0 Local implemented; G2 still BLOCKED | **0 incremental hosted-UI cost locally**; Azure hosting cost TBD | G0 local implemented; G0 Azure DEV remains BLOCKED; no vendor is selected for Azure |
| Console identity (accounts/roles) | Implemented locally: researcher, reviewer, publisher; no shared login; uploader independence enforced in accounts. Runtime identity authority is PostgreSQL `workflow`; the gitignored `output/runtime/` directory is not its state store | Internal identity, not public signup. Azure provider **TBD** and subject to G0. Does not close G8 or provision Azure AD | Protocol v2.6 C5 / G0 / G8 | **0 current identity-service cost**; Azure identity cost TBD | G0 local implemented; no vendor is selected for Azure; G0 Azure DEV remains BLOCKED |
| Canonical/publication database | Existing PostgreSQL canonical object/release store and serving registry in `src/publication/canonical_publication_postgres_v1.py`; console workflow/review authority is also PostgreSQL. The SQLite publication pilot is retired by KO-5 | Managed database hosting, sizing, retention and operational configuration for the selected deployment | G8 | **Managed database cost must be budgeted** | Runtime implementation exists; no provisioning/deployment claim |
| Usage ledger | Local SQLite | Shared durable usage/audit backend for multi-replica production | G8 | Could share production DB or use separate observability/data service | Decision open |
| Tenant registry | Local JSON containing only API-key hashes; real tenant config excluded from Git | Production tenant/config store and controlled secret provisioning | G8 | Secret/config service may add cost | Decision open |
| Secrets and workload identity | Environment/managed-identity boundary described in provider contract; no production implementation | Select V&VN-approved secret management and workload identity; no plaintext repository secrets | G8 | Possible secret-management cost | Decision open |
| Rate limiting | In-process sliding window | `product_security_v1.py` explicitly requires APIM/Redis or distributed equivalent for distributed deployment | G8 / external traffic | **Potentially material new service cost** | Decision open |
| API gateway | Not required for local pilot | Azure API Management is named as one possible production rate-limit boundary, but is not yet a committed dependency | G8 / external traffic | Potentially material cost | Architecture decision open |
| Retrieval embeddings | Deterministic local char-TFIDF; no remote credentials | Hosted embedding provider is optional future C4 work, not required for current Product API | G6+ / future C4 | Usage-based model/API cost if adopted | **Not required now** |
| LLM / Answer-RAG | None in Product API | Separate optional future layer governed by G7/C6 | G7 only | Usage-based model cost if later approved | **Not required now** |
| Monitoring/alerting | No production monitoring implementation | Monitoring, incident visibility and operational alerting are mandatory for G8 | G8 | May add Azure monitoring/log-retention cost | Decision open |
| Backup/recovery | Existing PostgreSQL workflow and publication-chain backup, restore and integrity owners; immutable source bytes retain their source-store authority. See `docs/RUNTIME_DATA_RECOVERY.md` | Configure and verify backup storage, retention and recovery for the selected deployment; local files are not workflow/publication authority | G8 | Storage/retention cost | Recovery implementation exists; operational configuration and verification remain deployment-specific |
| Domain/TLS | Local API endpoints | Azure-managed endpoint may suffice for pilot; custom domain/DNS/certificate only if governance/product requires it | G8 if externally exposed | Conditional | Not yet required |
| Infrastructure as code | No Bicep/Terraform/`azd` deployment baseline found | Deployment resources/configuration should become reproducible before production | G8 | Engineering/setup effort; service costs captured above | Not implemented |

### Optional Bend development experiment

Bend 2.0.37 is an optional development tool for `experiments/bend/` (#773).
The repository stores a version- and checksum-pinned upstream installer; the
Codespace workspace installs it after creation. A path-filtered GitHub Actions
workflow runs the demonstration proof. Existing Codespaces need a rebuild or
manual installation. The isolated security runner and production runtime are
unchanged. No account, secret, hosted model, or additional managed service is
required; normal Codespaces/Actions compute quotas still apply. The default
upstream version-check telemetry is disabled in the configured workspace and CI.
The example verifies only its own Bend law, not the existing Python application.
PR-D2 (#775) adds a checksum-pinned Lean 4.34.0 download (about 580 MB) to the
dedicated CI job for the independent BendTT kernel check and bounded console
conformance tests. Lean is proof tooling only, with no runtime service or
production dependency. See `experiments/bend/README.md` and
`experiments/bend/pr_d2/README.md` for setup and proof limits.

### Test PostgreSQL for laptops and cloud coding agents

PostgreSQL tests use `scripts/test_postgres.sh`: a reachable
`METIS_TEST_POSTGRES_DSN` is reused; otherwise it starts PostgreSQL 16 on a free
loopback port in a unique temporary directory, with UTC timezone. Root uses
`postgres` or `nobody` as server owner. The script prints only the DSN.
Pytest invokes it during collection and fails once if console/PG tests cannot
obtain a database. Pure-function selections can run without PostgreSQL.

`scripts/agent_env_setup.sh` remains a compatibility entry point for
`scripts/setup_test_environment.sh`. Setup installs the binaries and Python
dependencies; the server starts in the agent phase. Set persistent
`PGBIN=/usr/lib/postgresql/16/bin` in Codex environment settings. Cursor cloud
uses `.cursor/environment.json`; local Cursor uses installed PostgreSQL 16 or
an explicitly configured Docker DSN.

See [the shared PostgreSQL test instructions](agents/postgres-tests.md) for
startup, cleanup, environment verification and local console startup.
No managed service, account or secret is involved. The existing CI quota covers
these measurements; run the portions sequentially and give #695 priority. The
local/test dependency is declared as `test-postgres-local` in the infrastructure
manifest. Since D6b the local console itself also runs only on PostgreSQL; there
is no file topology.

## 3. Most likely budget surprises if left implicit

### 3.1 Production hosting is not yet selected

The Dockerfiles prove the service is container-ready, but they do not select or provision an Azure runtime. A future Azure DEV step will therefore require an explicit hosting decision and account/subscription access. This should be budgeted before deployment work starts.

### 3.2 Two different kinds of durable storage are already implied

They solve different problems:

1. **Object/file storage** for the exact canonical PDF/HTML/binary source bytes. The target architecture already names Azure Blob Storage.
2. **Relational database storage** for canonical object versions, releases, publication registry, workflow/review and audit state. PostgreSQL is the existing runtime authority, not only a reference schema; the SQLite publication pilot has been retired. The separate local SQLite usage ledger is not canonical/publication storage.

One does not replace the other.

### 3.3 The current API security/runtime components are deliberately single-process

The current rate limiter and usage ledger work locally, but not as a reliable shared state layer across multiple replicas. External/multi-replica use therefore creates an additional infrastructure choice: API Management, Redis/distributed rate limiting, a shared database implementation, or an approved equivalent.

### 3.4 Hosted embeddings are a choice, not a hidden prerequisite

The current retrieval stack works with a deterministic local char-TFIDF provider. A remote embedding provider must not be introduced merely because it is common in RAG architectures. If later evidence justifies it, it is a C4 change with its own provider, privacy, region, cost and acceptance decision.

### 3.5 A chatbot/LLM is not part of the current service

The Product API returns published V&VN evidence to consumers and explicitly performs no generation. A future Answer/RAG layer is separate. This prevents model/API expenditure from being treated as an unavoidable setup cost for the current Data Services pilot.

### 3.6 An internal operations console is implemented locally, not hosted on Azure

Protocol v2.6 authorizes an internal operations console (ingest, review, publish, later analytics) as a human surface over the knowledge kernel. The G0 local console MVP (ingest + family tree + review return-loop) is implemented in this repository; Azure hosting is not implemented. Identity (researcher / reviewer / publisher) is a required console capability; no vendor is selected for Azure; Azure AD is not provisioned; G8 is not closed. Vercel, Neon and a hosted LLM are not required. Protocol v2.8: do not build a mockup; Continentie bron 2 enters through that console; local `sources/private/` is the G0 stand-in until G0 Azure DEV; publication remains BLOCKED without an immutable locator (G2). Durable immutable storage is not skipped. Protocol v2.9: the console UX rewrite on the existing kernel (task-oriented researcher surface + V&VN digital stylesheet + official beeldmerk) is now in code (PR #25); not Azure, not Vercel/Neon, not a mockup. Protocol v2.10: the next implementation is a console follow-up on that v2.9 UX (Documentenhierarchie, waiting-task badges, Accounts room); that follow-up remains required. Protocol v2.11: uploaded HTML freeze, reject live URL-HTML at ingest, mandatory source locators, fail-closed Product API `supported` without a locator; that kernel work remains required law and is not a supersession of v2.12 §10. Protocol v2.12: the next implementation is object taxonomy / answerability × type / object-tuple review / atomic published projection on the existing kernel; THEN G2/Azure. G2 remains the publication blocker. No Azure in this delta.

## 4. Decisions that should be made before Azure DEV spending

Before creating paid Azure resources, record at minimum:

1. chosen Azure runtime/deployment product and region;
2. whether an image registry is required and where images are retained;
3. source-binary object store, immutability/retention and region;
4. production relational database product, sizing class and backup retention;
5. tenant secret/configuration and workload-identity solution;
6. rate-limit/API-gateway architecture for the expected pilot topology;
7. usage/audit persistence and retention;
8. monitoring/logging service and retention;
9. expected DEV and pilot monthly cost range, cost owner and spending alert/budget;
10. explicit statement on hosted embeddings: `not used` or selected provider/model with cost/data boundary;
11. operational owner and recovery/withdrawal responsibilities.

Unknown values should remain visibly `TBD`; they must not be silently filled in during implementation.

## 5. Source evidence in the repository

This inventory is derived from the current repository, especially:

- `docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md` — internal operations console scope; identity as a required console capability; no vendor selected.
- `docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md` — first-wave source, object-level retrieve-and-abstain API, live subscription product; no LLM in the MVP; no Vercel, Neon or LLM vendor.
- `docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md` — primary users, class×family source hierarchy, real console-MVP build order on the existing kernel; RAG on kennisplatform HTML is not the product.
- `docs/PROTOCOL_V2_9_CONSOLE_UX_BRAND_DELTA.md` — researcher-task console UX and V&VN digital stylesheet; licensed fonts not in repo; fail-closed system fallback; no Canva PDF in git.
- `docs/PROTOCOL_V2_10_CONSOLE_NAV_ACCOUNTS_DELTA.md` — Documentenhierarchie heading, waiting-task badges, Accounts room; closed role set; publisher is MVP identity admin; CLI `console-account` bootstrap remains valid.
- `docs/PROTOCOL_V2_11_HTML_FREEZE_LOCATOR_DELTA.md` — uploaded HTML freeze file; reject live URL-HTML at ingest; mandatory source locators; fail-closed Product API `supported` without a locator; no Azure/Vercel/Neon.
- `docs/PROTOCOL_V2_12_OBJECT_TYPE_REVIEW_PROJECTION_DELTA.md` — unclassified default, closed object-type set, answerability × type, object-tuple publish binding, atomic published projection; Azure/G2 out of this delta.
- `Dockerfile` and `Dockerfile.product-api` — Python/container runtime;
- `pyproject.toml` and lockfiles — pinned Python stack;
- `src/operations_console_v1.py` and `src/operations_console_app.py` — PostgreSQL-backed console orchestration and HTML routes;
- `src/publication/canonical_publication_postgres_v1.py` and `src/workflows/workflow_document_concurrency_v1.py` — existing PostgreSQL canonical/publication and workflow authorities;
- `src/workflows/workflow_chain_recovery_v1.py`, `src/publication/publication_chain_recovery_v1.py`, `scripts/publication_chain_recovery.py` and `docs/RUNTIME_DATA_RECOVERY.md` — workflow/publication backup, restore and integrity owners;
- `src/product_api_v1.py` — registry-backed Product API serving; `src/usage_ledger_v1.py` — separate local SQLite usage accounting;
- `src/product_security_v1.py` — in-process rate limiting and APIM/Redis replacement boundary;
- `src/retrieval/semantic_vector_retrieval_v1.py` and `config/vector_retrieval_v1.json` — active local deterministic character TF-IDF retrieval; no hosted embedding provider or credentials are used;
- `CONTRIBUTING.md` and `docs/REPOSITORY_CONVENTIONS.md` — controlled source binaries outside Git and Azure Blob target;
- `docs/history/PRODUCT_API_V1_REPORT.md` and `docs/history/FULL_TECHNICAL_AUDIT_2026-08-19.md` — Azure/multi-replica and production adapter gaps.

## 6. Maintenance rule

This baseline should be updated in the same pull request whenever code or protocol introduces, removes or materially changes an external service, paid plan, durable data store, hosted model/provider, runtime platform, account-level permission requirement or operational dependency.
