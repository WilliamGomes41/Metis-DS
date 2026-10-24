"""Disposable inputs owned by one console read operation, never command state."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConsoleReadSnapshot:
    console: Any
    retained_only: bool = False
    envelopes: dict[str, dict[str, Any]] = field(default_factory=dict)
    listed: bool = False
    snapshot_ids: list[str] | None = None
    objects: dict[str, tuple[list[dict[str, Any]], str | None]] = field(default_factory=dict)
    current_objects: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    bindings: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    cards: list[dict[str, Any]] | None = None
    publication_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    publication_history: dict[str, bool] = field(default_factory=dict)
    publication_summary_failed: bool = False


from contextlib import contextmanager
from contextvars import ContextVar

CURRENT_READ: ContextVar[ConsoleReadSnapshot | None] = ContextVar('document_read_snapshot', default=None)


@contextmanager
def detached_document_reads():
    """Commands/background execution load their own current working inputs."""
    token = CURRENT_READ.set(None)
    try:
        yield
    finally:
        CURRENT_READ.reset(token)
