"""Actual browser receipt -> explicit selection -> review on native PostgreSQL.
# release-control-evidence: scope/belofte toegang beschikbaarheid slop releasebewijs
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


@pytest.mark.skipif(not os.environ.get("METIS_BROWSER_EXECUTABLE"), reason="Browser proof runs in the required GitHub acceptance job")
def test_browser_workflow_order_receipt_selection_review_mobile(workflow_postgres, tmp_path):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, PYTHONPATH=str(root), METIS_BROWSER_BASE=base, METIS_BROWSER_OUTPUT=str(tmp_path))
    with (tmp_path/"server.log").open("w") as log:
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "tests.browser_source_selection_fixture:app",
            "--host", "127.0.0.1", "--port", str(port)], cwd=root, env=env, stdout=log, stderr=log)
        try:
            for _ in range(200):
                try:
                    with urllib.request.urlopen(base+"/browser-manifest") as response:
                        json.load(response)
                    break
                except OSError:
                    time.sleep(.1)
            else:
                pytest.fail((tmp_path/"server.log").read_text())
            subprocess.run(["node", str(root/"tests/browser_source_selection_check.cjs")], env=env, cwd=root, check=True, timeout=90)
            result = json.loads((tmp_path/"browser-result.json").read_text())
            assert result["receiptDidNotStart"] and result["reviewOpened"] and result["pageErrors"] == []
            assert result["namedReviewerEnteredReview"] and result["unassignedUploaderDirectedToTrajectory"]
            assert len(list(tmp_path.glob("*.png"))) == 5
        finally:
            server.terminate()
            server.wait(timeout=15)
