"""One real Settings flow proves that experimental evidence stays outside Review."""
# release-control-evidence: toegang
# release-control-evidence: metrics teller noemer score-must-drop
from fastapi.testclient import TestClient

from src.review_ledger import read_events
from src.integrity_kernel import stable_hash
from src.quality_metrics_app_v1 import capture
from src.quality_metrics_v1 import build_report
from test_d5_4_review_interaction_evidence import _system, PASSWORD


def test_settings_route_comparison_is_retired_and_keeps_canonical_state_unchanged(tmp_path, monkeypatch, *, production_app, production_console):
    console, users, snapshot_id, _ = _system(tmp_path, production_console=production_console)
    monkeypatch.setenv("METIS_LLM_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("METIS_LLM_MODEL", "synthetic-test-model")
    before_objects = stable_hash(console.snapshot_objects(snapshot_id))
    before_events = read_events(console._ledger_path)
    before_quality = build_report(capture(console, users["researcher"])["documents"], as_of="2026-09-28T00:00:00+00:00")
    client = TestClient(production_app(console))
    assert client.get("/settings/quality/compare").status_code == 401
    client.post("/login", data={"username": users["researcher"]["username"], "password": PASSWORD})
    home = client.get("/settings/quality/compare")
    assert home.status_code == 200
    assert "nieuwe vergelijkingen worden niet gestart" in home.text
    assert 'action="/inzicht/routevergelijking"' not in home.text
    for path in ("/settings/quality/compare", "/inzicht/routevergelijking"):
        refused = client.post(path, data={"snapshot_id": snapshot_id}, follow_redirects=False)
        assert refused.status_code == 400
        assert "comparison_route_retired" in refused.text
    assert stable_hash(console.snapshot_objects(snapshot_id)) == before_objects
    assert read_events(console._ledger_path) == before_events
    after_quality = build_report(capture(console, users["researcher"])["documents"], as_of="2026-09-28T00:00:00+00:00")
    assert after_quality == before_quality
