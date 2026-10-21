"""Synthetic cloud boundary over the actual PG production browser application."""
from fastapi.responses import JSONResponse
from tests.browser_postgres_support import browser_application
from tests.test_availability_repair import accounts, bind, provider
from tests.test_azure_source_processing import ImmutableBlobFixture

app = browser_application('source-browser', processing_binder=lambda console: None,
                          immutable_source_store=ImmutableBlobFixture())
console = app.state.operations_kernel
author, reviewer = accounts(console)
bind(console, provider)


@app.get('/browser-manifest')
def manifest():
    return JSONResponse({'reviewer': reviewer})
