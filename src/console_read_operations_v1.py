"""Operation-owned inputs for compact document overviews and console pages.

Workflow/canonical PostgreSQL remain authoritative. No retained payload crosses a
request boundary. Full detail operations continue using the existing domain
readers; summaries never load a full envelope or a full object.
"""
from contextlib import contextmanager
from functools import wraps
from dataclasses import dataclass, field
from typing import Any

from src.operations_console_v1 import ConsoleError
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.workflow_transaction_v1 import workflow_read_transaction


@dataclass
class DocumentOverviewInputs:
    documents: list[dict[str, Any]]
    state: Any
    diagnostics: dict = field(default_factory=dict)
    published: set = field(default_factory=set)
    processing: dict = field(default_factory=dict)
    metadata_partial: bool = False

    def select(self, snapshot_ids):
        missing = [sid for sid in snapshot_ids if sid not in self.diagnostics]
        for start in range(0, len(missing), 50):
            batch = missing[start:start + 50]
            processing = self.state.workflow_document_store.document_processing_inputs(batch)
            diagnostics = self.state.workflow_document_store.document_diagnostic_inputs(batch)
            published = self.state.published_snapshot_ids(batch)
            self.processing.update(processing)
            self.diagnostics.update(diagnostics)
            self.published.update(published)

    def status_and_diagnostics(self, envelope):
        from src.processing_retry_v1 import status
        from src.processing_diagnostics_v1 import processing_diagnostics
        sid = envelope['snapshot_id']
        # Capture is explicit and complete before leaving the SQL boundary.
        inputs = self.diagnostics[sid]
        processing = self.processing[sid]
        result = status(processing, policy=self.state._processing_limits())
        if (sid in self.published or inputs['objects'] or inputs['has_bindings']
                or processing.get('has_review_passes')):
            result['retry_allowed'] = False
        return result, processing_diagnostics(inputs['objects'])


@contextmanager
def document_overview_operation(state, account, *, scan_limit=None):
    # Current domain identity/role validation is outside the pure SQL transaction:
    # current=True uses FOR SHARE and is deliberately not a read-only SQL query.
    actor = state._account(account['account_id'], current=True)
    if actor.get('retirement'):
        raise ConsoleError('not_authenticated')
    try:
        with workflow_read_transaction(state.workflow_document_store):
            documents = state.workflow_document_store.list_document_summaries(
                limit=scan_limit + 1 if scan_limit is not None else None)
    except WorkflowDocumentStoreError as exc:
        raise ConsoleError('workflow_document_unavailable') from exc
    # Never yield control to a consumer while holding a SQL transaction open.
    partial = scan_limit is not None and len(documents) > scan_limit
    yield actor, DocumentOverviewInputs(documents[:scan_limit] if scan_limit is not None else documents,
                                       state, metadata_partial=partial)


def install_console_read_operations(app, console):
    """Every GET owns its detail snapshot, including routes installed later.

    Wrap synchronous endpoint execution so ContextVars are created and destroyed
    in the route's worker thread (or async task). Mixed GETs (e.g. quality-report recording) get
    input ownership but never a blanket read-only SQL transaction. Pure compact
    operations explicitly own that transaction above.
    """
    import inspect
    from fastapi.routing import APIRoute

    def wrap(route):
        if not isinstance(route, APIRoute) or 'GET' not in route.methods:
            return
        original = route.dependant.call
        if getattr(original, '_metis_read_operation', False):
            return
        if inspect.iscoroutinefunction(original):
            @wraps(original)
            async def read(*args, **kwargs):
                with console.document_read_operation():
                    return await original(*args, **kwargs)
        else:
            @wraps(original)
            def read(*args, **kwargs):
                with console.document_read_operation():
                    return original(*args, **kwargs)
        read._metis_read_operation = True
        route.dependant.call = read

    base_route = app.router.route_class
    class ConsoleReadRoute(base_route):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            wrap(self)

    for route in app.routes:
        wrap(route)
    app.router.route_class = ConsoleReadRoute
