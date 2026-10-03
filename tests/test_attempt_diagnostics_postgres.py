"""Native PostgreSQL attempt diagnostics, authorization and restart proof.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
from threading import Thread, Barrier
import json

import pytest

from src.operations_console_v1 import ConsoleError
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing, PASSAGE_FORMATION_MODE_ENV, SEMANTIC_MODE
from src.llm_provider_v1 import LLM_API_KEY_ENV, LLM_MODEL_ENV
from src.attempt_diagnostics_v1 import replay_diagnostic
from tests.test_review_batch_atomic_postgres import _console, _client
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401
from tests.test_pre_review_semantic_v1 import _response, _full_span_proposal


def bound(console, reject=True):
    def provider(_url, _headers, payload, _timeout):
        proposal = _full_span_proposal(payload, proposed_type="definition")
        if reject:
            proposal["objects"][0]["spans"][0]["end"] += 100000
        return _response(proposal)
    bind_pre_review_semantic_processing(console, environ={PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        LLM_API_KEY_ENV: "DO_NOT_STORE_SECRET", LLM_MODEL_ENV: "test"}, post_json=provider)


def ingest(console):
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer", "publisher"))
    receipt = console.ingest(actor_id=researcher["account_id"], filename="terms.html", content_type="text/html",
        data=b'<html><body><h1>Begrippen</h1><p>Een observatie is een systematische waarneming van gedrag.</p></body></html>',
        ingest_kind="new", title="Begrippen", version="1", date="2026-10-03", live_url="",
        class_="richtlijn", family="begrippen", named_reviewers=[reviewer["account_id"]])
    return receipt["snapshot_id"], researcher["account_id"], reviewer["account_id"]


def test_failed_initial_ingest_evidence_restart_http_replay_and_success_activation(workflow_postgres, tmp_path):
    console = _console(tmp_path, workflow_postgres)
    bound(console)
    sid, actor, reviewer = ingest(console)
    persisted = deepcopy(console._envelope(sid))
    attempt = persisted["processing_attempts"][-1]
    assert attempt["state"] == "failed"
    assert attempt["diagnostic"]["finding"]["reason_code"] == "semantic_span_bounds_invalid"
    assert "DO_NOT_STORE_SECRET" not in json.dumps(persisted)
    restarted = _console(tmp_path, workflow_postgres)
    assert restarted._envelope(sid) == persisted
    assert restarted.snapshot_objects(sid) == []
    assert replay_diagnostic(attempt)["reason_code"] == "semantic_span_bounds_invalid"
    client = _client(restarted)
    response = client.get("/review/processing-diagnostic-replay", params={"document": sid, "attempt_id": attempt["attempt_id"]})
    assert response.status_code == 200 and response.json()["status"] == "rejected"
    assert response.headers["cache-control"] == "no-store"
    assert restarted._envelope(sid) == persisted
    bound(restarted, reject=False)
    restarted.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="success")
    after = _console(tmp_path, workflow_postgres)
    assert after.snapshot_objects(sid)
    last = after._envelope(sid)["processing_attempts"][-1]
    assert last["state"] == "succeeded" and last["diagnostic"]["provider_evidence"]["response"]["output_text"]
    assert after._envelope(sid)["processing_attempts"][0] == attempt


def test_recovery_permission_http_restart_and_concurrent_consumption(workflow_postgres, tmp_path):
    console = _console(tmp_path, workflow_postgres)
    bound(console)
    sid, actor, reviewer = ingest(console)
    for i in range(3):
        with pytest.raises(ConsoleError):
            console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id=f"fail-{i}")
    prior = deepcopy(console._envelope(sid)["processing_attempts"])
    with pytest.raises(ConsoleError, match="publisher_role_required"):
        console.authorize_processing_recovery(actor_id=actor, snapshot_id=sid, reason="Investigate")
    client = _client(console)
    assert client.post("/tree/processing-recovery", data={"snapshot_id": sid, "reason": "Record rejected evidence"}, follow_redirects=False).status_code == 303
    restarted = _console(tmp_path, workflow_postgres)
    assert restarted.processing_status(sid)["retry_allowed"]
    with pytest.raises(ConsoleError, match="processing_recovery_already_authorized"):
        restarted.authorize_processing_recovery(actor_id=reviewer, snapshot_id=sid, reason="Again")
    barrier = Barrier(2)
    outcomes = []
    def retry(index):
        local = _console(tmp_path, workflow_postgres)
        bound(local)
        barrier.wait()
        try:
            local.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id=f"recovery-{index}")
        except ConsoleError as error:
            outcomes.append(error.code)
    workers = [Thread(target=retry, args=(i,)) for i in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=15)
        assert not worker.is_alive()
    final = _console(tmp_path, workflow_postgres)._envelope(sid)
    assert len(final["processing_attempts"]) == 5
    assert final["processing_attempts"][:4] == prior
    assert final["processing_recovery"]["consumed_by"] == final["processing_attempts"][-1]["attempt_id"]
    assert len(outcomes) == 2 and "pre_review_llm_proposal_rejected" in outcomes
    assert not _console(tmp_path, workflow_postgres).processing_status(sid)["retry_allowed"]
