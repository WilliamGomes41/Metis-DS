# V&VN Data Services Protocol v2.3 — Setup, Stack and Cost Transparency

**Status:** Approved for project use
**Protocol delta version:** 2.3.0
**Approval date:** 2026-08-25
**Approved by:** Project owner
**Extends:** Protocol v2.2.0
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.3 closes an infrastructure-readiness gap exposed during implementation: a system can be technically sound in local development while external services, paid plans, durable storage, runtime platforms or account-level permissions become visible only when deployment is attempted.

This delta requires those dependencies to be identified before they become implementation or budget surprises.

It does not prescribe Azure, GitHub, PostgreSQL, Blob Storage, an embedding provider or an LLM merely because those technologies are common. It requires the **capability need, selected implementation, cost exposure and operational ownership** to be explicit before the dependency is relied upon.

Protocol v2.2.0 and this approved delta jointly form the normative baseline v2.3.0. Where requirements conflict, the stricter fail-closed requirement applies.

## 2. Core setup-transparency rule

A new external service, paid plan, hosted model, durable store, managed runtime, identity service, gateway, monitoring service or account-level feature MUST NOT become an implicit runtime dependency.

Before code or deployment relies on such a dependency, the project MUST record:

- the capability that is required;
- whether the dependency is mandatory, optional or future-only;
- the environment(s) in which it is needed;
- the selected provider/product when a provider has been chosen;
- a provider-neutral description when selection remains open;
- the reason the current implementation is insufficient;
- data categories handled by the service;
- region/data-residency requirements where applicable;
- authentication, secret and workload-identity requirements;
- persistence, retention, backup and recovery expectations where applicable;
- expected cost model and a reasonable cost range or `TBD` with a decision deadline;
- free-tier or trial assumptions and what happens when those assumptions end;
- account, subscription, organization or plan prerequisites;
- named decision owner and operational owner when known;
- fallback, exit or replacement path when material vendor lock-in exists;
- gate or milestone before which the open decision MUST be resolved.

`TBD` is an acceptable transparent state. An undocumented assumption is not.

## 3. Required infrastructure manifest

The repository MUST contain a versioned infrastructure manifest or equivalent machine-readable record for every target environment that moves beyond purely local development.

At minimum, each dependency record MUST contain:

- `capability_id`;
- `capability`;
- `environment`;
- `requirement_status`: `required`, `optional`, `future`, or `not_applicable`;
- `implementation_status`: `implemented`, `selected_not_provisioned`, `decision_open`, `blocked`, or `not_needed`;
- `current_implementation`;
- `target_implementation` or `TBD`;
- `provider` or `TBD`;
- `data_classification`;
- `region` or `TBD` when relevant;
- `persistence` and retention requirement where relevant;
- `identity_secret_boundary`;
- `cost_model`;
- `expected_cost_range` or `TBD`;
- `budget_owner` or `TBD`;
- `operational_owner` or `TBD`;
- `decision_deadline_gate`;
- `evidence` linking the requirement to code, protocol or architecture.

The manifest MUST distinguish an actual requirement from a likely future option. A hosted embedding provider or LLM, for example, MUST NOT be reported as required while the accepted architecture still functions without it.

## 4. Stack baseline

A human-readable stack/setup baseline MUST accompany the infrastructure manifest and explain the architecture in operational terms.

It MUST identify at least:

1. authoritative code repository and required repository plan/features;
2. CI/build environment;
3. application runtime and deployment platform;
4. container/image registry if required by the selected runtime;
5. durable relational/database storage;
6. object/file storage for source binaries or other immutable files;
7. runtime/usage/audit persistence;
8. tenant configuration, authentication and authorization;
9. secrets and workload identity;
10. API gateway and distributed rate limiting where applicable;
11. monitoring, alerting and log retention;
12. backup and disaster recovery;
13. domain/TLS/network boundary where externally exposed;
14. hosted embeddings or model APIs, explicitly marked required/optional/future;
15. infrastructure-as-code or other reproducible provisioning mechanism;
16. account, subscription and permission prerequisites.

The baseline MUST state which components are local pilot substitutes and which must change for multi-replica, external-pilot or production use.

## 5. Cost transparency

### 5.1 Before provisioning

Before a paid or potentially paid external resource is provisioned for DEV, pilot or production, the project MUST record:

- pricing basis relevant to expected use (for example fixed monthly, compute time, requests, tokens, storage, transfer or retained logs);
- expected low/nominal/high usage assumption when reasonably estimable;
- an expected monthly cost range or a documented reason why it cannot yet be estimated;
- whether a free tier, credit or trial is being relied upon;
- the likely cost after the free tier, credit or trial ends;
- the person or function responsible for the budget;
- spending alert, budget cap or equivalent control when supported by the platform.

The estimate is a planning control, not a financial guarantee. It MUST be updated when architecture or usage assumptions materially change.

### 5.2 Hidden-cost prohibition

A pull request MUST NOT introduce a new paid-service requirement while describing the change only as an application-code feature.

If a change creates a new infrastructure or cost dependency, that dependency MUST be called out in the pull request and the stack/infrastructure records MUST be updated in the same change or explicitly blocked pending a linked decision.

## 6. Environment stages

Infrastructure readiness MUST be evaluated per environment.

### 6.1 Local development

Local development MAY use reproducible local substitutes such as SQLite, local files, deterministic local embeddings or an in-process rate limiter when their limitations are explicit.

A local substitute MUST NOT be described as production-ready merely because the API contract can remain unchanged.

### 6.2 Shared DEV / Azure DEV

Before a shared DEV environment processes real canonical source material or external pilot traffic, all infrastructure capabilities required by that topology MUST have a selected implementation, owner, data boundary and cost exposure recorded.

### 6.3 External pilot and production

External pilot and production additionally require the existing Protocol v2.2 G8 controls, including tenant isolation, secret management, monitoring, tested emergency withdrawal and backup/recovery.

## 7. Gate G0 — Infrastructure and cost readiness

G0 is evaluated **per target environment**.

### G0 PASS

PASS requires:

- a complete infrastructure manifest for the target environment;
- a current human-readable stack/setup baseline;
- every required external capability identified;
- every required dependency either implemented or selected with a documented provisioning plan;
- region/data handling and identity/secret boundaries recorded where applicable;
- cost model and expected cost range recorded, or a justified `TBD` with a deadline before provisioning;
- required accounts, subscriptions, organization plans and permissions identified;
- budget owner identified before paid resources are created;
- operational owner identified before external traffic is accepted;
- no implementation code depends on an undocumented external service;
- no optional/future component is misrepresented as an unavoidable dependency.

### G0 BLOCKED

G0 is `BLOCKED` when a required capability is known but provider/product selection, funding, account access, required plan, region, ownership or provisioning remains unresolved past its declared decision deadline.

### G0 FAIL

G0 is `FAIL` when evidence shows that implementation already relies on an undocumented external dependency, paid service, secret source or persistence layer, or when a required production capability is knowingly omitted from the manifest.

### G0 NOT_EVALUATED

Use `NOT_EVALUATED` when a target environment has not yet been scoped.

### Relationship to existing gates

G0 does not prohibit local product, evidence, review or retrieval development. It is a cross-cutting readiness gate.

- G0 for the applicable environment MUST PASS **before paid target-environment resources are provisioned**, except for a documented time-limited discovery/sandbox resource with an explicit cost ceiling.
- G0 MUST PASS before G8 Production Readiness can PASS.
- If G1–G7 rely on a target-environment external dependency, the applicable part of G0 becomes a prerequisite for that dependency-dependent work.

This environment-specific rule supersedes any interpretation of the v2.2 gate-order sentence that would make unresolved production infrastructure block unrelated local evidence or retrieval development.

## 8. Change-impact rule for stack changes

A change that only updates a previously documented non-normative cost estimate is C0 unless it changes an acceptance or security decision.

A change that introduces, removes or replaces an external runtime dependency MUST be assigned at least the change class implied by the affected function:

- repository/CI-only operational dependency: at least C1;
- source acquisition or storage dependency affecting source identity/provenance: at least C2 and, where publication eligibility is affected, C5;
- database/schema or canonical persistence change: at least C3;
- embedding/retrieval provider change: C4;
- authentication, entitlement, publication, secrets or externally exposed gateway change: C5;
- generation/model provider change: C6.

The pull request MUST state both the behavioral change class and the infrastructure impact.

## 9. Pull-request disclosure

Every pull request SHOULD contain an `Infrastructure / cost impact` section with one of:

- `None`;
- `Uses an already-declared dependency`;
- `Changes an existing dependency`;
- `Introduces a new dependency`;
- `Removes a dependency`.

When the value is not `None`, the pull request MUST link to the updated infrastructure manifest and stack baseline or record why progression is blocked.

## 10. Current V&VN Data Services mapping at approval

The following mapping was re-evaluated at approval and records the current environment-specific G0 state.

| Capability | Current state | Approved G0 interpretation |
|---|---|---|
| GitHub authoritative repository | Implemented; branch protection remains procedural under current plan | Known plan/control dependency already recorded |
| GitHub Actions CI | Implemented | No new provider required |
| Python/Docker runtime | Implemented locally; target Azure runtime not selected | Azure DEV: decision open |
| Canonical source binary storage | Local/mounted in pilot; Azure Blob Storage named as target architecture | Azure DEV: required, not provisioned |
| Canonical/publication database | SQLite executable pilot; PostgreSQL production reference schema only | Azure DEV: required production adapter/store decision open |
| Usage ledger | Local SQLite | Multi-replica target: shared durable implementation decision open |
| Rate limiting | In-process | Multi-replica/external target: APIM/Redis/distributed equivalent decision open |
| Tenant secrets/config | Local safe template; real values excluded from Git | Azure DEV: secret/config solution decision open |
| Monitoring/alerting | No production implementation | Azure DEV/external pilot: decision open |
| Backup/recovery | No managed production implementation | Azure DEV/external pilot: decision open |
| Hosted embedding provider | Not required by current accepted retrieval architecture | Future/optional; no budget dependency now |
| LLM / Answer-RAG | Not part of Product API | Future/optional; governed separately by G7/C6 |

On this approved mapping, **G0 Local Development can be treated as PASS once the manifest is present and consistent; G0 Azure DEV remains BLOCKED until the open infrastructure decisions are resolved.**

## 11. Required implementation artefacts for v2.3 adoption

At adoption, the repository MUST contain:

- `docs/STACK_SETUP_BASELINE.md`;
- a versioned machine-readable infrastructure manifest;
- a PR template field for infrastructure/cost impact;
- a lightweight CI/preflight validation that required manifest structure is present and valid;
- current environment mapping for Local Development and Azure DEV;
- an approval record binding the final v2.3 protocol checksum to the authoritative commit.

The CI validator does not need to verify vendor pricing. It MUST verify that required fields exist and that unresolved required decisions are visible rather than silently omitted.

## 12. Approval effect

Approval of v2.3 establishes infrastructure and cost transparency as a protocol requirement. It does not itself authorize expenditure, select a vendor, provision Azure resources, or convert G0 Azure DEV or G8 to PASS.

From approval, Protocol v2.2.0 and this delta jointly form the authoritative normative baseline v2.3.0. Approval does not override any gate status; unresolved Azure DEV requirements remain `BLOCKED`.
