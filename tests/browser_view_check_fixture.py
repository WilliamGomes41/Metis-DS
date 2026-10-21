"""Real PG production app, synthetic source/model and private evidence transport."""
import os

from fastapi.responses import JSONResponse

from tests.browser_postgres_support import browser_application
from tests.test_availability_repair import accounts, bind, provider
from tests.test_azure_source_processing import ImmutableBlobFixture
from tests.test_view_check_postgres import configure

app = browser_application('view-check-browser', processing_binder=lambda state: None,
                          immutable_source_store=ImmutableBlobFixture())
console = app.state.operations_kernel
author, reviewer = accounts(console)
bind(console, provider)
configure(app, console, None, console.runtime / 'private-test-evidence',
          origin=os.environ['METIS_BROWSER_BASE'], module=os.environ['METIS_PLAYWRIGHT_MODULE'],
          browser=os.environ['METIS_BROWSER_EXECUTABLE'])


@app.get('/browser-manifest')
def manifest():
    return JSONResponse({'reviewer': reviewer})
