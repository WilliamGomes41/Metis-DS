"""Synthetic cloud boundary over the actual PG production browser application."""
from threading import Event

from fastapi.responses import JSONResponse
from tests.browser_postgres_support import browser_application
from tests.test_availability_repair import accounts
from tests.decision_graph_native_support import receive_tree
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_azure_source_processing import ImmutableBlobFixture

app = browser_application('source-browser', processing_binder=bind_fixture_selections,
                          immutable_source_store=ImmutableBlobFixture())
console = app.state.operations_kernel
author, reviewer = accounts(console)
tree = receive_tree(console, author, reviewer, 'Beslisboom voor voortgang')
release = Event()
prepare = console._fragments_and_spec


def held_preparation(*args, **kwargs):
    if not release.wait(timeout=45):
        raise TimeoutError('Browser did not release tree preparation')
    return prepare(*args, **kwargs)


console._fragments_and_spec = held_preparation


@app.post('/browser-release-tree')
def release_tree():
    release.set()


@app.get('/browser-manifest')
def manifest():
    return JSONResponse({'reviewer': reviewer, 'tree': tree})
