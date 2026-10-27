"""Actual PostgreSQL/ASGI composition for the unified content workplace."""
from tests.browser_postgres_support import browser_application
from tests.content_review_fixture_support import PASSWORD, bind, prepare, snapshot

app = browser_application('content-review', processing_binder=bind)
state = app.state.operations_kernel
accounts, docs = prepare(state, copies=2)


@app.get('/browser-manifest')
def manifest():
    return {'documents': docs, 'username': accounts['a']['username'],
            'other': accounts['b']['username'], 'password': PASSWORD}


@app.get('/browser-content-state')
def current_state():
    return snapshot(state, docs)
