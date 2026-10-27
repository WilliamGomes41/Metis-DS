"""Controlled findings and real PostgreSQL for C's two existing commands."""
from copy import deepcopy

from tests.browser_postgres_support import browser_application
from tests.source_recovery_workplace_support import blocked_source
from tests.test_availability_repair import accounts
from tests.production_support import restart_production

app = browser_application('source-recovery', processing_binder=lambda console: None)
state = app.state.operations_kernel
author, reviewer = accounts(state)
documents = [dict(pages=blocked_source(state, author, reviewer, f'pages-{i}', pages=True),
                  recovery=blocked_source(state, author, reviewer, f'grant-{i}')) for i in range(2)]
initial = {sid: deepcopy(state._envelope(sid)) for d in documents for sid in d.values()}


@app.get('/browser-manifest')
def manifest():
    return dict(documents=documents, username='author', password='fixture-only')


@app.get('/browser-recovery-state')
def recovery_state():
    restarted = restart_production(state)
    result = {}
    for sid, before in initial.items():
        envelope = restarted._envelope(sid)
        result[sid] = dict(accountings=len(envelope.get('source_page_accountings', [])),
            grant=bool(envelope.get('processing_recovery')),
            consumed=(envelope.get('processing_recovery') or {}).get('consumed_by'),
            attempts_unchanged=envelope['processing_attempts'] == before['processing_attempts'],
            source_unchanged=(envelope['sha256'], envelope['version']) == (before['sha256'], before['version']),
            objects=restarted.snapshot_objects(sid), bindings=restarted.object_review_bindings(sid))
    return result
