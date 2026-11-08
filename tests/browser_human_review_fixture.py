"""Actual PG/ASGI correction fixture; no test endpoints in product code."""
from tests.browser_postgres_support import browser_application
from tests.test_human_annotation_build_postgres import saved_source
from tests.test_human_annotation_review_postgres import execute_build, candidate, approve

app = browser_application('human-review')
console = app.state.operations_kernel
_, actor, sid, original = saved_source(lambda **kwargs: console, console.root, context_function='supported_by')
execute_build(console, actor, sid)
reviewer = console._envelope(sid)['named_reviewers'][0]
oid = candidate(console, sid)['object_id']
approve(console, sid, oid, reviewer)
version = candidate(console, sid)['object_version']


@app.get('/browser-manifest')
def manifest():
    return {'document': sid, 'annotation': original['annotation_id'], 'object': oid,
            'version': version, 'username': 'reviewer', 'password': 'human-build-secret'}
