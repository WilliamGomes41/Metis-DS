"""Empty production composition for the upload-to-human-build browser proof."""
from tests.browser_postgres_support import browser_application

app = browser_application('human-build')
console = app.state.operations_kernel
console.create_account(username='human.chain', password='human-chain-secret', roles=('researcher', 'reviewer'))


@app.get('/browser-manifest')
def manifest():
    return {'username': 'human.chain', 'password': 'human-chain-secret'}
