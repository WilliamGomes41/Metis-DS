"""Post-#120 audit remediation 5: topology bound (scale).

Supported console topology is CONFIGURE-only: one Gunicorn worker,
one instance, sequential writes. Accidental multi-worker / multi-instance
/ multi-writer assumptions MUST fail closed or be clearly out-of-bound.
EXTEND for multiple writers (consistent mutate-path for accounts /
envelopes / bindings) is out of scope here.

Markers in this file are CI metadata pointing at these checks
(scripts/release_control_preflight.py and this suite). They are not
live-release evidence.

# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.topology_bound_v1 import (
    SUPPORTED_INSTANCE_COUNT,
    SUPPORTED_WRITE_MODE,
    SUPPORTED_WORKERS,
    TopologyBoundError,
    assert_supported_topology,
    evaluate_topology,
)


ROOT = Path(__file__).resolve().parents[1]
STARTUP = ROOT / "scripts" / "azure_console_startup.sh"

pytestmark = [
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _clean_topology_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "WEB_CONCURRENCY",
        "GUNICORN_WORKERS",
        "CONSOLE_GUNICORN_WORKERS",
        "GUNICORN_CMD_ARGS",
        "CONSOLE_INSTANCE_COUNT",
        "CONSOLE_WRITE_MODE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_supported_topology_is_one_worker_one_instance_sequential_writes() -> None:
    assert SUPPORTED_WORKERS == 1
    assert SUPPORTED_INSTANCE_COUNT == 1
    assert SUPPORTED_WRITE_MODE == "sequential"


def test_default_env_is_inside_supported_topology(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_topology_env(monkeypatch)
    result = evaluate_topology(os.environ)
    assert result["status"] == "PASS"
    assert result["workers"] == 1
    assert result["instances"] == 1
    assert result["write_mode"] == "sequential"
    assert result["errors"] == []
    assert assert_supported_topology(os.environ)["status"] == "PASS"


def test_explicit_single_writer_env_stays_in_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_topology_env(monkeypatch)
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    monkeypatch.setenv("CONSOLE_INSTANCE_COUNT", "1")
    monkeypatch.setenv("CONSOLE_WRITE_MODE", "sequential")
    result = evaluate_topology(os.environ)
    assert result["status"] == "PASS"
    assert result["workers"] == 1
    assert result["instances"] == 1


@pytest.mark.parametrize(
    "name,value",
    (
        ("WEB_CONCURRENCY", "2"),
        ("WEB_CONCURRENCY", "4"),
        ("GUNICORN_WORKERS", "3"),
        ("CONSOLE_GUNICORN_WORKERS", "2"),
    ),
)
def test_multi_worker_env_fails_closed(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    _clean_topology_env(monkeypatch)
    monkeypatch.setenv(name, value)
    result = evaluate_topology(os.environ)
    assert result["status"] == "BLOCKED"
    assert result["workers"] != 1 or "multi_worker" in " ".join(result["errors"])
    errors = " ".join(result["errors"])
    assert "multi_worker_out_of_bound" in errors
    with pytest.raises(TopologyBoundError, match="multi_worker_out_of_bound"):
        assert_supported_topology(os.environ)


def test_gunicorn_cmd_args_multi_worker_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_topology_env(monkeypatch)
    monkeypatch.setenv("GUNICORN_CMD_ARGS", "--bind 0.0.0.0:8000 --workers 4")
    result = evaluate_topology(os.environ)
    assert result["status"] == "BLOCKED"
    assert "multi_worker_out_of_bound" in " ".join(result["errors"])
    with pytest.raises(TopologyBoundError, match="multi_worker_out_of_bound"):
        assert_supported_topology(os.environ)


def test_gunicorn_cmd_args_dash_w_multi_worker_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_topology_env(monkeypatch)
    monkeypatch.setenv("GUNICORN_CMD_ARGS", "-w 2 -k uvicorn.workers.UvicornWorker")
    with pytest.raises(TopologyBoundError, match="multi_worker_out_of_bound"):
        assert_supported_topology(os.environ)


def test_invalid_worker_count_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_topology_env(monkeypatch)
    monkeypatch.setenv("WEB_CONCURRENCY", "abc")
    result = evaluate_topology(os.environ)
    assert result["status"] == "BLOCKED"
    with pytest.raises(TopologyBoundError):
        assert_supported_topology(os.environ)


def test_multi_instance_env_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_topology_env(monkeypatch)
    monkeypatch.setenv("CONSOLE_INSTANCE_COUNT", "2")
    result = evaluate_topology(os.environ)
    assert result["status"] == "BLOCKED"
    assert "multi_instance_out_of_bound" in " ".join(result["errors"])
    with pytest.raises(TopologyBoundError, match="multi_instance_out_of_bound"):
        assert_supported_topology(os.environ)


def test_explicit_multi_writer_mode_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_topology_env(monkeypatch)
    monkeypatch.setenv("CONSOLE_WRITE_MODE", "multi_writer")
    result = evaluate_topology(os.environ)
    assert result["status"] == "BLOCKED"
    assert "multi_writer_mode_out_of_bound" in " ".join(result["errors"])
    with pytest.raises(TopologyBoundError, match="multi_writer_mode_out_of_bound"):
        assert_supported_topology(os.environ)


def test_build_app_fails_closed_when_multi_worker_assumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.console_asgi import build_app

    _clean_topology_env(monkeypatch)
    monkeypatch.setenv("CONSOLE_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("CONSOLE_BOOTSTRAP_USERNAME", raising=False)
    monkeypatch.delenv("CONSOLE_BOOTSTRAP_PASSWORD", raising=False)
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    with pytest.raises(TopologyBoundError, match="multi_worker_out_of_bound"):
        build_app()


def test_build_app_fails_closed_when_multi_instance_assumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.console_asgi import build_app

    _clean_topology_env(monkeypatch)
    monkeypatch.setenv("CONSOLE_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("CONSOLE_BOOTSTRAP_USERNAME", raising=False)
    monkeypatch.delenv("CONSOLE_BOOTSTRAP_PASSWORD", raising=False)
    monkeypatch.setenv("CONSOLE_INSTANCE_COUNT", "3")
    with pytest.raises(TopologyBoundError, match="multi_instance_out_of_bound"):
        build_app()


def test_azure_startup_pins_one_gunicorn_worker_and_asserts_topology() -> None:
    text = STARTUP.read_text(encoding="utf-8")
    assert "gunicorn -w 1 " in text
    assert "-w 2" not in text
    assert "--workers" not in text
    assert "assert_supported_topology" in text
    assert "one Gunicorn worker" in text or "één Gunicorn-worker" in text
    assert "sequential" in text.lower() or "sequentiële" in text


def test_azure_startup_fails_closed_on_web_concurrency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "azure_console_startup.sh"
    script.write_text(STARTUP.read_text(encoding="utf-8"), encoding="utf-8")
    env = os.environ.copy()
    env["WEB_CONCURRENCY"] = "2"
    env["PORT"] = "8099"
    result = subprocess.run(
        ["bash", str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "out of bound" in combined or "multi_worker" in combined


def test_docs_declare_supported_topology_not_silent_multi_writer() -> None:
    recovery = (ROOT / "docs" / "RUNTIME_DATA_RECOVERY.md").read_text(encoding="utf-8")
    startup = STARTUP.read_text(encoding="utf-8")
    assert "één Gunicorn-worker" in recovery or "one Gunicorn worker" in recovery
    assert "één instance" in recovery or "one instance" in recovery
    assert "sequentiële writes" in recovery or "sequential writes" in recovery
    assert "multi-writer" in recovery.lower() or "multi-writer" in startup.lower()
    assert "out of bound" in recovery.lower() or "buiten de topologie" in recovery.lower()


def test_roadmap_records_remediation_5_landing_note() -> None:
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = "Eigenaarslock 2026-09-06 — Post-#120 audit acceptatiecorrectie (ROADMAP)"
    lock = roadmap[roadmap.index(heading) :]
    next_lock = lock.find("\n## ", 1)
    section = lock if next_lock < 0 else lock[:next_lock]
    note = section[section.index("Remediatie 5 (topology bound)") :]
    assert "die Forge-golf is in code" in note
    assert "Gunicorn" in note
    assert "topology bound" in changelog.lower()
    assert "one Gunicorn worker" in changelog or "one gunicorn worker" in changelog.lower()


def test_remediation_5_does_not_open_multi_writer_extend_or_protocol() -> None:
    module = (ROOT / "src" / "topology_bound_v1.py").read_text(encoding="utf-8")
    assert "CONFIGURE" in module
    assert "EXTEND" in module
    assert "accounts/envelopes/bindings" in module or "session reload" in module
    root_protocol = (ROOT / "PROTOCOL.md").read_text(encoding="utf-8")
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.31.0") == 1
    assert not (ROOT / "docs" / "PROTOCOL_V2_32_TOPOLOGY_BOUND_DELTA.md").exists()
    assert not (ROOT / "HANDOFF.md").exists()
