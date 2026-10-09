"""Failure diagnostics correlate attempts without changing durable review state.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import re
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from src.document_status_ui_v1 import install_document_status_ui
from src.llm_provider_v1 import LLM_API_KEY_ENV, LLM_MODEL_ENV
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, PRE_REVIEW_BLOCKED
from src.pre_review_semantic_v1 import (
    PASSAGE_FORMATION_MODE_ENV, SEMANTIC_MODE, _PROCESSING_REFERENCE,
    bind_pre_review_semantic_processing,
    semantic_spec_from_fragments,
)
from tests.test_review_batch_atomic_postgres import _console
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


def fixture_console(tmp_path, failure, config):
    console = _console(tmp_path, config)
    fragment = dict(fragment_id="p1", fragment_hash="hash-p1", raw_text="Een private-brontekst is een afgeschermde bron.",
                    clean_text="Een private-brontekst is een afgeschermde bron.", section_path=["Begrippen"],
                    source_locator={"locator_type": "web_line_range", "locator_value": "lines:1-1"})
    console._extract = lambda *_a, **_kw: [fragment]

    def provider(_url, _headers, payload, _timeout):
        if failure["kind"] == "provider":
            raise ConsoleError("pre_review_llm_provider_unavailable", "private-provider-response")
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        obj = {"spans": [{"block_id": block["block_id"], "start": 0,
                          "end": len(block["text"]) + (failure["kind"] == "bounds")}],
               "proposed_object_type": "definition", "recommendation_semantics": None}
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(
            {"objects": [obj], "abstain_reason": None})}]}]}

    bind_pre_review_semantic_processing(console, environ={PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        LLM_API_KEY_ENV: "private-api-key", LLM_MODEL_ENV: "fixture-model"}, post_json=provider)
    return console


@pytest.mark.parametrize("kind,code,reason", [
    ("bounds", "pre_review_llm_proposal_rejected", "semantic_span_bounds_invalid"),
    ("provider", "pre_review_llm_provider_unavailable", ""),
])
def test_blocked_capture_retry_diagnostics_and_restart_preserve_state(workflow_postgres, tmp_path, caplog, kind, code, reason):
    caplog.set_level(logging.INFO, logger="metis.provider")
    failure = {"kind": kind}
    console = fixture_console(tmp_path, failure, workflow_postgres)
    actor = console.create_account(username="researcher", password="researcher-secret", roles=("researcher", "reviewer"))
    other = console.create_account(username="other", password="other-secret", roles=("reviewer",))
    app = create_console_app(console)
    install_document_status_ui(app, console)
    with TestClient(app, base_url="https://testserver") as client:
        client.post("/login", data={"username": "researcher", "password": "researcher-secret"})
        response = client.post("/ingest", data={
            "ingest_kind": "new", "title": "Synthetic blocked document", "version": "1",
            "date": "2026-10-01", "class_": "richtlijn", "family": "Smetten",
            "review_mode": "single", "primary_reviewer": actor["account_id"], "command_id": "receipt-diagnostics",
        }, files={"file": ("synthetic.html", b"<p>synthetic</p>", "text/html")})
        assert response.status_code == 200, response.text
        envelope = console.list_envelopes()[0]
        sid = envelope["snapshot_id"]
        assert "Document veilig ontvangen" in response.text
        assert "Status: nog niet gestart" in response.text
        assert not console._envelope(sid).get("processing_attempts")
        started = client.post("/source-selection/start", data={"document": sid,
            "command_id": "selection-diagnostics", "expected_revision": console.objects_revision(sid)}, follow_redirects=False)
        assert started.status_code == 303
        import asyncio
        async def wait():
            await asyncio.gather(*tuple(app.state.source_selection_workers))
        client.portal.call(wait)
        response = client.get("/source-selection", params={"document": sid})
        assert "Status: mislukt" in response.text
        envelope = console._envelope(sid)
        assert code not in response.text
        assert envelope["publication_eligibility"] == PRE_REVIEW_BLOCKED
        assert envelope["processing_blocker"] == code
        assert console.snapshot_objects(sid) == []
        assert console.waiting_task_counts(actor["account_id"])["review"] == 0
        assert console.document_status(sid) == "blocked"
        before = deepcopy(envelope)
        before_revision = console.objects_revision(sid)
        before_bindings = deepcopy(console.object_review_bindings(sid))

        from tests.test_pre_review_blocked_list_status_v1 import _ListStatusReader
        reader = _ListStatusReader({sid: {**envelope, "has_open_review": False}})
        console.list_document_lifecycle_statuses = reader.list_document_lifecycle_statuses
        tree = client.get("/tree")
        assert "status <b>geblokkeerd</b>" in tree.text
        assert "Technische diagnose bekijken" not in tree.text
        management = client.get(f"/settings/technical/processing?document={sid}")
        assert management.status_code == 200
        assert code in management.text
        payload = client.get(f"/review/processing-diagnostics?document={sid}").json()
        assert payload["diagnostics"]["blocked_candidate_count"] == 0
        assert payload["pre_review"]["blocked"] is True
        assert payload["pre_review"]["reason_code"] == code
        assert payload["pre_review"]["object_count"] == 0
        assert "Nul kandidaten betekent niet" in payload["pre_review"]["note"]

        response = client.post("/tree/reprocess", data={"snapshot_id": sid}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/source-selection?document={sid}"
        assert console._envelope(sid) == before
        started = client.post("/source-selection/start", data={"document": sid,
            "command_id": "retry-diagnostics", "expected_revision": console.objects_revision(sid)}, follow_redirects=False)
        assert started.status_code == 303
        client.portal.call(wait)
        response = client.get("/source-selection", params={"document": sid})
        assert response.status_code == 200 and "Status: mislukt" in response.text
        reference = console._envelope(sid)["processing_attempts"][-1]["processing_reference"]
        assert re.fullmatch(r"[a-f0-9]{32}", reference)
        assert "Verwerkingsreferentie:" not in response.text
        assert "Validatiereden:" not in response.text
        management = client.get(f"/settings/technical/processing?document={sid}")
        assert management.status_code == 200
        if reason:
            assert reason in management.text
        assert any(f"reference={reference} snapshot_id={sid} code={code} reason={reason or '-'}" in row.message
                   for row in caplog.records)
        attempts = [row.message for row in caplog.records if "METIS_PRE_REVIEW blocked" in row.message]
        assert len(attempts) == 2
        assert len(set(re.findall(r"reference=([a-f0-9]{32})", "\n".join(attempts)))) == 2
        assert "private-" not in caplog.text and "private-" not in response.text
        assert _PROCESSING_REFERENCE.get() == "-"

        after_failure = deepcopy(console._envelope(sid))
        attempts = after_failure.pop("processing_attempts")
        assert attempts[-1]["state"] == "failed"
        old = deepcopy(before)
        assert attempts[:-1] == old.pop("processing_attempts")
        previous_runs = old.pop("quality_processing_runs")
        current_runs = after_failure.pop("quality_processing_runs")
        assert current_runs[:len(previous_runs)] == previous_runs
        assert len(current_runs) == len(previous_runs) + 1
        assert after_failure == old
        assert console.objects_revision(sid) == before_revision
        assert console.object_review_bindings(sid) == before_bindings

        client.post("/login", data={"username": "other", "password": "other-secret"})
        assert "Technische diagnose bekijken" not in client.get("/tree").text
        assert client.get(f"/review/processing-diagnostics?document={sid}").status_code == 400
        client.post("/logout")
        assert client.get(f"/review/processing-diagnostics?document={sid}").status_code == 401

        restarted = fixture_console(tmp_path, failure, workflow_postgres)
        assert restarted._envelope(sid)["processing_attempts"][-1]["processing_reference"] == reference
        failure["kind"] = "valid"
        recovered = restarted.reextract_unpublished(actor_id=actor["account_id"], snapshot_id=sid)
        assert recovered["snapshot_id"] == sid and recovered["sha256"] == before["sha256"]
        assert "processing_blocker" not in recovered
        assert recovered["publication_eligibility"] != PRE_REVIEW_BLOCKED
        assert len(recovered["quality_processing_runs"]) == 3  # both failed explicit selections retain evidence
        assert [attempt["state"] for attempt in recovered["processing_attempts"]] == ["failed", "failed", "succeeded"]
        assert restarted.waiting_task_counts(actor["account_id"])["review"] == 1
        assert _PROCESSING_REFERENCE.get() == "-"
        with TestClient(create_console_app(restarted), base_url="https://testserver") as recovered_client:
            recovered_client.post("/login", data={"username": "researcher", "password": "researcher-secret"})
            diagnostic = recovered_client.get(f"/review/processing-diagnostics?document={sid}").json()["pre_review"]
            assert diagnostic["blocked"] is False and diagnostic["reason_code"] is None
            assert diagnostic["object_count"] > 0


def test_concurrent_failures_keep_distinct_safe_references_and_reset_context(caplog):
    from tests.test_pre_review_semantic_v1 import _fragment
    barrier = Barrier(2)

    def attempt(snapshot_id):
        seen = []

        def unavailable(*_args):
            seen.append(_PROCESSING_REFERENCE.get())
            barrier.wait(timeout=5)
            assert _PROCESSING_REFERENCE.get() == seen[0]
            raise ConsoleError("pre_review_llm_provider_unavailable", "private-provider-detail")

        with pytest.raises(ConsoleError) as error:
            semantic_spec_from_fragments(document_id="private-document-title", title="Private title", family="test",
                class_="richtlijn", content_kind="html", fragments=[_fragment("p1", "Bespreek private-brontekst.")],
                api_key="private-api-key", model="fixture", formation_context={"snapshot_id": snapshot_id},
                post_json=unavailable)
        assert error.value.pre_review_diagnostics == {"reference": seen[0], "reason_code": ""}
        assert _PROCESSING_REFERENCE.get() == "-"
        return seen[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(pool.map(attempt, ["snap-one", "snap-two\nprivate-injected-log"]))
    assert refs[0] != refs[1]
    assert f"reference={refs[0]} snapshot_id=snap-one" in caplog.text
    assert f"reference={refs[1]} snapshot_id=-" in caplog.text
    assert "private-" not in caplog.text
