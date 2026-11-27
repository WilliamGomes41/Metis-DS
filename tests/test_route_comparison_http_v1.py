"""One real Settings flow proves that experimental evidence stays outside Review."""
# release-control-evidence: toegang
# release-control-evidence: metrics teller noemer score-must-drop
from fastapi.testclient import TestClient

from src.review.review_ledger import read_events
from src.integrity_kernel import stable_hash
from src.settings.quality_metrics_app_v1 import capture
from src.settings.quality_metrics_v1 import build_report
from test_d5_4_review_interaction_evidence import _system, PASSWORD


def test_settings_route_comparison_is_retired_and_keeps_canonical_state_unchanged(tmp_path, *, production_app, production_console):
    console, users, snapshot_id, _ = _system(tmp_path, production_console=production_console)
    before_objects = stable_hash(console.snapshot_objects(snapshot_id))
    before_events = read_events(console._ledger_path)
    before_quality = build_report(capture(console, users["researcher"])["documents"], as_of="2026-09-28T00:00:00+00:00")
    client = TestClient(production_app(console))
    client.post("/login", data={"username": users["researcher"]["username"], "password": PASSWORD})
    for prefix in ("/settings/quality/compare", "/inzicht/routevergelijking"):
        for suffix in ("", "/example"):
            assert client.get(prefix + suffix, follow_redirects=False).status_code == 404
        for suffix in ("", "/example/run/test", "/example/assess/test", "/example/analyze", "/example/close", "/example/cancel"):
            response = client.post(prefix + suffix, data={"snapshot_id": snapshot_id}, follow_redirects=False)
            assert response.status_code == 404, suffix
    assert client.post("/inzicht/veiligheidstests/run", follow_redirects=False).status_code == 404
    assert client.post("/audit", follow_redirects=False).status_code == 404
    assert stable_hash(console.snapshot_objects(snapshot_id)) == before_objects
    assert read_events(console._ledger_path) == before_events
    after_quality = build_report(capture(console, users["researcher"])["documents"], as_of="2026-09-28T00:00:00+00:00")
    assert after_quality == before_quality
