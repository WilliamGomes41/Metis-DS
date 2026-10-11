# Example Vulnerability Report

Use this format and level of detail.

## Finding: Untrusted content can reach canonical knowledge object without human-review gate
- **Location**: `src/api/knowledge.py:142` (POST /v1/objects) and `src/domain/objects.py:87` (create_object)
- **Type**: integrity / missing review gate
- **Reachability**: Yes — request body field `content` is written directly to the object store when `source=agent` and no review status is checked.
- **Impact**: An agent or external caller can insert content that later surfaces as authoritative in Athena responses or Metis queries. Violates “canonical objects stay human-reviewed”.
- **Confidence**: High (static path confirmed; dynamic confirmation recommended in sandbox).
- **Suggested fix**:
  1. Add mandatory `review_status` check before persistence.
  2. Reject or quarantine objects where `source != human` until an explicit review transition occurs.
  3. Emit an audit event on any transition to canonical.
- **Verification**:
  - Unit test that POST with `source=agent` returns 403 or creates non-canonical object.
  - Trace in sandbox that the object never appears in the truth-path query until reviewed.
- **Domain note**: This is a stateful change. Owning context is Knowledge Objects. Hard invariant: only human-reviewed objects are canonical. Lifecycle transition `DRAFT → REVIEWED` must be explicit and authorized.

## Finding: Potential IDOR on tenant-scoped query
- **Location**: `src/api/query.py:67`
- **Type**: authZ
- **Reachability**: Likely — `tenant_id` taken from query param instead of authenticated context.
- **Impact**: Caller with valid token for tenant A can request objects from tenant B.
- **Confidence**: Medium (needs confirmation that auth middleware does not override).
- **Suggested fix**: Always derive tenant from the authenticated principal; ignore client-supplied tenant_id for authorization decisions.
- **Verification**: Sandbox test with two tenants and a token for one of them.
