"""Standalone browser fixture over real PostgreSQL; never a product route."""
from tests.browser_postgres_support import browser_application
from tests.test_human_annotation_postgres import source

app = browser_application('human-annotation')
console = app.state.operations_kernel
_, actor, _, sid, view, _ = source(lambda **kwargs:console, console.root)


@app.get('/browser-manifest')
def manifest():
    return {'document':sid,'username':'annotator','password':'annotation-secret'}
