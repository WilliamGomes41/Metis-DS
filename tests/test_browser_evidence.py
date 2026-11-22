"""Verify the browser failure evidence beside the original test outcome."""

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


TESTS = Path(__file__).resolve().parent
PROJECT = TESTS.parent
BROWSER_ENV = os.environ.get("METIS_BROWSER_EXECUTABLE")


def run_node(script, *args, env=None):
    return subprocess.run(
        [os.environ.get("METIS_BROWSER_NODE", "node"), "-e", script, *map(str, args)],
        cwd=PROJECT, env=env, text=True, capture_output=True, timeout=60,
    )


@pytest.mark.parametrize("base,options,reason", [
    ("https://example.invalid", {}, "browser-evidence-loopback-required"),
    ("http://127.0.0.1", {"storageState": "state.json"}, "browser-evidence-storage-state-file"),
    ("http://127.0.0.1", {"recordHar": {}}, "browser-evidence-har-disabled"),
])
def test_evidence_rejects_unsafe_options_before_using_browser(base, options, reason):
    result = run_node("""
        const { withBrowserEvidence } = require('./tests/browser_evidence.cjs');
        const base = process.argv[1];
        const options = JSON.parse(process.argv[2]);
        const chromium = { launch: async () => ({
          newContext: async () => { throw Error('UNSAFE_CONTEXT_CREATED'); },
          close: async () => {},
        }) };
        if (base.includes('example.invalid')) {
          chromium.launch = async () => { throw Error('UNSAFE_BROWSER_LAUNCHED'); };
        }
        withBrowserEvidence(chromium, { base }, ({ newContext }) => newContext(options))
          .catch(error => { console.error(error.message); process.exitCode = 1; });
    """, base, json.dumps(options))
    assert result.returncode != 0
    assert reason in result.stderr


def test_projector_rejects_an_oversized_or_unrecognized_trace(tmp_path):
    raw_trace = tmp_path / "raw.zip"
    safe_trace = tmp_path / "safe.zip"
    with zipfile.ZipFile(raw_trace, "w") as archive:
        archive.writestr("trace.trace", "x" * 256)
    command = [sys.executable, str(TESTS / "browser_evidence_archive.py"), str(raw_trace), str(safe_trace)]
    oversized = subprocess.run([*command, "64"], capture_output=True, text=True)
    assert oversized.stdout.strip() == "trace-too-large"
    invalid = subprocess.run([*command, "1024"], capture_output=True, text=True)
    assert invalid.stdout.strip() == "trace-unusable"
    assert not safe_trace.exists()


@pytest.mark.skipif(not BROWSER_ENV, reason="Chromium browser verification is opt-in")
@pytest.mark.parametrize("outcome", ["pass", "assertion", "browser-error"])
def test_browser_evidence_only_exports_safe_trace_on_failure(tmp_path, outcome):
    result = run_node("""
        const assert = require('node:assert/strict');
        const http = require('node:http');
        const { chromium } = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
        const { withBrowserEvidence } = require('./tests/browser_evidence.cjs');
        const output = process.argv[1];
        const outcome = process.argv[2];
        (async () => {
          const fixture = http.createServer((request, response) => {
            response.setHeader('Set-Cookie', 'fixture-session=planted-session-value; HttpOnly');
            response.setHeader('Content-Type', 'text/html');
            response.end('<form method="POST"><input name="password"><button>Submit</button></form>');
          });
          await new Promise(resolve => fixture.listen(0, '127.0.0.1', resolve));
          const base = 'http://127.0.0.1:' + fixture.address().port;
          try {
            await withBrowserEvidence(chromium, {
              base, output, label: 'fixture', launchOptions: {
                executablePath: process.env.METIS_BROWSER_EXECUTABLE,
              },
            }, async ({ newContext }) => {
              const context = await newContext({ storageState: { cookies: [], origins: [] } }, true);
              const page = await context.newPage();
              await page.goto(base);
              await page.locator('input').fill('planted-password-value');
              await page.getByRole('button').click();
              if (outcome === 'browser-error') {
                await page.getByText('planted-error-content').click({ timeout: 150 });
              }
              assert.notEqual(outcome, 'assertion', 'original synthetic assertion');
            });
          } finally {
            fixture.close();
          }
        })().catch(error => { console.error(error.message); process.exitCode = 1; });
    """, tmp_path, outcome)
    if outcome == "pass":
        assert result.returncode == 0, result.stderr
        assert not (tmp_path / "evidence").exists()
        return

    assert result.returncode == 1, result.stderr
    expected_error = "original synthetic assertion" if outcome == "assertion" else "Timeout 150ms exceeded"
    assert expected_error in result.stderr
    trace = tmp_path / "evidence" / "fixture-1.trace.zip"
    with zipfile.ZipFile(trace) as archive:
        assert archive.namelist() == ["trace.trace"]
        content = archive.read("trace.trace")
        for marker in (
            b"planted-session-value", b"planted-password-value", b"planted-error-content",
            b"cookie", b"authorization",
        ):
            assert marker not in content.lower()
        events = [json.loads(line) for line in content.splitlines()]
    assert events[0]["type"] == "context-options"
    assert {"goto", "fill", "click"} <= {event.get("method") for event in events}
    errors = [event["error"]["message"] for event in events if "error" in event]
    assert errors == (["Browser action failed"] if outcome == "browser-error" else [])
