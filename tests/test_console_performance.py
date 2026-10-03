"""Request telemetry isolation/failure/privacy proof for #490.

# release-control-evidence: metrics
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: releasebewijs
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.console_performance_v1 import (
    _CURRENT, _LOGGER, connect_postgres, install_console_performance,
    measure_badges, performance_scope,
)


class Cursor:
    def __init__(self): pass
    def execute(self, *args, **kwargs):
        if args[0] == "FAIL": raise ValueError("synthetic query failure")
        return self
    def executemany(self, *args, **kwargs): return self


def connection(*args, **kwargs):
    return SimpleNamespace(cursor=kwargs.get("cursor_factory", Cursor)())


def test_counts_include_failures_without_retaining_parameters():
    fake = SimpleNamespace(Cursor=Cursor, connect=connection)
    with performance_scope() as metrics:
        con = connect_postgres(fake, "private connection string")
        con.cursor.execute("SELECT secret", ["private parameter"])
        with pytest.raises(ValueError): con.cursor.execute("FAIL")
        con.cursor.executemany("private SQL", [["private parameter"]])
        assert metrics.connections == 1 and metrics.queries == 3
        assert "private" not in repr(metrics)
    assert _CURRENT.get() is None
    def failed_connection(*args, **kwargs): raise OSError("synthetic connection failure")
    fake.connect = failed_connection
    with performance_scope() as metrics:
        with pytest.raises(OSError): connect_postgres(fake)
        assert metrics.connections == 1


def test_overlapping_contexts_and_threads_are_isolated():
    async def run():
        ready = asyncio.Event()
        async def one(number):
            with performance_scope() as metrics:
                metrics.connections = number
                ready.set()
                await asyncio.sleep(0)
                # Thread copies share only their owning request's counter.
                def add(): _CURRENT.get().queries += number
                await asyncio.to_thread(add)
                assert metrics.connections == number and metrics.queries == number
                return metrics
        results = await asyncio.gather(one(1), one(2))
        assert results[0] is not results[1]
        assert _CURRENT.get() is None
    asyncio.run(run())


def test_badge_time_is_recorded_on_failure():
    @measure_badges
    def failing(): raise ValueError("synthetic error")
    with performance_scope() as metrics:
        with pytest.raises(ValueError): failing()
        assert metrics.badge_ms > 0


def test_request_log_uses_route_template_and_reports_errors(monkeypatch):
    app = FastAPI()
    @app.middleware("http")
    async def dependency_work(request, call_next):
        _CURRENT.get().queries += 2
        return await call_next(request)
    install_console_performance(app)
    messages = []
    monkeypatch.setattr(_LOGGER, "info", lambda fmt, *args: messages.append(fmt % args))
    @app.get("/document/{document_id}")
    def document(document_id: str):
        _CURRENT.get().queries += 3
        return {"ok": True}
    @app.get("/failure")
    def failure(): raise RuntimeError("private failure text")
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/document/private-id?token=private-secret").status_code == 200
    assert "route=/document/{document_id}" in messages[-1]
    assert "db_queries=5" in messages[-1]
    assert "private" not in messages[-1]
    assert client.get("/failure").status_code == 500
    assert "status=500" in messages[-1] and "private" not in messages[-1]
    assert _CURRENT.get() is None
    def broken_logger(*args): raise OSError("synthetic logger failure")
    monkeypatch.setattr(_LOGGER, "info", broken_logger)
    assert client.get("/document/one").status_code == 200
