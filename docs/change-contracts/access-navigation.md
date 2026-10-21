# Access and navigation — #546

Change class: B
Rewrite risk: none
Promise: Authentication reaches home without document/review calculations; shared navigation does not request review badges. Anonymous visitors do not receive session-expiry warnings, and an identity outage denies access with HTTP 503 while preserving the session cookie.
Proof: Route fault injection, rendered JavaScript execution, existing navigation/authorization regressions, and PostgreSQL callback-to-home integration.
Touches lifecycle invariants: no

## Existing path and bounded change

`home -> _counts -> waiting_task_counts -> review_work_item` and
`home -> list_envelopes` blocked the authenticated landing page before HTML was
returned. Other HTML routes also invoked `_counts` only to render navigation.
The home now renders four neutral destinations after the existing session check.
Navigation no longer accepts counts. This includes the route installers in
`review_workboard_v1`, `publish_readiness_ui_v1`, `audit_room_v1`,
`closed_review_loop_v1`, `deterministic_review_repair_v1` and `review_closure_v1`. Review/publication task pages retain their
own authoritative calculations. No deferred calculation, cache or second source
of task truth is introduced.

The session dialog is rendered by authenticated navigation rather than the
unconditional page shell. Without the dialog the browser starts no session poll
or countdown. Authenticated pages retain renewal and expiry behavior; both a 401
and countdown to zero now show the expired title and sign-in action.

`_current` propagates `workflow_identity_unavailable` to a 503 response. The same
response is used for unavailable Entra navigation renewal and other existing 503
failure paths, preserving cookies. Authentication rejection keeps its existing
401/403 or redirect behavior. Session duration, role checks and identity storage
remain owned by the existing identity implementation.

## State and proof boundary

No durable state, source, object, review decision, release or schema is changed.
No startup, deployment or extractor setting changes. Rollback is a code revert;
there is no data rollback. Upload/object-formation separation is a later change.

Before the patch, synthetic HTTP tests failed at the actual home/navigation
boundary when review counts or the home inventory read were unavailable. Browser
script tests reproduced the anonymous-home warning and incorrect expiry title.
After the patch these checks pass. The regression also constructs the app
through `console_asgi.build_app`, exercising the installed production route
composition, and the existing hot-path checks verify that navigation badge SQL
reads disappear while document projections remain intact. A native PostgreSQL integration test follows
the Microsoft callback to home with both heavy reads forbidden; only the external
Microsoft exchange is replaced in that test.

The local environment has no configured PostgreSQL test database, so those
integration tests require CI. Local synthetic proof does not establish Azure
availability or explain every gateway failure. Production acceptance still
requires the running artifact and login -> home -> task navigation to be checked,
including during document processing. Detailed review-page latency remains a
separate measurement.
