"""Semantic safety tests as a standalone check; the Audit room is retired.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import json
import time

import pytest

from fastapi.testclient import TestClient

from src.semantic_safety_app_v1 import install_semantic_safety_routes
from src.telemetry.hub import HUB

BASELINE = "79b35616725da3a1f42a938c2f5a874ca16cfad0"
DEPLOYED = "47e7652574ee37f91fbd58e5ffa16b2dfd44b378"


def _full_source_model(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
    block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
    text = json.dumps({"objects": [{"spans": [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}],
                                    "proposed_object_type": "unclassified"}], "abstain_reason": None})
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


def _system(tmp_path, *, commit: str | None=DEPLOYED, post_json=None, roles=('researcher',), production_app, production_console):
    from src import console_asgi
    marker = tmp_path / "deployed_commit.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    if commit is not None:
        marker.write_text(commit + "\n", encoding="utf-8")
    # Supply transport and packaged-commit evidence to the actual installer.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(console_asgi, 'install_semantic_safety_routes',
                      lambda app, console: install_semantic_safety_routes(
                          app, console, post_json=post_json, deployed_commit_path=marker))
        console = production_console(processing_binder=bind_fixture_selections, root=tmp_path)
    if not any(a['username'] == 'anne' for a in console.list_accounts()):
        console.create_account(username="anne", password="anne-secret", roles=roles, display_name="Anne")
    app = production_app(console)
    client = TestClient(app, base_url="https://testserver")
    assert client.post("/login", data={"username": "anne", "password": "anne-secret"}, follow_redirects=False).status_code == 303
    return console, client


def test_run_shows_result_directly_and_persists_nothing(tmp_path, monkeypatch, *, production_app, production_console):
    monkeypatch.setenv("METIS_LLM_MODEL", "test-model")
    monkeypatch.setenv("METIS_LLM_API_KEY", "shared-provider-secret")
    console, client = _system(tmp_path, post_json=_full_source_model, production_app=production_app, production_console=production_console)
    before = console.list_envelopes()
    page = client.get("/inzicht/veiligheidstests")
    assert page.status_code == 200
    assert "Veiligheidstests uitvoeren" in page.text and BASELINE in page.text and DEPLOYED in page.text
    since = time.time() - 1
    response = client.post("/inzicht/veiligheidstests/run", follow_redirects=False)
    assert response.status_code == 200
    assert "5 van 5 veiligheidstests geslaagd" in response.text
    assert "Machinecheck PASS" in response.text and "geen activatiebesluit" in response.text
    assert "shared-provider-secret" not in response.text
    assert not (console.runtime / "audits").exists()
    assert console.list_envelopes() == before
    assert not (console.runtime / "published_projection.jsonl").exists()
    events = [e for e in HUB.events(since) if e.get("event") == "semantic_safety_run"]
    assert events and events[-1]["case_count"] == 5 and events[-1]["pass_count"] == 5
    assert "shared-provider-secret" not in json.dumps(events)


def test_run_fails_closed_without_valid_packaged_commit(tmp_path, monkeypatch, *, production_app, production_console):
    monkeypatch.setenv("METIS_LLM_MODEL", "test-model")
    monkeypatch.setenv("METIS_LLM_API_KEY", "shared-provider-secret")
    for commit in ("not-a-commit", None):
        console, client = _system(tmp_path / str(commit), commit=commit, production_app=production_app, production_console=production_console)
        page = client.get("/inzicht/veiligheidstests")
        assert "Run geblokkeerd" in page.text and "Veiligheidstests uitvoeren" not in page.text
        response = client.post("/inzicht/veiligheidstests/run")
        assert response.status_code == 200
        assert "Geen geldige packaged deployment-commit beschikbaar" in response.text
        assert not (console.runtime / "audits").exists()


def test_safety_tests_require_researcher(tmp_path, *, production_app, production_console):
    _console, client = _system(tmp_path, roles=("reviewer",), production_app=production_app, production_console=production_console)
    assert client.get("/inzicht/veiligheidstests").status_code == 403
    assert client.post("/inzicht/veiligheidstests/run").status_code == 403
    anonymous = TestClient(client.app, base_url="https://testserver")
    assert anonymous.get("/inzicht/veiligheidstests").status_code == 401


def test_retired_audit_addresses_redirect_and_review_signals_stay(tmp_path, *, production_app, production_console):
    _console, client = _system(tmp_path, production_app=production_app, production_console=production_console)
    for old, new in (("/audit", "/inzicht?tab=controles"), ("/audit/new", "/inzicht?tab=controles"),
                     ("/audit/archive", "/inzicht?tab=controles"),
                     ("/audit/semantic-safety", "/inzicht/veiligheidstests")):
        response = client.get(old, follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == new, old
    assert client.get("/audit/audit-0123456789abcdef").status_code == 404
    assert client.post("/audit", data={"type": "experiment"}).status_code in (404, 405)
    controls = client.get("/inzicht?tab=controles").text
    assert 'href="/inzicht/veiligheidstests"' in controls
    assert 'href="/audit"' not in controls and 'href="/audit/archive"' not in controls
