"""Synthetic installed-route browser server, never loaded in production."""
import os
import tempfile
from pathlib import Path
from fastapi.responses import JSONResponse
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from tests.test_review_batch_atomic_postgres import _console
from tests.test_availability_repair import accounts, bind, provider, installed_app
from tests.test_azure_source_processing import ImmutableBlobFixture

config = PostgresCanonicalConfig(dsn=os.environ["METIS_TEST_POSTGRES_DSN"])
console = _console(Path(tempfile.mkdtemp(prefix="metis-source-browser-")), config)
console.immutable_source_store = ImmutableBlobFixture()
author, reviewer = accounts(console)
bind(console, provider)
app = installed_app(console)

@app.get("/browser-manifest")
def manifest():
    return JSONResponse({"reviewer": reviewer})
