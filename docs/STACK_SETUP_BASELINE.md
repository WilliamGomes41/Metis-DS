# V&VN Data Services — Stack and setup baseline

**Status:** working technical inventory
**Date:** 2026-08-24
**Scope:** current repository baseline and infrastructure dependencies visible in code/protocol
**Purpose:** make setup, vendor, account, persistence and cost dependencies visible before they become implementation blockers or budget surprises.

This document is descriptive, not a vendor commitment. The approved normative baseline is Protocol v2.7.0.

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
        +--> local SQLite canonical/publication store
        +--> local SQLite usage ledger
        +--> in-process rate limiter
        +--> locally mounted canonical source binaries

Target external/Azure operation requires replacing several local pilot components
with durable, shared and operationally managed services.
```

The repository currently contains no frontend application. Protocol v2.6 authorizes an internal operations console as scope; that console is not implemented and MUST NOT be claimed as existing code. Protocol v2.7 keeps those console rules and records: No LLM in the MVP; the Product API is object-level retrieve-and-abstain and MUST NOT generate prose. The Product API contains no LLM/generation layer. Vercel, Neon and a hosted LLM are therefore **not** current V&VN Data Services requirements. No identity vendor is selected. No Vercel, Neon, or LLM vendor.

## 2. Dependency inventory

| Capability | Current implementation | Target / production implication | Required by | Cost/setup exposure | Status |
|---|---|---|---|---|---|
| Authoritative code | GitHub repository `WilliamGomes41/VENVN-DS` (public during the declared MVP period under Protocol v2.5) | After MVP restore private hosting or an organization plan that can protect a private default branch | G1 | Current free personal plan cannot protect a private default branch (403); public MVP is the accepted workaround | **Implemented:** G1 technical protection is ON |
| CI | GitHub Actions, Python 3.12/3.13 | Continue clean lockfile install, preflight, compile and tests | G1 | Usually existing GitHub usage; monitor quota/plan | Implemented |
| Runtime language | Python `>=3.12,<3.14` | Pin supported runtime in deployed container | G1/G8 | No separate service cost | Implemented |
| Packaging/runtime image | Docker, `python:3.13-slim` | A managed Azure container/web runtime must be selected before Azure DEV | G8 | **New hosting cost likely** | Decision open |
| Container image registry | None required locally | May be needed depending selected Azure deployment route | G8 | Possible registry/storage cost | Decision open; do not assume ACR until runtime is chosen |
| Product API | FastAPI + Uvicorn | Externally reachable machine-to-machine API | G8 | Included in runtime; network/ingress may add cost | Implemented locally |
| Canonical source binaries | Local file supplied to source registry; binaries excluded from Git. Local `sources/private/` is the G0 Local substitute and is explicitly not production | Controlled immutable source store. Target architecture names **Azure Blob Storage** when G0 Azure DEV PASSes. Console ingest (Protocol v2.6) requires this store | G2/G8 / console ingest | **New durable storage cost** | Required before real source operation in Azure; G0 Azure DEV remains BLOCKED |
| Internal operations console UI | Not implemented. Protocol v2.6 authorizes an intuitive console for researchers and reviewers (ingest, review, publish, later analytics). Not a care-app frontend, chatbot, EPD/ECD UI or public website. Chat is not a room | Hosted internal UI in this repository or a tightly bound same-product package; vendor **TBD**. Vercel is not required | Protocol v2.6 / after bron 2 storage is capturable | **New internal UI cost if/when built**; no vendor selected | Authorized not built; do not implement in this protocol change |
| Console identity (accounts/roles) | Not implemented. Required console capability when the console is built: researcher, reviewer, publisher; no shared login for review/publish | Internal identity, not public signup. Provider **TBD** and subject to G0. Does not close G8 or provision Azure AD | Protocol v2.6 C5 / G0 / G8 | **New identity/access cost if/when selected**; no vendor selected | Decision open; G0 Azure DEV remains BLOCKED |
| Canonical/publication database | SQLite reference runtime; PostgreSQL schema exists in `db/schema_v2.sql` | Production database adapter and durable relational store; current reference target is PostgreSQL | G8 | **New managed database cost** | Adapter/integration not implemented |
| Usage ledger | Local SQLite | Shared durable usage/audit backend for multi-replica production | G8 | Could share production DB or use separate observability/data service | Decision open |
| Tenant registry | Local JSON containing only API-key hashes; real tenant config excluded from Git | Production tenant/config store and controlled secret provisioning | G8 | Secret/config service may add cost | Decision open |
| Secrets and workload identity | Environment/managed-identity boundary described in provider contract; no production implementation | Select V&VN-approved secret management and workload identity; no plaintext repository secrets | G8 | Possible secret-management cost | Decision open |
| Rate limiting | In-process sliding window | `product_security_v1.py` explicitly requires APIM/Redis or distributed equivalent for distributed deployment | G8 / external traffic | **Potentially material new service cost** | Decision open |
| API gateway | Not required for local pilot | Azure API Management is named as one possible production rate-limit boundary, but is not yet a committed dependency | G8 / external traffic | Potentially material cost | Architecture decision open |
| Retrieval embeddings | Deterministic local char-TFIDF; no remote credentials | Hosted embedding provider is optional future C4 work, not required for current Product API | G6+ / future C4 | Usage-based model/API cost if adopted | **Not required now** |
| LLM / Answer-RAG | None in Product API | Separate optional future layer governed by G7/C6 | G7 only | Usage-based model cost if later approved | **Not required now** |
| Monitoring/alerting | No production monitoring implementation | Monitoring, incident visibility and operational alerting are mandatory for G8 | G8 | May add Azure monitoring/log-retention cost | Decision open |
| Backup/recovery | Local files/SQLite only | Managed backup/restore and tested recovery for durable stores | G8 | Storage/retention cost | Decision open |
| Domain/TLS | Local API endpoints | Azure-managed endpoint may suffice for pilot; custom domain/DNS/certificate only if governance/product requires it | G8 if externally exposed | Conditional | Not yet required |
| Infrastructure as code | No Bicep/Terraform/`azd` deployment baseline found | Deployment resources/configuration should become reproducible before production | G8 | Engineering/setup effort; service costs captured above | Not implemented |

## 3. Most likely budget surprises if left implicit

### 3.1 Production hosting is not yet selected

The Dockerfiles prove the service is container-ready, but they do not select or provision an Azure runtime. A future Azure DEV step will therefore require an explicit hosting decision and account/subscription access. This should be budgeted before deployment work starts.

### 3.2 Two different kinds of durable storage are already implied

They solve different problems:

1. **Object/file storage** for the exact canonical PDF/HTML/binary source bytes. The target architecture already names Azure Blob Storage.
2. **Relational database storage** for canonical object versions, releases, publication registry and audit state. Local SQLite is explicitly a pilot/reference implementation; PostgreSQL is the production reference schema.

One does not replace the other.

### 3.3 The current API security/runtime components are deliberately single-process

The current rate limiter and usage ledger work locally, but not as a reliable shared state layer across multiple replicas. External/multi-replica use therefore creates an additional infrastructure choice: API Management, Redis/distributed rate limiting, a shared database implementation, or an approved equivalent.

### 3.4 Hosted embeddings are a choice, not a hidden prerequisite

The current retrieval stack works with a deterministic local char-TFIDF provider. A remote embedding provider must not be introduced merely because it is common in RAG architectures. If later evidence justifies it, it is a C4 change with its own provider, privacy, region, cost and acceptance decision.

### 3.5 A chatbot/LLM is not part of the current service

The Product API returns published V&VN evidence to consumers and explicitly performs no generation. A future Answer/RAG layer is separate. This prevents model/API expenditure from being treated as an unavoidable setup cost for the current Data Services pilot.

### 3.6 An internal operations console is authorized, not built

Protocol v2.6 authorizes an internal operations console (ingest, review, publish, later analytics) as a human surface over the knowledge kernel. The console is not implemented. Identity (researcher / reviewer / publisher) is a required console capability; no vendor is selected; Azure AD is not provisioned; G8 is not closed. Vercel, Neon and a hosted LLM are not required. Console work starts only after bron 2 storage is at least capturable and does not replace Fase 2.

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
- `Dockerfile` and `Dockerfile.product-api` — Python/container runtime;
- `pyproject.toml` and lockfiles — pinned Python stack;
- `src/canonical_store.py` and `db/schema_v2.sql` — SQLite pilot versus PostgreSQL production reference;
- `src/product_api_v1.py` and `src/usage_ledger_v1.py` — local file/SQLite runtime state;
- `src/product_security_v1.py` — in-process rate limiting and APIM/Redis replacement boundary;
- `src/embedding_provider_v1.py` and `config/embedding_provider_local_v1.json` — local deterministic embedding provider and managed-identity/env secret boundary;
- `CONTRIBUTING.md` and `docs/REPOSITORY_CONVENTIONS.md` — controlled source binaries outside Git and Azure Blob target;
- `docs/history/PRODUCT_API_V1_REPORT.md` and `docs/history/FULL_TECHNICAL_AUDIT_2026-08-19.md` — Azure/multi-replica and production adapter gaps.

## 6. Maintenance rule

This baseline should be updated in the same pull request whenever code or protocol introduces, removes or materially changes an external service, paid plan, durable data store, hosted model/provider, runtime platform, account-level permission requirement or operational dependency.
