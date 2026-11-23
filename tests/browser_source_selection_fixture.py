"""Synthetic cloud boundary over the actual PG production browser application."""
from threading import Event

from fastapi.responses import JSONResponse
from tests.browser_postgres_support import browser_application
from tests.test_availability_repair import accounts, bind, provider
from tests.test_azure_source_processing import ImmutableBlobFixture

app = browser_application('source-browser', processing_binder=lambda console: None,
                          immutable_source_store=ImmutableBlobFixture())
console = app.state.operations_kernel
author, reviewer = accounts(console)
provider_release = Event()


def held_provider(*args):
    if not provider_release.wait(timeout=25):
        raise TimeoutError('Browser proof did not release the provider')
    return provider(*args)


bind(console, held_provider)


@app.post('/browser-release-provider')
def release_provider():
    provider_release.set()


@app.get('/browser-manifest')
def manifest():
    return JSONResponse({'reviewer': reviewer})
