# #974 P4a evidence: exception handlers no longer block the event loop

Trunk is `969936e` (main `48039ce` plus only the failing test). Head is the fix commit on top.
Both ran on 2026-11-05 with Python 3.13, Starlette 0.50.0, FastAPI 0.128.2, uvicorn 0.48.0
and a disposable PostgreSQL 16 from `tests/conftest.py`.

## Mechanism

Starlette 0.50.0, `starlette/_exception_handler.py`, `wrap_app_handling_exceptions`:

```python
if is_async_callable(handler):
    response = await handler(conn, exc)
else:
    response = await run_in_threadpool(handler, conn, exc)
```

Handlers registered with `app.add_exception_handler` or `@app.exception_handler` both go through
this code. An `async def` handler runs on the event loop, so synchronous work inside it blocks the
single production worker.

- `structured_repair_handler` is now a plain `def`, so it runs in the threadpool.
- `console_errors` stays async for `await request.form()`. It reads only the submitted
  `snapshot_revision` on the loop. The session lookup and page/nav rendering run in
  `run_in_threadpool`.
- `view_check.access_denied` only builds a `JSONResponse`, so it is unchanged.

## Proof

`tests/test_974_exception_handler_event_loop.py` serves the production app (`production_app`)
with a real uvicorn server on one event loop. The test slows the handler's synchronous work by
2 s with `time.sleep`. While that request is in flight, it times a concurrent `GET /login`.

| Slowed work | Trunk probe | Head probe |
|---|---|---|
| `render_repair` behind `POST /review` revise | 2.148 / 2.152 / 2.148 s | 0.032 / 0.022 / 0.026 s |
| `_nav` in the `ConsoleError` page (`GET /review`, unauthenticated) | 2.012 / 2.011 / 2.011 s | 0.027 / 0.018 / 0.019 s |

These are three runs per side. The probe printed its timing through a temporary `print`, which was not committed.

Trunk (red):

```
E       AssertionError: GET /login waited 2.14s behind the repair render
E       assert 2.141616823999982 < 0.75
E       AssertionError: GET /login waited 2.01s behind the error page
E       assert 2.0096620580000035 < 0.75
2 failed, 1 passed, 1 warning in 10.52s
```

Head (green):

```
3 passed, 1 warning in 10.72s
```

The third test passes on both sides. It pins the behaviour of a `ConsoleError('correction_role_required')`
raised inside the repair handler. That error still renders through the ConsoleError page with status 403
and the same copy, `data-error-code` and `data-request-id`. The request's `request_finished` diagnostic
carries the same request id and `{"type": "ConsoleError", "code": "correction_role_required", "handled": true}`.

## Regression

```
python -m pytest -q -rs -p no:logging tests/test_974_exception_handler_event_loop.py \
  tests/test_deterministic_review_repair_v1.py tests/test_review_disposition_precheck.py \
  tests/test_review_save_chain.py tests/test_closed_review_loop_http_negative.py \
  tests/test_stale_write_ux.py tests/test_care_companion.py tests/test_review_direct_workspace_v1.py \
  tests/test_source_discrepancy_v1.py tests/test_telemetry_v1.py tests/test_request_diagnostics.py \
  tests/test_b6_handled_source_rows.py tests/test_b6_source_group_command.py \
  tests/test_b6_v3_source_group_exclusions.py tests/test_source_batch_bounded_commands.py
175 passed, 2 warnings in 157.23s (0:02:37)
```

There were no skips. `tests/test_source_batch_bounded_commands.py` (line 98, `== 409` on
`/review/source-exclusions`) covers the moved `snapshot_revision` form read. The `tests/test_b6_*`
files cover the other source-group routes.

`scripts/check_architecture_boundaries.py` returned PASS. `scripts/repository_preflight.py` returned PASS.
`scripts/release_control_preflight.py --base origin/main` returned `errors: []`.

## Out of scope

`render_repair` still takes as long as before. It now holds one threadpool thread instead of the
whole event loop. P4b covers making the render itself fast.
