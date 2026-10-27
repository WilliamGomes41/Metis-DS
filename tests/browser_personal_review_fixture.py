"""#860 actual PostgreSQL/ASGI fixture; evidence endpoints exist only in tests."""
from tests.browser_postgres_support import browser_application
from tests.personal_review_fixture_support import PASSWORD, bind, prepare, snapshot

app = browser_application('personal-review', processing_binder=bind)
state = app.state.operations_kernel
accounts, docs = prepare(state, mixed_copies=2)


@app.get('/browser-manifest')
def manifest():
    return {'documents': docs, 'username': accounts['a']['username'],
            'other': accounts['b']['username'], 'empty': accounts['outsider']['username'], 'password': PASSWORD}


@app.get('/browser-personal-state')
def current_state():
    return snapshot(state, docs)
