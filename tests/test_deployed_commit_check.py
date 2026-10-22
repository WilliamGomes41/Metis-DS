"""Execute the real post-deploy commands against a disposable HTTP server.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import textwrap
import time
from threading import Thread

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "a" * 40
OLD = "b" * 40
CHECKER = "python scripts/verify_console_deployment.py"


@contextmanager
def health_server(responses):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            status, payload = responses[min(len(calls) - 1, len(responses) - 1)]
            payload = payload() if callable(payload) else payload
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # The deployment checker can time out or reject a large body.

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def workflow_command(environment):
    text = (ROOT / ".github/workflows" / f"deploy-{environment}.yml").read_text()
    step = text.split(f"      - name: Verify {environment} health\n", 1)[1]
    match = re.search(r"^        run: ([>|])-?\n((?:          .*\n?)+)", step, re.MULTILINE)
    assert match, "The actual health-verification run block must be tested"
    command = textwrap.dedent(match[2])
    return " ".join(command.splitlines()) if match[1] == ">" else command


def manual_command():
    text = (ROOT / "docs/AZURE_STEP9_CUTOVER_RUNBOOK.md").read_text()
    return re.search(r"```bash\n(az webapp deploy .*?)\n```", text, re.DOTALL)[1]


def run_route(route, origin, tmp_path):
    command = manual_command() if route == "manual" else workflow_command(route)
    # Substitute only the deployment address and bound startup waiting for this
    # test. The actual checked-in run command and HTTP client still execute.
    command = command.replace('https://${METIS_WEBAPP}.azurewebsites.net', origin)
    command = re.sub(r"\$\{\{ vars\.AZURE_(?:PRODUCTION|TEST)_APP_URL \}\}", origin, command)
    command = command.replace(CHECKER, f'"{sys.executable}" scripts/verify_console_deployment.py --attempts 1 --retry-delay 0')
    tools = tmp_path / "bin"
    tools.mkdir(exist_ok=True)
    az = tools / "az"
    az.write_text("#!/bin/sh\nexit 0\n")
    az.chmod(0o700)
    return subprocess.run(
        ["bash", "-e", "-c", command], cwd=ROOT, capture_output=True, text=True, timeout=10,
        env={**os.environ, "PATH": f"{tools}:{os.environ['PATH']}",
             "APP_URL": origin, "REQUESTED_SHA": EXPECTED, "METIS_MAIN_SHA": EXPECTED,
             "METIS_SUBSCRIPTION_ID": "fixture", "METIS_RESOURCE_GROUP": "fixture",
             "METIS_WEBAPP": "fixture"},
    )


@pytest.mark.parametrize("route", ["production", "test", "manual"])
@pytest.mark.parametrize("commit,accepted", [(OLD, False), (EXPECTED, True)])
def test_actual_deploy_route_checks_running_commit(route, commit, accepted, tmp_path):
    payload = {"status": "ok", "service": "operations-console", "deployed_commit": commit}
    with health_server([(200, payload)]) as (origin, calls):
        result = run_route(route, origin, tmp_path)
    assert calls == ["/health"], result.stderr
    assert (result.returncode == 0) is accepted, (
        f"{route}: HTTP 200 from an old build must not pass deployment verification; "
        f"returncode={result.returncode}"
    )


@pytest.mark.parametrize("route", ["production", "test", "manual"])
@pytest.mark.parametrize("commit,accepted", [(OLD, False), (EXPECTED, True)])
def test_deploy_route_normalizes_trailing_origin_slash(route, commit, accepted, tmp_path):
    payload = {"status": "ok", "service": "operations-console", "deployed_commit": commit}
    with health_server([(200, payload)]) as (origin, calls):
        result = run_route(route, origin + "/", tmp_path)
    assert calls == ["/health"], result.stderr
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr


def run_checker(origin, *, commit=EXPECTED, attempts=1, delay=0):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_console_deployment.py"),
         "--health-url", origin + "/health", "--expected-commit", commit,
         "--attempts", str(attempts), "--retry-delay", str(delay)],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )


VALID = {"status": "ok", "service": "operations-console", "deployed_commit": EXPECTED}


@pytest.mark.parametrize("status,payload,code", [
    (200, {**VALID, "status": "starting"}, "status_mismatch"),
    (200, {**VALID, "service": "another-service"}, "service_mismatch"),
    (200, {**VALID, "deployed_commit": "not_recorded"}, "commit_mismatch"),
    (200, {**VALID, "deployed_commit": EXPECTED[:12]}, "commit_mismatch"),
    (200, {k: v for k, v in VALID.items() if k != "deployed_commit"}, "commit_mismatch"),
    (200, {k: v for k, v in VALID.items() if k != "service"}, "service_mismatch"),
    (200, {k: v for k, v in VALID.items() if k != "status"}, "status_mismatch"),
    (200, [VALID], "invalid_json"),
    (200, b"<html>sign-in wall</html>", "invalid_json"),
    (200, b"\xff", "invalid_json"),
    (302, VALID, "unavailable"),
    (503, VALID, "unavailable"),
    (200, b"x" * 65537, "unavailable"),
])
def test_cli_rejects_nonmatching_or_unreadable_health(status, payload, code):
    with health_server([(status, payload)]) as (origin, calls):
        result = run_checker(origin)
    assert result.returncode == 1
    assert calls == ["/health"]
    assert "deployment_health_" + code in result.stdout
    assert origin not in result.stdout + result.stderr
    assert "sign-in wall" not in result.stdout + result.stderr


@pytest.mark.parametrize("first", [(200, {**VALID, "deployed_commit": OLD}), (503, VALID)])
def test_cli_retries_startup_until_exact_version(first):
    with health_server([first, (200, VALID)]) as (origin, calls):
        result = run_checker(origin, attempts=3)
    assert result.returncode == 0
    assert calls == ["/health", "/health"]
    assert result.stdout.count("deployment_verification_failed") == 1
    assert "deployment_verified commit=" + EXPECTED in result.stdout


def test_cli_exhausts_attempts_without_accepting_old_version():
    with health_server([(200, {**VALID, "deployed_commit": OLD})]) as (origin, calls):
        result = run_checker(origin, attempts=3)
    assert result.returncode == 1
    assert calls == ["/health"] * 3
    assert result.stdout.count("deployment_verification_failed") == 3


@pytest.mark.parametrize("commit", ["", EXPECTED[:7], EXPECTED.upper(), "g" * 40, "not_recorded"])
def test_cli_rejects_invalid_expected_commit_before_http(commit):
    with health_server([(200, VALID)]) as (origin, calls):
        result = run_checker(origin, commit=commit)
    assert result.returncode == 2
    assert calls == []
    assert "deployment_expected_commit_invalid" in result.stderr


@pytest.mark.parametrize("attempts,delay", [(0, 0), (61, 0), (1, -1), (1, "nan"), (1, "inf")])
def test_cli_rejects_unbounded_or_invalid_retry_configuration(attempts, delay):
    with health_server([(200, VALID)]) as (origin, calls):
        result = run_checker(origin, attempts=attempts, delay=delay)
    assert result.returncode == 2
    assert calls == []


def test_http_timeout_is_bounded():
    def delayed():
        time.sleep(12)
        return VALID

    with health_server([(200, delayed)]) as (origin, calls):
        started = time.monotonic()
        result = run_checker(origin)
        elapsed = time.monotonic() - started
    assert result.returncode == 1
    assert "deployment_health_unavailable" in result.stdout
    assert calls == ["/health"]
    assert elapsed < 11.5, f"HTTP timeout was not enforced: {elapsed}"


@pytest.mark.parametrize("url", [
    "file:///health", "https://user:password@example.test/health",
    "https://example.test/health?token=private", "https://example.test/health#private",
    "https://example.test/not-health", "https://example.test:bad/health",
])
def test_cli_rejects_invalid_health_target_without_echoing_credentials(url):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_console_deployment.py"),
         "--health-url", url, "--expected-commit", EXPECTED],
        cwd=ROOT, capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 2
    assert "deployment_health_url_invalid" in result.stderr
    assert url not in result.stdout + result.stderr
    assert "password" not in result.stdout + result.stderr


@pytest.mark.parametrize("environment,sha_source", [
    ("production", "inputs.commit_sha"), ("test", "github.sha"),
])
def test_workflow_binds_expected_commit_to_selected_release(environment, sha_source):
    text = (ROOT / ".github/workflows" / f"deploy-{environment}.yml").read_text()
    step = text.split(f"      - name: Verify {environment} health\n", 1)[1]
    assert "REQUESTED_SHA: ${{ " + sha_source + " }}" in step


def test_packaged_marker_through_real_health_endpoint_and_checker(tmp_path, monkeypatch, *, production_app, production_console):
    import uvicorn
    from src import request_diagnostics_v1 as diagnostics

    marker = tmp_path / "deployed_commit.txt"
    marker.write_text(OLD)
    monkeypatch.setattr(diagnostics, "DEPLOYED_COMMIT_MARKER", marker)
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path, runtime=tmp_path / "runtime")
    app = production_app(console)
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", lifespan="off"))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        old = run_checker(origin)
        assert old.returncode == 1 and "commit_mismatch" in old.stdout
        marker.write_text(EXPECTED)
        current = run_checker(origin)
        assert current.returncode == 0
        marker.unlink()
        missing = run_checker(origin)
        assert missing.returncode == 1 and "commit_mismatch" in missing.stdout
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
    assert not thread.is_alive()
