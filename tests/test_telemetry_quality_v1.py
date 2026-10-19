"""Measurement quality through the existing hub and authenticated HTTP API.

# release-control-evidence: scope/belofte
# release-control-evidence: metrics teller/noemer score-must-drop
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.telemetry import hub as hub_module
from src.telemetry.hub import TelemetryHub, recent_events
from src.telemetry.routes import install_telemetry_routes


def event(at, name="request_finished", request_id="a" * 32):
    return {"ts": datetime.fromtimestamp(at, timezone.utc).isoformat(),
            "event": name, "request_id": request_id, "route": "/review",
            "outcome": "completed", "status": 200, "elapsed_ms": 10}


class TelemetryQualityTests(unittest.TestCase):
    def setUp(self):
        self.hub = TelemetryHub()
        self.addCleanup(patch.stopall)
        patch("src.telemetry.hub.HUB", self.hub).start()
        patch("src.telemetry.routes.HUB", self.hub).start()
        self.now = time.time()

    def read(self, since, **kwargs):
        quality = {}
        events, partial = recent_events(since, quality=quality, **kwargs)
        return events, partial, quality

    def test_ring_displacement_is_scoped_and_disk_copy_is_not_reported_lost(self):
        self.hub._ring = deque(maxlen=2)
        for i in range(3):
            self.hub.record(event(self.now - 10 + i))
        events, _, quality = self.read(self.now - 60)
        self.assertEqual(len(events), 2)
        self.assertEqual(quality["process"]["ring_evictions"], 1)
        self.assertIn("ring_evictions", quality["reasons"])
        self.assertEqual(self.hub.dropped, 0)
        with tempfile.TemporaryDirectory() as directory:
            self.hub.configure(Path(directory))
            for i in range(3):
                self.hub.record(event(self.now - 5 + i))
            events, _, quality = self.read(self.now - 60)
            self.assertEqual(len(events), 3)
            self.assertNotIn("ring_evictions", quality["reasons"])
            self.hub.configure(None)

    def test_read_losses_are_per_scan_and_do_not_accumulate_as_write_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            self.hub.configure(directory)
            self.hub.record(event(self.now - 10))
            bad = directory / "events-bad.jsonl"
            bad.write_text('not-json\n[]\n{"ts":"invalid"}\n')
            for _ in range(2):
                events, _, quality = self.read(self.now - 60)
                self.assertEqual(len(events), 1)
                self.assertEqual(quality["read"]["malformed_lines"], 1)
                self.assertEqual(quality["read"]["invalid_events"], 2)
                self.assertEqual(quality["status"], "partial")
                self.assertEqual(self.hub.dropped, 0)
            original = Path.open
            def unreadable(path, *args, **kwargs):
                if path == bad:
                    raise PermissionError("synthetic")
                return original(path, *args, **kwargs)
            with patch.object(Path, "open", unreadable):
                _, _, quality = self.read(self.now - 60)
            self.assertEqual(quality["read"]["read_errors"], 1)
            self.assertEqual(quality["read"]["malformed_lines"], 0)
            self.hub.configure(None)

    @unittest.skipUnless(os.name == "posix" and os.geteuid() != 0,
                         "POSIX directory permissions require a non-root user")
    def test_real_directory_permission_failure_is_visible_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            self.hub.configure(directory)
            self.hub.record(event(self.now - 10))
            original_mode = directory.stat().st_mode & 0o777
            directory.chmod(0)
            try:
                with self.assertRaises(PermissionError):
                    os.listdir(directory)
                for _ in range(2):
                    events, _, quality = self.read(self.now - 60)
                    self.assertEqual(events, [])
                    self.assertEqual(quality["read"]["read_errors"], 1)
                    self.assertIn("read_errors", quality["reasons"])
                    self.assertEqual(self.hub.dropped, 0)
            finally:
                directory.chmod(original_mode)
            events, _, quality = self.read(self.now - 60)
            self.assertEqual(len(events), 1)
            self.assertEqual(quality["read"]["read_errors"], 0)
            self.assertEqual(quality["status"], "no_known_loss")
            self.hub.configure(None)

    def test_missing_finish_is_an_observation_not_a_confirmed_worker_failure(self):
        from src.telemetry.analysis import request_detail, summarize
        with tempfile.TemporaryDirectory() as directory:
            self.hub.configure(Path(directory))
            self.hub.record(event(self.now - 100, "request_started"))
            with self.hub._sink._path.open("a") as handle:
                handle.write("corrupted_request_finished\n")
            events, _, quality = self.read(self.now - 900)
            self.assertEqual(quality["read"]["malformed_lines"], 1)
            summary = summarize(events, now=self.now, since=self.now - 900)
            warning = next(item for item in summary["insights"]
                           if item["filter"] == {"state": "aborted"})
            self.assertEqual(warning["severity"], "warning")
            self.assertIn("telemetrie", warning["detail"])
            detail = request_detail(events, "a" * 32, now=self.now)
            self.assertEqual(detail["request"]["state"], "aborted")  # API compatibility
            self.assertEqual(detail["guidance"]["category"], "missing_completion")
            self.assertIn("niet vastgesteld", detail["guidance"]["explanation"])
            self.assertIn("meetdekking", detail["guidance"]["steps"][0])
            # A recorded finish must resolve the missing-completion warning,
            # even while an unrelated corrupt line still makes the scan partial.
            self.hub.record(event(self.now - 90))
            events, _, quality = self.read(self.now - 900)
            summary = summarize(events, now=self.now, since=self.now - 900)
            self.assertEqual(quality["read"]["malformed_lines"], 1)
            self.assertEqual(summary["kpis"]["aborted"], 0)
            self.assertFalse(any(item["filter"] == {"state": "aborted"}
                                 for item in summary["insights"]))
            self.hub.configure(None)

    def test_analysis_omission_counts_distinguish_window_and_lookback(self):
        for i in range(4):
            self.hub.record(event(self.now - 3000 + i))
        for i in range(2):
            self.hub.record(event(self.now - 60 + i))
        with patch.object(hub_module, "MAX_ANALYZED_EVENTS", 3):
            events, partial, quality = self.read(self.now - 4500, window_start=self.now - 900)
        self.assertFalse(partial)  # backwards-compatible window-only flag
        self.assertEqual(quality["analysis"]["window_omitted"], 0)
        self.assertEqual(quality["analysis"]["lookback_omitted"], 3)
        self.assertEqual(quality["status"], "partial")
        self.assertAlmostEqual(quality["analysis"]["oldest_used_at"], self.now - 2997, places=5)
        with patch.object(hub_module, "MAX_ANALYZED_EVENTS", 1):
            _, partial, quality = self.read(self.now - 4500, window_start=self.now - 900)
        self.assertTrue(partial)
        self.assertEqual(quality["analysis"]["window_omitted"], 1)
        self.assertEqual(quality["analysis"]["lookback_omitted"], 4)

    def test_decode_list_and_write_failures_remain_best_effort(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            self.hub.configure(directory)
            self.hub.record(event(self.now - 10))
            (directory / "events-undecodable.jsonl").write_bytes(b"\xff\n")
            events, _, quality = self.read(self.now - 60)
            self.assertEqual(len(events), 1)
            self.assertEqual(quality["read"]["read_errors"], 1)
            with patch.object(self.hub._sink, "files", side_effect=OSError("synthetic")):
                events, _, quality = self.read(self.now - 60)
            self.assertEqual(events, [])
            self.assertEqual(quality["read"]["read_errors"], 1)
            with patch.object(self.hub._sink, "write", side_effect=OSError("synthetic")):
                result = self.hub.record(event(self.now - 5))
            self.assertIsNotNone(result)
            _, _, quality = self.read(self.now - 60)
            self.assertEqual(quality["process"]["record_failures"], 1)
            self.assertIn("record_failures", quality["reasons"])
            self.assertEqual(quality["source"], "process_ring")

    @unittest.skipUnless(shutil.which("node"), "JavaScript runtime unavailable")
    def test_existing_ui_renders_omissions_and_no_zero_percent_without_requests(self):
        from src.telemetry.analysis import summarize
        from src.telemetry.page import _SCRIPT
        events, _, quality = self.read(self.now - 60)
        data = summarize(events, now=self.now, since=self.now - 60)
        data["telemetry"]["quality"] = quality
        # Run the production presentation functions; capture their text output.
        labels = _SCRIPT[_SCRIPT.index("const STATE_NL ="): _SCRIPT.index("const SEV_NL =")]
        helpers = _SCRIPT[_SCRIPT.index("const nf ="): _SCRIPT.index("function query(")]
        note = _SCRIPT[_SCRIPT.index("function qualityNote("): _SCRIPT.index("function renderInsights(")]
        kpis = _SCRIPT[_SCRIPT.index("function renderKpis("): _SCRIPT.index("const tip =")]
        errors = _SCRIPT[_SCRIPT.index("function renderErrors("): _SCRIPT.index("function sortable(")]
        missing = summarize([event(self.now - 100, "request_started")],
                            now=self.now, since=self.now - 900)
        harness = """
const assert = require('node:assert/strict');
const el = (tag, attrs={}, ...children) => ({text:attrs.text || '', children:children.flat()});
const text = node => typeof node === 'string' ? node : (node?.text || '') + ' ' + (node?.children || []).map(text).join(' ');
let tiles;
const $ = () => ({replaceChildren:(...nodes) => {tiles=nodes;}});
const sparkline = () => el('svg'); // Chart internals are outside this text-rendering test.
const icon = kind => el('icon', {text:kind});
const sev = kind => el('badge', {text:kind});
"""
        checks = """
renderKpis(data);
const errorTile = tiles.find(node => text(node).includes('Foutpercentage'));
assert.ok(text(errorTile).includes('onvoldoende gegevens'));
assert.ok(!text(errorTile).includes('0%'));
assert.ok(text(qualityNote(data.telemetry)).includes('Stilte bewijst geen gezondheid'));
data.telemetry.quality.analysis.window_omitted = 3;
data.telemetry.quality.analysis.lookback_omitted = 2;
const explanation = text(qualityNote(data.telemetry));
assert.ok(explanation.includes('3 events uit het gekozen venster'));
assert.ok(explanation.includes('2 eerdere events voor reconstructie'));
const missingBadge = text(stateBadge('aborted'));
assert.ok(missingBadge.includes('Afronding ontbreekt') && missingBadge.includes('warning'));
assert.ok(!missingBadge.includes('critical'));
assert.ok(text(stateBadge('error')).includes('critical'));
renderErrors(groups);
const groupText = tiles.map(text).join(' ');
assert.ok(groupText.includes('warning') && groupText.includes('telemetrie'));
assert.ok(!groupText.includes('critical'));
"""
        result = subprocess.run([shutil.which("node")], input=harness+labels+helpers+note+kpis+errors+
                                "\nconst data="+json.dumps(data)+";\nconst groups="+
                                json.dumps(missing["errors"])+";\n"+checks,
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_quality_reaches_summary_detail_and_missing_detail_behind_auth(self):
        app = FastAPI()
        def require_account(request):
            if request.headers.get("x-test-account") != "fixture":
                raise HTTPException(401)
            return {"account_id": "fixture"}
        install_telemetry_routes(app, require_account=require_account)
        with TestClient(app) as client:
            self.assertEqual(client.get("/telemetry/api/summary").status_code, 401)
            self.assertEqual(client.get("/telemetry/api/request/" + "a" * 32).status_code, 401)
            client.headers["x-test-account"] = "fixture"
            empty = client.get("/telemetry/api/summary").json()
            self.assertIsNone(empty["kpis"]["error_rate"])
            self.assertEqual(empty["telemetry"]["quality"]["status"], "insufficient")
            self.hub.record(event(self.now - 20))
            self.hub.record(event(self.now - 10, request_id="b" * 32))
            with patch.object(hub_module, "MAX_ANALYZED_EVENTS", 1):
                summary = client.get("/telemetry/api/summary").json()
                detail = client.get("/telemetry/api/request/" + "b" * 32)
                missing = client.get("/telemetry/api/request/" + "a" * 32)
            for body in (summary, detail.json(), missing.json()):
                quality = body["telemetry"]["quality"]
                self.assertEqual(quality["analysis"]["window_omitted"], 1)
                self.assertEqual(quality["coverage"], "not_established")
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.headers["cache-control"], "no-store")

    def test_registered_handlers_preserve_quality_and_authorization(self):
        # Exercises the real registered handlers without the HTTP thread portal.
        # The TestClient case above additionally covers ASGI dispatch.
        app = FastAPI()
        def require_account(request):
            if not request.headers.get("x-test-account"):
                raise HTTPException(401)
        install_telemetry_routes(app, require_account=require_account)
        handlers = {route.path: route.endpoint for route in app.routes}
        def request(auth=True):
            return Request({"type": "http", "method": "GET", "path": "/telemetry/api/summary",
                            "query_string": b"", "headers": [(b"x-test-account", b"fixture")] if auth else []})
        summary = handlers["/telemetry/api/summary"]
        detail = handlers["/telemetry/api/request/{request_id}"]
        with self.assertRaises(HTTPException) as caught:
            summary(request(False))
        self.assertEqual(caught.exception.status_code, 401)
        empty = json.loads(summary(request()).body)
        self.assertIsNone(empty["kpis"]["error_rate"])
        self.assertEqual(empty["telemetry"]["quality"]["status"], "insufficient")
        self.hub.record(event(self.now - 20))
        self.hub.record(event(self.now - 10, request_id="b" * 32))
        with patch.object(hub_module, "MAX_ANALYZED_EVENTS", 1):
            found = detail(request(), "b" * 32)
            missing = detail(request(), "a" * 32)
        self.assertEqual(found.status_code, 200)
        self.assertEqual(missing.status_code, 404)
        for response in (found, missing):
            q = json.loads(response.body)["telemetry"]["quality"]
            self.assertEqual(q["analysis"]["window_omitted"], 1)
            self.assertEqual(q["coverage"], "not_established")


if __name__ == "__main__":
    unittest.main()
