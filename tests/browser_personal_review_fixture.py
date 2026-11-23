"""#860 actual PostgreSQL/ASGI fixture; evidence endpoints exist only in tests."""
import asyncio

from fastapi import Request

from tests.browser_postgres_support import browser_application
from tests.personal_review_fixture_support import PASSWORD, bind, prepare, snapshot

app = browser_application('personal-review', processing_binder=bind)
state = app.state.operations_kernel
accounts, docs = prepare(state, mixed_copies=2)
review_gate = asyncio.Event()
review_gate.set()


@app.middleware('http')
async def pause_review_post(request: Request, call_next):
    if request.method == 'POST' and request.url.path == '/review':
        await asyncio.wait_for(review_gate.wait(), timeout=15)
    return await call_next(request)


@app.post('/browser-review-gate')
async def set_review_gate(paused: bool):
    if paused:
        review_gate.clear()
    else:
        review_gate.set()


@app.get('/browser-manifest')
def manifest():
    return {'documents': docs, 'username': accounts['a']['username'],
            'other': accounts['b']['username'], 'empty': accounts['outsider']['username'], 'password': PASSWORD}


@app.get('/browser-personal-state')
def current_state():
    return snapshot(state, docs)
