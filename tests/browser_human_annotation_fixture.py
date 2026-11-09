"""Standalone browser fixture over real PostgreSQL; never a product route."""
from tests.browser_postgres_support import browser_application

app = browser_application('human-annotation')
console = app.state.operations_kernel
console.create_account(username='annotator', password='annotation-secret', roles=('researcher','reviewer'))


@app.get('/browser-manifest')
def manifest():
    return {'username':'annotator','password':'annotation-secret'}
