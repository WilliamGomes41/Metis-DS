"""Disposable request metrics; never a domain cache or audit authority."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Any, Iterator


@dataclass
class ConsolePerformance:
    connections: int = 0
    queries: int = 0
    badge_ms: float = 0.0
    connect_ms: float = 0.0
    query_ms: float = 0.0


_CURRENT: ContextVar[ConsolePerformance | None] = ContextVar("console_performance", default=None)
_LOGGER = logging.getLogger("metis.console.performance")


@contextmanager
def performance_scope() -> Iterator[ConsolePerformance]:
    """Each request owns one mutable counter, including copied thread contexts."""
    metrics = ConsolePerformance()
    token = _CURRENT.set(metrics)
    try:
        yield metrics
    finally:
        _CURRENT.reset(token)


def measure_badges(function: Any) -> Any:
    @wraps(function)
    def measured(*args: Any, **kwargs: Any) -> Any:
        metrics = _CURRENT.get()
        if metrics is None:
            return function(*args, **kwargs)
        start = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            metrics.badge_ms += (time.perf_counter() - start) * 1000
    return measured


def connect_postgres(psycopg: Any, *args: Any, **kwargs: Any) -> Any:
    """Count attempted connections and statement calls, including failed calls.

    No SQL text or parameters are retained. Outside a measurement scope psycopg
    receives exactly its original arguments. Transactions remain psycopg-owned.
    """
    metrics = _CURRENT.get()
    if metrics is None:
        return psycopg.connect(*args, **kwargs)
    metrics.connections += 1

    class MeasuredCursor(psycopg.Cursor):
        def execute(self, *args: Any, **kwargs: Any) -> Any:
            metrics.queries += 1
            start = time.perf_counter()
            try:
                return super().execute(*args, **kwargs)
            finally:
                metrics.query_ms += (time.perf_counter() - start) * 1000

        def executemany(self, *args: Any, **kwargs: Any) -> Any:
            metrics.queries += 1
            start = time.perf_counter()
            try:
                return super().executemany(*args, **kwargs)
            finally:
                metrics.query_ms += (time.perf_counter() - start) * 1000

    kwargs["cursor_factory"] = MeasuredCursor
    start = time.perf_counter()
    try:
        return psycopg.connect(*args, **kwargs)
    finally:
        metrics.connect_ms += (time.perf_counter() - start) * 1000


def install_console_performance(app: Any) -> None:
    # Gunicorn need not configure the application's root logger. Keep this one
    # safe operational stream visible without changing other logger policies.
    if not _LOGGER.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.INFO)
    _LOGGER.propagate = False

    @app.middleware("http")
    async def console_performance(request: Any, call_next: Any) -> Any:
        start = time.perf_counter()
        status = 500
        with performance_scope() as metrics:
            try:
                response = await call_next(request)
                status = response.status_code
                return response
            finally:
                # Only the matched route template is logged, never the raw URL.
                route = getattr(request.scope.get("route"), "path", "<unmatched>")
                try:
                    _LOGGER.info(
                        "console_performance route=%s status=%d duration_ms=%.3f "
                        "badge_ms=%.3f db_connections=%d db_queries=%d "
                        "db_connect_ms=%.3f db_query_ms=%.3f",
                        route, status, (time.perf_counter() - start) * 1000,
                        metrics.badge_ms, metrics.connections, metrics.queries,
                        metrics.connect_ms, metrics.query_ms,
                    )
                except Exception:
                    # Diagnostics must not change the result of a domain request.
                    pass
