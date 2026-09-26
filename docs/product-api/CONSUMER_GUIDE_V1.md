# Metis Product API v1 — consumer guide

This is the integration contract for external products consuming published Metis knowledge.

## What a consumer needs

A consumer needs only:

1. the deployment base URL;
2. one active Metis API credential for its ConsumerApplication;
3. the published OpenAPI contract at `schemas/product_api_v1.openapi.json`.

No consumer-specific Metis endpoint, schema, deploy, or source-code change is part of the integration contract.

## Authentication

Send the issued credential as an HTTP Bearer token:

```http
Authorization: Bearer <metis credential>
```

The plaintext credential is shown only when issued. Metis stores only its SHA-256 digest.

A credential identifies one ConsumerApplication. Access is determined separately by the tenant entitlement, application grant, application/tenant lifecycle state, and endpoint capability.

## Stable major contract

The stable API boundary is `/v1`.

API contract version, knowledge-object version, source version, and publication/release version are different concepts. A new knowledge or publication release does not create `/v2`.

Within `/v1`, incompatible endpoint/request/response/security changes are blocked by contract checks. Additive optional response fields may be introduced after deliberate contract regeneration and review.

## Capabilities and endpoints

| Capability | Endpoint | Scope |
| --- | --- | --- |
| Retrieve relevant published knowledge | `POST /v1/retrieve` | `retrieve` |
| Resolve one knowledge object | `GET /v1/knowledge/{object_id}` | `knowledge:read` |
| Discover entitled documents | `GET /v1/documents` | `documents:read` |
| Resolve document metadata | `GET /v1/documents/{document_id}` | `documents:read` |
| Poll entitled publication changes | `GET /v1/updates` | `updates:read` |
| Read tenant usage summary | `GET /v1/usage` | `usage:read` |
| Service health | `GET /v1/health` | public |

Content is filtered to effective access before retrieval. A consumer cannot influence ranking with knowledge it is not entitled to see.

## Minimal retrieve request

```http
POST /v1/retrieve
Authorization: Bearer <credential>
Content-Type: application/json
X-Request-ID: consumer-request-123

{
  "query": "Wanneer gebruik je de risicofactorenscore?",
  "top_k": 5
}
```

`X-Request-ID` is optional. If supplied, Metis returns the same value in the response header and response body. If omitted, Metis generates one. Persist it in consumer-side diagnostics so a failed integration request can be correlated.

A successful retrieval can either return supported knowledge or abstain. HTTP 200 therefore does not mean that Metis found sufficient evidence.

Supported shape:

```json
{
  "api_version": "v1",
  "status": "retrieve",
  "answerability": "supported",
  "results": [
    {
      "knowledge_object_id": "...",
      "object_version": "...",
      "document_id": "...",
      "content": "...",
      "source": {
        "title": "...",
        "url": "...",
        "page": 15,
        "version": "..."
      },
      "release": {
        "release_id": "...",
        "release_version": "...",
        "published_at": "..."
      }
    }
  ],
  "request_id": "consumer-request-123"
}
```

Consumers should retain returned identifiers and provenance rather than copying knowledge into an untraceable local blob.

## Abstention

Metis does not generate an answer from latent model knowledge when published evidence is insufficient.

An abstaining retrieval still uses HTTP 200 and contains:

```json
{
  "api_version": "v1",
  "status": "abstain",
  "answerability": "insufficient_evidence",
  "reason": "...",
  "results": [],
  "result_count": 0
}
```

Consumers must treat this as a knowledge outcome, not as an infrastructure error.

## Error semantics

Product API domain/security failures use an HTTP status plus a stable `detail.code`.

Common cases:

| HTTP | Example code | Meaning |
| ---: | --- | --- |
| 400 | `top_k_exceeds_tenant_limit` | Request exceeds the application/tenant limit |
| 401 | `missing_api_key`, `invalid_api_key` | Credential absent, invalid, revoked, or parent access inactive |
| 403 | `scope_denied`, `document_not_entitled` | Authenticated but capability/resource not granted |
| 404 | `knowledge_object_not_found`, `document_not_found` | Resource absent or intentionally undisclosed outside access |
| 429 | `rate_limit_exceeded` | Current application rate limit exceeded; honor `Retry-After` |
| 503 | `access_store_unavailable` | Authorization authority unavailable; Metis fails closed |

Pydantic request-validation failures remain HTTP 422 and are represented in OpenAPI.

## Usage

`GET /v1/usage` is the minimum consumer-visible operational summary. It reports tenant-level request totals, retrieves, abstentions, returned-result count, and counts by endpoint.

Usage is telemetry. It is not an authorization, publication, or serving authority.

## Publication changes

`GET /v1/updates` exposes publication releases currently visible within effective access. Live retrieve/read operations always use the current serving authority; consumers do not need a Metis reintegration when a new entitled release is published.

A future offline mirror/synchronization product may require stronger cursor/tombstone semantics. Those semantics are not implied by the current endpoint.

## Credential rotation

An application may temporarily have multiple active credentials. A normal rotation is:

1. issue credential B;
2. deploy B to the consumer;
3. verify B;
4. revoke credential A.

Revocation takes effect on the next Product API request in PostgreSQL access mode.

## Contract source

The checked-in OpenAPI contract is generated from the running FastAPI application:

```text
schemas/product_api_v1.openapi.json
```

Generation/check command:

```bash
python scripts/product_api_contract.py --check --base-ref origin/main
```

To deliberately regenerate after a compatible contract change:

```bash
python scripts/product_api_contract.py --write
```

The regenerated diff is part of code review. Consumer-specific contract variants are not supported.
