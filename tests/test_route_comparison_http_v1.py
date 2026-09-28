"""One real Settings flow proves that experimental evidence stays outside Review."""
import re

from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.review_ledger import read_events
from src.integrity_kernel import stable_hash
from test_d5_4_review_interaction_evidence import _system, PASSWORD


def _version(body):
    return re.search(r'name="version" value="(\d+)"', body).group(1)


def test_settings_paired_route_flow_keeps_canonical_state_unchanged(tmp_path, monkeypatch):
    console, users, snapshot_id, _ = _system(tmp_path)
    monkeypatch.setenv("METIS_LLM_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("METIS_LLM_MODEL", "synthetic-test-model")

    def fake_execute(row, route):
        return ([{"text": "Gebruik interventie A.", "type": "recommendation",
                  "source_fragment_ids": [row["fragments"][0]["fragment_id"]]}],
                {"strategy": route, "model": row["semantic_model"] if route == "semantic" else None})

    monkeypatch.setattr("src.route_comparison_app_v1.execute_arm", fake_execute)
    before_objects = stable_hash(console.snapshot_objects(snapshot_id))
    before_events = read_events(console._ledger_path)
    client = TestClient(create_console_app(console))
    assert client.get("/settings/quality/compare").status_code == 401
    client.post("/login", data={"username": users["researcher"]["username"], "password": PASSWORD})
    home = client.get("/settings/quality/compare")
    assert home.status_code == 200
    created = client.post("/settings/quality/compare", data={"snapshot_id": snapshot_id},
                          follow_redirects=False)
    assert created.status_code == 303
    path = created.headers["location"]
    draft = client.get(path)
    fragment_id = re.search(r'name="fragment_id" value="([^"]+)"', draft.text).group(1)
    frozen = client.post(path + "/freeze", data={"version": _version(draft.text),
                                                "fragment_id": fragment_id}, follow_redirects=False)
    assert frozen.status_code == 303, frozen.text
    for route in ("deterministic", "semantic"):
        current = client.get(path)
        run = client.post(path + "/run/" + route, data={"version": _version(current.text)},
                          follow_redirects=False)
        assert run.status_code == 303, run.text
    blind = client.get(path)
    assert blind.status_code == 200
    assert "Voorstel A" in blind.text and "Voorstel B" in blind.text
    assert "De routenamen blijven verborgen" in blind.text
    for label in ("A", "B"):
        current = client.get(path)
        assessed = client.post(path + "/assess/" + label,
                               data={"version": _version(current.text), "choice_0": "direct",
                                     "coverage": "complete", "actions": "1"},
                               follow_redirects=False)
        assert assessed.status_code == 303, assessed.text
    current = client.get(path)
    assert client.post(path + "/analyze", data={"version": _version(current.text)},
                       follow_redirects=False).status_code == 303
    report = client.get(path)
    assert "Resultaten per route" in report.text
    assert stable_hash(console.snapshot_objects(snapshot_id)) == before_objects
    assert read_events(console._ledger_path) == before_events
