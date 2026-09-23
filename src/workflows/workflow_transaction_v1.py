"""Request-local PostgreSQL transaction boundary for workflow stores.

Workflow stores keep their existing APIs. When a shared transaction is active,
participant stores borrow one psycopg connection so their nested transactions
become savepoints inside one outer transaction. Outside that boundary every
store keeps its normal independent connection behavior.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator


_ACTIVE_CONNECTION: ContextVar[Any | None] = ContextVar(
    "metis_workflow_transaction_connection", default=None
)
_BOUND_MARKER = "_metis_workflow_transaction_bound"
_ORIGINAL_CONNECT = "_metis_workflow_original_connect"


class WorkflowTransactionError(RuntimeError):
    """Fail-closed workflow transaction configuration error."""


class _BorrowedConnection:
    """Connection facade whose context manager does not close the shared owner."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def __enter__(self) -> Any:
        return self._connection

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


def _config_identity(store: Any) -> tuple[Any, ...]:
    config = getattr(store, "config", None)
    if config is None:
        raise WorkflowTransactionError("workflow_transaction_config_missing")
    return (
        getattr(config, "dsn", None),
        getattr(config, "host", None),
        getattr(config, "database", None),
        getattr(config, "user", None),
        getattr(config, "tenant_id", None),
    )


def bind_workflow_stores(*stores: Any) -> None:
    """Bind stores to the request-local connection without changing normal use."""
    participants = [store for store in stores if store is not None]
    if not participants:
        raise WorkflowTransactionError("workflow_transaction_store_missing")
    expected = _config_identity(participants[0])
    if any(_config_identity(store) != expected for store in participants[1:]):
        raise WorkflowTransactionError("workflow_transaction_database_mismatch")

    for store in participants:
        if getattr(store, _BOUND_MARKER, False):
            continue
        original = store._connect

        def connect(_original: Any = original) -> Any:
            shared = _ACTIVE_CONNECTION.get()
            if shared is None:
                return _original()
            return _BorrowedConnection(shared)

        setattr(store, _ORIGINAL_CONNECT, original)
        store._connect = connect
        setattr(store, _BOUND_MARKER, True)


@contextmanager
def workflow_transaction(owner: Any) -> Iterator[Any]:
    """Run all bound workflow-store writes in one outer PostgreSQL transaction."""
    if not getattr(owner, _BOUND_MARKER, False):
        bind_workflow_stores(owner)

    existing = _ACTIVE_CONNECTION.get()
    if existing is not None:
        with existing.transaction():
            yield existing
        return

    original_connect = getattr(owner, _ORIGINAL_CONNECT, None)
    if original_connect is None:
        raise WorkflowTransactionError("workflow_transaction_store_not_bound")

    with original_connect() as connection:
        token = _ACTIVE_CONNECTION.set(connection)
        try:
            with connection.transaction():
                yield connection
        finally:
            _ACTIVE_CONNECTION.reset(token)
