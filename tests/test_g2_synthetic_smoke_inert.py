from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "g2_synthetic_sha256_smoke.py"


def _load_smoke():
    spec = importlib.util.spec_from_file_location("g2_synthetic_sha256_smoke", SMOKE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_constant_is_inert() -> None:
    smoke = _load_smoke()
    assert smoke.SMOKE_INERT is True
    assert smoke.OWNER_CONSENT_ENV == "METIS_G2_SYNTHETIC_SMOKE_OWNER_CONSENT"
    with pytest.raises(RuntimeError, match="smoke_not_armed"):
        smoke.execute_smoke()
    prepared = smoke.prepared_synthetic_digest()
    assert prepared["sha256"]
    assert prepared["inert"] == "True"
    assert len(prepared["sha256"]) == 64


def test_smoke_script_refuses_without_running_azure() -> None:
    result = subprocess.run(
        [sys.executable, str(SMOKE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "", "METIS_G2_SYNTHETIC_SMOKE_OWNER_CONSENT": "I_HAVE_EXPLICIT_OWNER_CONSENT"},
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "INERT"
    assert payload["ran"] is False
    assert payload["smoke_inert"] is True
    assert payload["azure_called"] is False
    assert payload["publish_called"] is False
    assert payload["mutations"] == []


def test_ci_and_docs_do_not_invoke_the_smoke() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "G2_BLOB_ACTIVATION_RUNBOOK.md").read_text(encoding="utf-8")
    assert "g2_synthetic_sha256_smoke" not in ci
    assert "MUST NOT run" in runbook
    assert "SMOKE_INERT" in runbook


def test_smoke_module_main_never_reaches_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    smoke = _load_smoke()

    def fail() -> None:
        raise AssertionError("execute_smoke must not run")

    monkeypatch.setattr(smoke, "execute_smoke", fail)
    assert smoke.main([]) == 2
