"""#974: the save-outcome check reads review events in a window and discloses no ids."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.telemetry.hub import doc_ref
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from tests.test_console_badge_counts_postgres_v1 import _envelope

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_review_save_outcome.py"


def _run(dsn, *args):
    env = {**os.environ, "METIS_CANONICAL_DB_DSN": dsn}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          env=env, cwd=ROOT, timeout=90)


def _seed(dsn):
    snapshot_id, account_id = "snap-0123abcd-9f9f", "acct-974"
    store = PostgresWorkflowDocumentRuntimeStore(PostgresCanonicalConfig(dsn=dsn))
    with store._connect() as con:
        con.execute(
            "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
            (account_id, "reviewer-974", "Reviewer 974", ["reviewer"], "salt", "hash"))
    store.write_bundle(envelope=_envelope(snapshot_id=snapshot_id, token="ab12", account_id=account_id,
                                          reviewer=True), objects=None)
    with store._connect() as con:
        for index, at in enumerate(("2026-11-04T09:12:10Z", "2026-11-04T09:20:00Z")):
            con.execute(
                "INSERT INTO workflow.review_events(snapshot_id,object_id,object_version,event_type,"
                "actor_account_id,occurred_at,details,event_hash) VALUES(%s,%s,'1','review_decision',%s,%s,"
                "'{\"comment\":\"private text\"}'::jsonb,%s)",
                (snapshot_id, f"object-secret-{index}", account_id, at, f"hash-974-{index}"))
    return snapshot_id


def test_reports_only_events_inside_the_window_without_ids_or_details(complete_postgres):
    snapshot_id = _seed(complete_postgres.dsn)
    result = _run(complete_postgres.dsn, "--doc-ref", doc_ref(snapshot_id),
                  "--start", "2026-11-04T09:12:03Z", "--seconds", "60")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["review_events_in_window"] == 1
    assert report["events"][0]["event_type"] == "review_decision"
    assert report["events"][0]["object_ref"].startswith("o_")
    for secret in (snapshot_id, "object-secret", "acct-974", "private text"):
        assert secret not in result.stdout


def test_unknown_document_is_reported_not_guessed(complete_postgres):
    _seed(complete_postgres.dsn)
    result = _run(complete_postgres.dsn, "--doc-ref", "d_" + "0" * 16, "--start", "2026-11-04T09:12:03Z")
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"status": "document_not_resolved", "doc_ref": "d_" + "0" * 16,
                                         "matches": 0}


def test_rejects_malformed_input_before_connecting(complete_postgres):
    assert _run(complete_postgres.dsn, "--doc-ref", "snap-x", "--start", "2026-11-04T09:12:03Z").returncode == 2
    assert _run(complete_postgres.dsn, "--doc-ref", "d_" + "0" * 16, "--start", "2026-11-04T09:12:03").returncode == 2
    assert _run(complete_postgres.dsn, "--doc-ref", "d_" + "0" * 16, "--start", "2026-11-04T09:12:03Z",
                "--seconds", "601").returncode == 2
