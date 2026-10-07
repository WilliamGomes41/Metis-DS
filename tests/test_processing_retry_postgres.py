"""Stored-source retry: native PostgreSQL failure/restart/concurrency proof.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
from datetime import timedelta
from threading import Event, Thread
import subprocess
import sys

import pytest

from src.operations_console_v1 import ConsoleError, PRE_REVIEW_BLOCKED
from src.processing_retry_v1 import KEY, now
from src.processing_evidence_export_v1 import processing_evidence_tables
from tests.test_review_batch_atomic_postgres import _console as _raw_console, _client
from tests.semantic_fixture_support import bind_fixture_selections


def _console(root, config):
    console = _raw_console(root, config)
    bind_fixture_selections(console)
    return console
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


def blocked(root, config, monkeypatch):
    console = _raw_console(root, config)
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    original = console._fragments_and_spec
    def reject(*args, **kwargs):
        error = ConsoleError("pre_review_llm_proposal_rejected", "recommendation_strength_literal_mismatch")
        error.pre_review_diagnostics = {"reference": "test-reference", "reason_code": "recommendation_strength_literal_mismatch"}
        raise error
    monkeypatch.setattr(console, "_fragments_and_spec", reject)
    receipt = console.ingest(actor_id=researcher["account_id"], filename="begrippen.html", content_type="text/html",
        data=b'<html><body><h1>Begrippen</h1><p>Een observatie is een systematische waarneming van gedrag.</p></body></html>',
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-09-20", live_url="",
        class_="richtlijn", family="begrippen", named_reviewers=[reviewer["account_id"]])
    monkeypatch.setattr(console, "_fragments_and_spec", original)
    bind_fixture_selections(console)
    return console, researcher["account_id"], receipt["snapshot_id"], reject


def test_failure_deduplication_success_http_and_restart(workflow_postgres, tmp_path, monkeypatch):
    console, actor, sid, reject = blocked(tmp_path, workflow_postgres, monkeypatch)
    before = deepcopy(console._envelope(sid))
    calls = []
    original = console._fragments_and_spec
    def failed(*args, **kwargs):
        calls.append(1)
        return reject(*args, **kwargs)
    monkeypatch.setattr(console, "_fragments_and_spec", failed)
    for _ in range(2):
        with pytest.raises(ConsoleError, match="recommendation_strength_literal_mismatch"):
            console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="failed")
    assert len(calls) == 1
    restarted = _console(tmp_path, workflow_postgres)
    envelope = restarted._envelope(sid)
    assert envelope["sha256"] == before["sha256"]
    assert envelope["publication_eligibility"] == PRE_REVIEW_BLOCKED
    assert restarted.snapshot_objects(sid) == []
    assert envelope["quality_processing_runs"] == before["quality_processing_runs"]
    attempt = envelope[KEY][-1]
    assert attempt["state"] == "failed"
    assert attempt["validation_code"] == "recommendation_strength_literal_mismatch"
    tables, _ = processing_evidence_tables(snapshot_id=sid, revision="r", envelope=envelope, objects=[])
    assert tables["processing_attempts"][0]["processing_reference"] == "test-reference"
    monkeypatch.setattr(console, "_fragments_and_spec", original)
    client = _client(restarted)
    response = client.post("/tree/reprocess", data={"snapshot_id": sid, "command_id": "success"}, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert client.post("/tree/reprocess", data={"snapshot_id": sid, "command_id": "success"}, follow_redirects=False).status_code == 303
    final = _console(tmp_path, workflow_postgres)
    assert final._envelope(sid)[KEY][-1]["state"] == "succeeded"
    assert final._envelope(sid)["quality_processing_runs"][-1]["attempt_id"] == final._envelope(sid)[KEY][-1]["attempt_id"]
    assert final.snapshot_objects(sid)
    assert final._envelope(sid)["sha256"] == before["sha256"]
    assert len(final._envelope(sid)[KEY]) == 2
    diagnostics = _client(final).get("/review/processing-diagnostics", params={"document": sid}).json()
    assert diagnostics["processing_attempts"][0]["validation_code"] == attempt["validation_code"]


def test_concurrent_duplicate_and_other_command_cannot_start_second_attempt(workflow_postgres, tmp_path, monkeypatch):
    console, actor, sid, _ = blocked(tmp_path, workflow_postgres, monkeypatch)
    second = _console(tmp_path / "other-runtime", workflow_postgres)
    started, release = Event(), Event()
    original = console._fragments_and_spec
    def slow(*args, **kwargs):
        started.set()
        assert release.wait(10)
        return original(*args, **kwargs)
    monkeypatch.setattr(console, "_fragments_and_spec", slow)
    results = []
    def work():
        try:
            results.append(console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="one"))
        except BaseException as error:
            results.append(error)
    worker = Thread(target=work)
    worker.start()
    try:
        assert started.wait(10)
        for key in ("one", "two"):
            with pytest.raises(ConsoleError, match="processing_attempt_in_progress"):
                second.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id=key)
        process = subprocess.run([sys.executable, "-c", """
from pathlib import Path
import sys
from tests.test_review_batch_atomic_postgres import _console
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.operations_console_v1 import ConsoleError
console = _console(Path(sys.argv[1]), PostgresCanonicalConfig(dsn=sys.argv[2]))
try:
    console.retry_pre_review(actor_id=sys.argv[3], snapshot_id=sys.argv[4], command_id='separate-process')
except ConsoleError as error:
    print(error.code)
""", str(tmp_path / "process-runtime"), workflow_postgres.dsn, actor, sid], capture_output=True, text=True, timeout=10)
        assert process.returncode == 0 and process.stdout.strip() == "processing_attempt_in_progress", process.stderr
    finally:
        release.set()
        worker.join(15)
    assert len(results) == 1 and isinstance(results[0], dict), results
    restarted = _console(tmp_path, workflow_postgres)
    assert len(restarted._envelope(sid)[KEY]) == 1


@pytest.mark.parametrize("mutation,code", [
    ("published", "published_objects_must_not_be_rewritten"),
    ("reviews", "pre_review_retry_existing_work"),
    ("objects", "pre_review_retry_existing_work"),
    ("unauthorized", "researcher_role_required"),
    ("invalid-key", "processing_command_id_invalid"),
])
def test_reservation_guards_do_not_change_existing_work(workflow_postgres, tmp_path, monkeypatch, mutation, code):
    console, actor, sid, _ = blocked(tmp_path, workflow_postgres, monkeypatch)
    envelope = deepcopy(console._envelope(sid))
    objects = None
    if mutation == "published":
        envelope["published"] = True
    elif mutation == "reviews":
        envelope["review_passes"] = {"existing": {"decision": "approve"}}
    elif mutation == "objects":
        objects = [{"object_id": "existing", "object_version": "1", "content": {"raw_text": "Existing work"}}]
    if mutation in {"published", "reviews", "objects"}:
        console.workflow_document_store.write_bundle(envelope=envelope, objects=objects)
    elif mutation == "unauthorized":
        actor = console.create_account(username="visitor", password="visitor-secret", roles=("publisher",))["account_id"]
    before = deepcopy(console._envelope(sid))
    before_objects = console.snapshot_objects(sid)
    with pytest.raises(ConsoleError) as error:
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="bad key" if mutation == "invalid-key" else "guard")
    assert error.value.code == code
    restarted = _console(tmp_path, workflow_postgres)
    assert restarted._envelope(sid) == before
    assert restarted.snapshot_objects(sid) == before_objects


@pytest.mark.parametrize("fault,code", [("source", "freeze_bytes_missing"), ("timeout", "processing_timeout")])
def test_source_and_timeout_failures_are_durable_without_private_prose(workflow_postgres, tmp_path, monkeypatch, fault, code):
    console, actor, sid, _ = blocked(tmp_path, workflow_postgres, monkeypatch)
    if fault == "source":
        console._source_cache_path(console._envelope(sid)).write_bytes(b"corrupt source")
    else:
        def timeout(*args, **kwargs):
            raise TimeoutError("private-provider-payload")
        monkeypatch.setattr(console, "_fragments_and_spec", timeout)
    with pytest.raises((ConsoleError, TimeoutError)):
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="failure")
    envelope = _console(tmp_path, workflow_postgres)._envelope(sid)
    assert envelope[KEY][-1]["error_code"] == code
    assert "private-provider" not in str(envelope[KEY])
    assert envelope["publication_eligibility"] == PRE_REVIEW_BLOCKED


@pytest.mark.parametrize("change", ["envelope", "revision", "permission", "published"])
def test_changes_during_provider_work_block_stale_activation(workflow_postgres, tmp_path, monkeypatch, change):
    console, actor, sid, _ = blocked(tmp_path, workflow_postgres, monkeypatch)
    second = _console(tmp_path, workflow_postgres)
    original = console._fragments_and_spec
    retained = []
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        envelope = deepcopy(second._envelope(sid))
        if change == "permission":
            account = deepcopy(second._account(actor))
            account["roles"] = ["publisher"]
            second.workflow_identity_store.update_roles(actor, account["roles"])
        else:
            if change == "published":
                envelope["published"] = True
            elif change == "envelope":
                envelope["title"] = "Concurrent correction"
            else:
                retained.append({"object_id": "concurrent-work", "object_version": "1", "content": {"raw_text": "Retained"}})
            second.workflow_document_store.write_bundle(envelope=envelope, objects=retained or None)
        return result
    monkeypatch.setattr(console, "_fragments_and_spec", changed)
    with pytest.raises(ConsoleError):
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="stale")
    restarted = _console(tmp_path, workflow_postgres)
    assert restarted.snapshot_objects(sid) == retained
    assert restarted._envelope(sid)[KEY][-1]["state"] == "failed"
    assert not any(a["state"] == "succeeded" for a in restarted._envelope(sid)[KEY])


def test_expired_worker_cannot_overwrite_recovered_success(workflow_postgres, tmp_path, monkeypatch):
    console, actor, sid, _ = blocked(tmp_path, workflow_postgres, monkeypatch)
    second = _console(tmp_path, workflow_postgres)
    original = console._fragments_and_spec
    import src.processing_retry_v1 as retry
    def superseded(*args, **kwargs):
        result = original(*args, **kwargs)
        future = now() + timedelta(hours=1)
        monkeypatch.setattr(retry, "now", lambda: future)
        second.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="recovered")
        return result
    monkeypatch.setattr(console, "_fragments_and_spec", superseded)
    with pytest.raises(ConsoleError) as error:
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="old-worker")
    assert error.value.code == "processing_attempt_not_active"
    restarted = _console(tmp_path, workflow_postgres)
    envelope = restarted._envelope(sid)
    assert [a["state"] for a in envelope[KEY]] == ["interrupted", "succeeded"]
    assert envelope["quality_processing_runs"][-1]["attempt_id"] == envelope[KEY][-1]["attempt_id"]
    assert restarted.snapshot_objects(sid)


def test_interruption_expiry_recovery_and_failed_activation_are_non_destructive(workflow_postgres, tmp_path, monkeypatch):
    console, actor, sid, _ = blocked(tmp_path, workflow_postgres, monkeypatch)
    original = console._fragments_and_spec
    def crash(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(console, "_fragments_and_spec", crash)
    with pytest.raises(KeyboardInterrupt):
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="crashed")
    restarted = _console(tmp_path, workflow_postgres)
    assert restarted._envelope(sid)[KEY][-1]["state"] == "running"
    import src.processing_retry_v1 as retry
    future = now() + timedelta(hours=1)
    monkeypatch.setattr(retry, "now", lambda: future)
    with pytest.raises(ConsoleError, match="processing_attempt_expired"):
        restarted.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="crashed")
    assert _console(tmp_path, workflow_postgres)._envelope(sid)[KEY][-1]["state"] == "interrupted"
    store = restarted.workflow_document_store
    write = store.write_bundle
    def commit_failure(**kwargs):
        result = write(**kwargs)
        if kwargs.get("objects") is not None:
            from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
            raise WorkflowDocumentStoreError("injected_commit_failure")
        return result
    monkeypatch.setattr(store, "write_bundle", commit_failure)
    with pytest.raises(ConsoleError) as failed:
        restarted.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="commit-failure")
    assert failed.value.code == "workflow_document_write_failed"
    final = _console(tmp_path, workflow_postgres)
    assert final.snapshot_objects(sid) == []
    assert final._envelope(sid)["publication_eligibility"] == PRE_REVIEW_BLOCKED
    assert final._envelope(sid)[KEY][-1]["state"] == "failed"
    assert not any(a["state"] == "succeeded" for a in final._envelope(sid)[KEY])
    monkeypatch.setattr(store, "write_bundle", write)
    restarted.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="recovered")
    assert _console(tmp_path, workflow_postgres)._envelope(sid)[KEY][-1]["state"] == "succeeded"
