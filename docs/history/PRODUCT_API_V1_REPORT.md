# V&VN Data Services - Product API v1 technical report

## Result

Product API v1 is implemented as a separate machine-to-machine contract above
the published retrieval layer. It does not generate answers and cannot bypass
the publication gate.

## External contract

- `GET /v1/health` - public service health
- `POST /v1/retrieve` - published V&VN retrieval (`retrieve` scope)
- `GET /v1/knowledge/{object_id}` - a published knowledge projection (`knowledge:read`)
- `GET /v1/documents` - entitled published documents (`documents:read`)
- `GET /v1/documents/{document_id}` - document metadata (`documents:read`)
- `GET /v1/updates` - entitled publication releases (`updates:read`)
- `GET /v1/usage` - tenant usage summary (`usage:read`)

## Tenant boundary

Pilot authentication uses an API key supplied as an HTTP Bearer token. Only
SHA-256 key hashes are stored. Each tenant has explicit scopes, allowed document
IDs/topics, a requests-per-minute limit and a maximum `top_k`.

Entitlements are applied before the retrieval index is constructed. An object
outside the tenant entitlement is therefore not scored and the object endpoint
returns 404 rather than revealing its existence.

## Usage/audit

The pilot usage ledger is SQLite. It stores request ID, tenant, endpoint,
behavior, result count, latency, result object IDs and SHA-256 of normalized
query text. Raw query text is not stored.

For Azure/multi-replica production the local rate limiter and usage ledger are
replaceable infrastructure components; the `/v1` contract does not need to
change.

## Safety

REAL mode consumes only the current derived published retrieval file. The
current real corpus contains zero published records, so `/v1/retrieve` returns
`abstain / empty_published_corpus`. Fixture mode is disabled unless explicitly
enabled and every fixture response is marked synthetic.

There is no LLM or answer generation in Product API v1.

## Verification

- Full repository regression suite: 89 passed
- Aggregate test coverage: 84%
- Product API tests: 18 passed
- Actual HTTP fixture smoke: retrieve succeeds and exposes source/version/object IDs
- Actual HTTP real smoke: abstains on empty published corpus
- OpenAPI security scheme: `VVNApiKeyBearer`
- Product container entrypoint: `Dockerfile.product-api`

## Next technical boundary

Product API v1 is sufficient to demonstrate the original Data Services product
shape: an external chatbot can call `/v1/retrieve`, receive published V&VN
knowledge plus source/version metadata, and use its own LLM.

The next technical workstream should test an independent retrieval holdout set
and then plug in a hosted embedding provider behind the existing provider
interface. Azure deployment can follow without changing the public `/v1`
contract.
## v1.1 safety update (Protocol v2.1)

The public route remains `/v1/retrieve`, but the service implementation is now `product-api-v1.1.0`. Hybrid retrieval only produces candidates. A deterministic Answerability/Evidence Gate must pass before results are exposed as supported knowledge. The response adds `answerability` and `false_positive_class`; unsupported relations or constraints return `status=abstain`. No LLM/generation was added.
