"""Offline, credential-free characterization fixtures; no product changes."""
import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest


def pytest_addoption(parser):
    parser.addoption("--record-characterization", action="store_true", default=False)
    parser.addoption("--characterization-mutation", choices=("ingest", "review"), default=None,
                     help="One temporary in-memory mutation; expected to make goldens red")


@pytest.fixture(autouse=True)
def offline_clock(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Characterization attempted network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "gethostbyname", forbidden)
    for key in tuple(os.environ):
        if key.startswith(("METIS_", "AZURE_", "G2_", "OPENAI_", "PG")):
            monkeypatch.delenv(key, raising=False)
    import src.operations_console_v1 as op
    import src.operations_console_app as ui
    import src.quality_evidence_v1 as quality
    import src.processing_retry_v1 as retry
    import src.attempt_diagnostics_v1 as diagnostics
    import src.processing_trace_v1 as trace

    stamp = "2026-10-17T08:00:00+00:00"
    monkeypatch.setattr(op, "utc_now", lambda: stamp)
    monkeypatch.setattr(op, "quality_instant", lambda: stamp)
    monkeypatch.setattr(op, "time", SimpleNamespace(monotonic=time.monotonic))
    monkeypatch.setattr(op.uuid, "uuid4", lambda: UUID(int=1))
    monkeypatch.setattr(quality, "uuid4", lambda: UUID(int=2))
    monkeypatch.setattr(quality, "instant", lambda: stamp)
    monkeypatch.setattr(retry, "now", lambda: datetime(2026, 10, 17, 8, tzinfo=timezone.utc))
    monkeypatch.setattr(ui, "new_review_interaction_id", lambda: "characterization-interaction")
    monkeypatch.setattr(trace, "runtime_identity", lambda: {"version": "a" * 40, "instance": "local",
                                                          "pid": 1, "runtime_id": "b" * 32})
    monkeypatch.setattr(diagnostics, "deployment_identity", lambda: "characterization-main")

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 17, 8, tzinfo=timezone.utc)

    monkeypatch.setattr(diagnostics, "datetime", Clock)
    monkeypatch.setattr(trace, "datetime", Clock)
    # Imports may query local platform metadata using uname; execution may not spawn providers.
    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.fixture(autouse=True)
def temporary_behavior_mutation(request, monkeypatch, offline_clock):
    """Mutate one expression in memory; pytest restores it after each case."""
    selected = request.config.getoption("--characterization-mutation")
    if selected is None:
        return
    if request.config.getoption("--record-characterization"):
        raise pytest.UsageError("Never record goldens while a mutation is active")
    import ast
    import inspect
    import textwrap
    import src.operations_console_v1 as op
    import src.operations_console_app as ui

    owner, name, module = (op.OperationsConsole, "ingest", op) if selected == "ingest" else (ui, "_render_review_room", ui)
    function = inspect.unwrap(getattr(owner, name))
    source, start = inspect.getsourcelines(function)
    tree = ast.parse(textwrap.dedent("".join(source)))

    class Mutate(ast.NodeTransformer):
        count = 0

        def visit_Name(self, node):
            if selected == "ingest" and node.id == "CAPTURED":
                self.count += 1
                return ast.copy_location(ast.Constant("characterization-mutated-state"), node)
            return node

        def visit_Constant(self, node):
            if selected == "review" and isinstance(node.value, str) and "<h1>Review</h1>" in node.value:
                self.count += 1
                return ast.copy_location(ast.Constant(node.value.replace("<h1>Review</h1>", "<h1>Mutated review</h1>")), node)
            return node

    mutation = Mutate()
    tree = ast.fix_missing_locations(mutation.visit(tree))
    assert mutation.count == 1, "Mutation must change exactly one expression"
    ast.increment_lineno(tree, start - 1)
    namespace = vars(module).copy()
    exec(compile(tree, inspect.getsourcefile(function), "exec"), namespace)
    monkeypatch.setattr(owner, name, namespace[name])


@pytest.fixture
def golden(request, tmp_path):
    def check(group, name, value):
        # Only the sandbox root is normalized; IDs, state, text and order remain.
        actual = json.loads(json.dumps(value, ensure_ascii=False).replace(str(tmp_path), "<TMP>"))
        def portable(item):
            if isinstance(item, dict):
                return {k: "<PYTHON>" if k == "python_version" else portable(v) for k, v in item.items()}
            if isinstance(item, list):
                return [portable(v) for v in item]
            return item
        actual = portable(actual)
        path = Path(__file__).parent / "golden" / group / (name + ".json")
        if request.config.getoption("--record-characterization"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        assert path.exists(), f"Missing reviewed golden: {path.name}"
        assert actual == json.loads(path.read_text()), f"Behavior changed: {group}/{name}"
    return check
