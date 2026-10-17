"""Execute the real post-deploy commands against a disposable HTTP server.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
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
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

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
