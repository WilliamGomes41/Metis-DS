"""Chronological synthetic evidence, not production predictive-accuracy proof.

# release-control-evidence: scope/belofte
# release-control-evidence: metrics teller/noemer score-must-drop
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from datetime import datetime, timezone
import json
import unittest
import shutil
import subprocess
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from src.telemetry.analysis import summarize
from src.telemetry.routes import install_telemetry_routes

NOW = 1_800_000_000.0
QUALITY = {"status": "no_known_loss", "coverage": "not_established"}


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def history(values, *, start=NOW - 4500, route="/review", commit="abc123", phase=0.2,
            samples=10, request_prefix=""):
    events = []
    for index, value in enumerate(values):
        for sample in range(samples):
            elapsed = value[sample % len(value)] if isinstance(value, list) else value
            at = start + index * 300 + 30 + sample
            rid = f"{request_prefix}{route}-{commit}-{index}-{sample}"
            share = phase[index] if isinstance(phase, list) else phase
            common = {"request_id": rid, "route": route, "method": "GET", "commit": commit}
            events.extend([
                dict(common, ts=timestamp(at - elapsed / 1000), event="request_started"),
                dict(common, ts=timestamp(at), event="request_finished", outcome="completed",
                     status=200, elapsed_ms=elapsed,
                     phases={"db": {"exclusive_ms": elapsed * share},
                             **{f"other{n}": {"exclusive_ms": elapsed * (1-share)/3}
                                for n in range(3)}}),
            ])
    return events


def analyze(events, *, now=NOW, quality=QUALITY, filters=None):
    return summarize(events, now=now, since=now - 900, quality=quality, filters=filters)


class HistoricalTelemetryTests(unittest.TestCase):
    def test_sustained_latency_spread_and_phase_changes_have_independent_evidence(self):
        cases = [
            ([100] * 12 + [180] * 3, 0.2, "latency_p50_ms"),
            ([[100] * 9 + [110]] * 12 + [[100] * 6 + [250] * 4] * 3,
             0.2, "latency_spread_ms"),
            ([100] * 15, [0.2] * 12 + [0.55] * 3, "phase_share:db"),
        ]
        for values, phase, metric in cases:
            with self.subTest(metric=metric):
                h = analyze(history(values, phase=phase))["historical"]
                finding = next(f for f in h["findings"] if f["metric"] == metric)
                self.assertEqual(finding["reference_samples"], 120)
                self.assertEqual(finding["evaluation_samples"], 30)
                self.assertEqual(len(finding["evaluation_values"]), 3)
                self.assertIsNone(finding["time_to_limit_seconds"])
                self.assertEqual(h["reference"]["until"], h["evaluation"]["since"])
                self.assertEqual(h["coverage"], "not_established")

    def test_stable_noise_spike_recovery_and_route_mix_are_controls(self):
        for values in ([100] * 15, [100, 110, 90] * 5,
                       [100] * 14 + [500], [100] * 12 + [500, 100, 100]):
            self.assertEqual(analyze(history(values))["historical"]["findings"], [])
        fast = history([100] * 15, route="/fast", samples=5)
        slow = history([900] * 15, route="/slow", samples=10)
        # Additional slow traffic changes the aggregate, not either cohort.
        mix = fast + slow + history([900] * 3, start=NOW - 900, route="/slow", samples=50, request_prefix="extra-")
        finishes = [e for e in mix if e["event"] == "request_finished"]
        self.assertEqual(len(finishes), len({e["request_id"] for e in finishes}))
        h = analyze(mix)["historical"]
        self.assertEqual(h["eligible_cohorts"], 2)
        self.assertEqual(h["unsupported_cohorts"], 0)
        self.assertEqual(h["findings"], [])

    def test_new_commit_and_unknown_commit_cannot_borrow_a_baseline(self):
        events = history([100] * 12) + history([800] * 3, start=NOW - 900, commit="new123")
        h = analyze(events)["historical"]
        self.assertEqual(h["findings"], [])
        self.assertEqual(h["unsupported_cohorts"], 2)
        h = analyze(history([100] * 12 + [800] * 3, commit="unknown"))["historical"]
        self.assertEqual(h["status"], "insufficient")
        self.assertEqual(h["excluded_requests"], 150)

    def test_missing_data_and_biased_filters_abstain_instead_of_proving_health(self):
        events = history([100] * 12 + [800] * 3)
        for quality in (None, {"status": "partial"}, {"status": "insufficient"}):
            h = analyze(events, quality=quality)["historical"]
            self.assertEqual(h["reason"], "measurement_quality")
            self.assertEqual(h["findings"], [])
        for key in ("q", "error", "state", "status"):
            self.assertEqual(analyze(events, filters={key: "something"})["historical"]["reason"], "selection_bias")
        # Remove an entire baseline bin, even though the pooled total is ample.
        events = [e for e in events if not NOW - 4200 <= datetime.fromisoformat(e["ts"]).timestamp() < NOW - 3900]
        self.assertEqual(analyze(events)["historical"]["status"], "insufficient")
        self.assertEqual(analyze([])["historical"]["status"], "insufficient")

    def test_incomplete_phase_and_invalid_duration_are_not_silent_samples(self):
        events = history([100] * 15, phase=[0.2] * 12 + [0.6] * 3)
        events[-1]["phase_tree_truncated"] = True
        h = analyze(events)["historical"]
        self.assertEqual(h["findings"], [])
        self.assertEqual(h["unsupported_phase_metrics"], 4)
        for invalid in (float("nan"), float("inf"), -10, True):
            altered = history([100] * 12 + [800] * 3)
            altered[-1]["elapsed_ms"] = invalid
            # Test helper directly: legacy summary percentile behavior is unchanged.
            from src.telemetry.analysis import build_requests
            from src.telemetry.history import historical_deviations
            requests, _ = build_requests(altered)
            h = historical_deviations(requests.values(), now=NOW, filters={}, quality=QUALITY)
            self.assertEqual(h["excluded_requests"], 1)
            self.assertEqual(h["findings"], [])

    def test_chronological_replay_reports_actual_delay_without_future_leakage(self):
        # A fixed 1h reference, then a sustained shift, with no deployment/errors.
        stream = history([100] * 12 + [180] * 3)
        detections = []
        existing = []
        for tick in range(1, 4):
            now = NOW - 900 + tick * 300
            prefix = [e for e in stream if datetime.fromisoformat(e["ts"]).timestamp() < now]
            before = analyze(prefix, now=now)
            with_future = analyze(stream, now=now)
            self.assertEqual(before["historical"], with_future["historical"])
            detections.append(bool(before["historical"]["findings"]))
            existing.append(any(i["severity"] in ("warning", "serious", "critical") for i in before["insights"]))
        self.assertEqual(detections, [False, False, True])
        self.assertEqual(existing, [False, False, False])

    @unittest.skipUnless(shutil.which("node"), "Node is required for production rendering checks")
    def test_actual_page_renderer_explains_results_abstention_and_escaping(self):
        from src.telemetry.page import _SCRIPT
        renderer = _SCRIPT[_SCRIPT.index("function renderHistorical("):_SCRIPT.index("function renderInsights(")]
        helpers = _SCRIPT[_SCRIPT.index("const nf ="):_SCRIPT.index("function query(")]
        data = analyze(history([100] * 12 + [180] * 3))["historical"]
        data["findings"][0]["cohort"]["route"] = "<img src=x onerror=alert(1)>"
        harness = """
const assert = require('node:assert/strict');
const el = (tag, attrs={}, ...children) => ({tag, attrs, children:children.flat()});
const text = node => typeof node === 'string' ? node : (node?.attrs?.text || '') + ' ' + (node?.children || []).map(text).join(' ');
let rendered, selected;
const $ = () => ({replaceChildren:(...nodes) => {rendered=nodes;}});
const applyFilters = filters => {selected=filters;};
"""
        checks = """
renderHistorical(data);
let content = rendered.map(text).join(' ');
assert.ok(content.includes('experimenteel') && content.includes('180 ms'));
assert.ok(content.includes('120 verzoeken') && content.includes('30 verzoeken'));
assert.ok(content.includes('<img src=x onerror=alert(1)>'));
function visit(node) { if (!node || typeof node === 'string') return; assert.ok(!('innerHTML' in node.attrs)); if (node.tag === 'button') node.attrs.onclick(); (node.children || []).forEach(visit); }
rendered.forEach(visit);
assert.equal(selected.commit, 'abc123');
data.findings = []; data.reason = 'measurement_quality';
renderHistorical(data);
assert.ok(rendered.map(text).join(' ').includes('meetkwaliteit is onvoldoende'));
data.reason = null;
renderHistorical(data);
assert.ok(rendered.map(text).join(' ').includes('Dit bewijst geen gezondheid'));
"""
        completed = subprocess.run([shutil.which("node")], input=harness+helpers+renderer+
                                   "const data="+json.dumps(data)+";"+checks,
                                   text=True, capture_output=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_small_slow_drift_is_a_measured_detection_limit(self):
        # A real deterioration below the explicit effect floor is deliberately
        # missed. This is a sensitivity limitation, not a healthy-load control.
        h = analyze(history([100] * 12 + [110, 115, 120]))["historical"]
        self.assertGreater(h["evaluated_metrics"], 0)
        self.assertEqual(h["findings"], [])

    def test_bounded_cohort_and_finding_omissions_are_visible(self):
        events = [e for i in range(31) for e in
                  history([100] * 12 + [180] * 3, route=f"/route-{i:02d}", samples=5)]
        h = analyze(events)["historical"]
        self.assertEqual(h["eligible_cohorts"], 30)
        self.assertEqual(h["omitted_cohorts"], 1)
        self.assertEqual(len(h["findings"]), 20)
        self.assertEqual(h["omitted_findings"], 10)

    def test_real_files_and_existing_reader_preserve_quality_abstention(self):
        import os
        import tempfile
        from pathlib import Path
        from src.telemetry.hub import TelemetryHub, recent_events
        hub = TelemetryHub()
        with tempfile.TemporaryDirectory() as directory:
            hub.configure(Path(directory))
            try:
                for event in history([100] * 12 + [180] * 3):
                    hub.record(event)
                hub.flush()
                # Match filesystem time to this fixed historical-replay clock.
                for path in Path(directory).glob("events-*.jsonl"):
                    os.utime(path, (NOW, NOW))
                with patch("src.telemetry.hub.HUB", hub):
                    quality = {}
                    events, _ = recent_events(NOW - 4500, window_start=NOW - 900, quality=quality)
                    self.assertEqual(len(events), 300)
                    self.assertEqual(analyze(events, quality=quality)["historical"]["status"], "observed_deviation")
                    with patch("src.telemetry.hub.MAX_ANALYZED_EVENTS", 200):
                        quality = {}
                        events, _ = recent_events(NOW - 4500, window_start=NOW - 900, quality=quality)
                    self.assertEqual(analyze(events, quality=quality)["historical"]["reason"], "measurement_quality")
            finally:
                hub.configure(None)

    def test_reference_boundary_uses_its_own_reconstruction_margin(self):
        import os
        import tempfile
        from pathlib import Path
        from src.telemetry.hub import TelemetryHub
        app = FastAPI()
        install_telemetry_routes(app, require_account=lambda request: {"id": "fixture"})
        handler = next(r.endpoint for r in app.routes if r.path == "/telemetry/api/summary")
        reference_start = NOW - 4500
        events = history([100] * 12 + [180] * 3)
        # Both requests finish one second into the reference. Their starts are
        # outside it; the longer case prevents a one-second special-case fix.
        for index, elapsed in enumerate((2000, 1_801_000)):
            carry = history([elapsed], start=reference_start - 29, samples=1)
            for event in carry:
                event["request_id"] = f"carry-{index}"
            events.extend(carry)
        hub = TelemetryHub()
        with tempfile.TemporaryDirectory() as directory:
            hub.configure(Path(directory))
            try:
                for event in events:
                    hub.record(event)
                hub.flush()
                for path in Path(directory).glob("events-*.jsonl"):
                    os.utime(path, (NOW, NOW))
                with patch("src.telemetry.routes.HUB", hub), patch("src.telemetry.hub.HUB", hub), patch("src.telemetry.routes.time.time", return_value=NOW):
                    results = []
                    for window in ("15m", "1h", "6h"):
                        request = Request({"type": "http", "headers": [],
                                           "query_string": f"window={window}".encode()})
                        body = json.loads(handler(request).body)
                        self.assertEqual(body["telemetry"]["quality"]["status"], "no_known_loss")
                        h = body["historical"]
                        self.assertEqual(h["status"], "observed_deviation")
                        self.assertEqual(h["excluded_requests"], 0)
                        finding = next(f for f in h["findings"] if f["metric"] == "latency_p50_ms")
                        self.assertEqual(finding["reference_samples"], 122)
                        self.assertEqual(finding["evaluation_samples"], 30)
                        results.append(h)
                    self.assertEqual(results[0], results[1])
                    self.assertEqual(results[0], results[2])
            finally:
                hub.configure(None)
        # A genuinely missing start inside the reference is still insufficient,
        # and known loss still takes precedence over any available samples.
        events = history([100] * 12 + [180] * 3)[1:]
        h = analyze(events)["historical"]
        self.assertEqual(h["status"], "insufficient")
        self.assertEqual(h["excluded_requests"], 1)
        h = analyze(events, quality={"status": "partial"})["historical"]
        self.assertEqual(h["reason"], "measurement_quality")

    def test_summary_route_passes_quality_and_authorizes_before_reading(self):
        app = FastAPI()
        def account(request):
            if not request.headers.get("x-test-account"):
                raise HTTPException(401)
            return {"id": "test"}
        install_telemetry_routes(app, require_account=account)
        handler = next(r.endpoint for r in app.routes if r.path == "/telemetry/api/summary")
        req = lambda auth: Request({"type": "http", "query_string": b"window=15m",
                                   "headers": [(b"x-test-account", b"yes")] if auth else []})
        def read(*args, quality, **kwargs):
            quality.update(QUALITY)
            return history([100] * 12 + [180] * 3), False
        with patch("src.telemetry.routes.recent_events", side_effect=read) as reader, patch("src.telemetry.routes.time.time", return_value=NOW):
            with self.assertRaises(HTTPException):
                handler(req(False))
            reader.assert_not_called()
            response = handler(req(True))
            body = json.loads(response.body)
            self.assertEqual(body["historical"]["status"], "observed_deviation")
            self.assertEqual(body["telemetry"]["quality"], QUALITY)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        def broken(*args, quality, **kwargs):
            quality.update(status="partial")
            return history([100] * 12 + [180] * 3), True
        with patch("src.telemetry.routes.recent_events", side_effect=broken), patch("src.telemetry.routes.time.time", return_value=NOW):
            self.assertEqual(json.loads(handler(req(True)).body)["historical"]["reason"], "measurement_quality")


class HistoricalTelemetryHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_summary_uses_existing_hub_quality_and_auth(self):
        import tempfile
        from pathlib import Path
        import httpx
        from src.telemetry.hub import TelemetryHub
        app = FastAPI()
        def account(request):
            if request.headers.get("x-test-account") != "fixture":
                raise HTTPException(401)
            return {"id": "fixture"}
        install_telemetry_routes(app, require_account=account)
        hub = TelemetryHub()
        with tempfile.TemporaryDirectory() as directory:
            hub.configure(Path(directory))
            for event in history([100] * 12 + [180] * 3):
                hub.record(event)
            hub.flush()
            import os
            for path in Path(directory).glob("events-*.jsonl"):
                os.utime(path, (NOW, NOW))
            with patch("src.telemetry.routes.HUB", hub), patch("src.telemetry.hub.HUB", hub), patch("src.telemetry.routes.time.time", return_value=NOW):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    self.assertEqual((await client.get("/telemetry/api/summary")).status_code, 401)
                    response = await client.get("/telemetry/api/summary?window=15m", headers={"x-test-account": "fixture"})
                    self.assertEqual(response.status_code, 200)
                    body = response.json()
                    self.assertEqual(body["historical"]["status"], "observed_deviation")
                    self.assertEqual(body["telemetry"]["quality"]["status"], "no_known_loss")
            hub.configure(None)


if __name__ == "__main__":
    unittest.main()
