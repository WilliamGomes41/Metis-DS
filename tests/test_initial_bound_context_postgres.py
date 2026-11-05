"""#979: initial source use survives the native PostgreSQL task boundary.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: opslag recovery stale concurrent
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.vorming.source_bound_fields_v3 import MODE
from src.vorming.source_selection_v1 import summary_projection
from src.workflows.formation_task_store_v1 import FormationTaskStore
from tests.production_support import restart_production
from tests.test_recommendation_context_v3 import response_for


PARENT = "Overweeg maatregelen uit Tabel 1."
TABLE = "Houd de huid droog."
FOLLOWING = "Controleer dagelijks de huid."


@pytest.mark.parametrize("interrupt", [False, True], ids=["initial", "restart"])
def test_initial_bound_table_is_preserved_without_a_second_candidate(
    tmp_path, production_console, monkeypatch, interrupt
):
    console = production_console(root=tmp_path, processing_binder=lambda console: None)
    actor = console.create_account(
        username="source.researcher", password="fixture-password", roles=("researcher", "reviewer")
    )["account_id"]
    reviewer = console.create_account(
        username="source.reviewer", password="fixture-password", roles=("reviewer",)
    )["account_id"]
    sid = console.receive_source(
        actor_id=actor,
        filename="bound-table.html",
        content_type="text/html",
        data=(f"<html><body><h1>Advies</h1><p>{PARENT}</p>"
              f"<h1>Tabel 1</h1><p>{TABLE}</p>"
              f"<h1>Vervolg</h1><p>{FOLLOWING}</p></body></html>").encode(),
        ingest_kind="new", title="Exacte tabelcontext", version="1", date="2026-11-05",
        live_url="", class_="richtlijn", family="test", named_reviewers=[reviewer],
    )["snapshot_id"]
    monkeypatch.setenv("METIS_FORMATION_TASK_STORAGE", "v1")
    calls = []
    interrupted = []
    table_ref = {}

    def provider(_url, _headers, payload, _timeout):
        request = json.loads(payload["input"][1]["content"])
        text = request["source_blocks"][0]["text"]
        calls.append(text)
        if interrupt and text == FOLLOWING and not interrupted:
            interrupted.append(True)
            raise ConsoleError("processing_test_interrupted")
        proposal = response_for(payload, text)
        if text == PARENT:
            table = next(block for block in request["evidence_blocks"] if block["text"] == TABLE)
            table_ref.update(block_id=table["block_id"], start=0, end=len(TABLE))
            proposal["objects"][0]["context_evidence"] = [{
                "role": "support",
                "span": {"block_id": table["block_id"], "literal": TABLE, "occurrence": None},
                "unresolved_reason": None,
            }]
        return {"status": "completed", "output": [{"type": "message", "content": [{
            "type": "output_text", "text": json.dumps(proposal),
        }]}]}

    def bind(target):
        bind_pre_review_semantic_processing(target, environ={
            "METIS_PASSAGE_FORMATION_MODE": MODE,
            "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "test",
        }, post_json=provider)

    bind(console)
    attempt, _ = console.reserve_source_selection(
        actor_id=actor, snapshot_id=sid, command_id="initial-context",
        expected_revision=console.objects_revision(sid),
    )
    if interrupt:
        with pytest.raises(ConsoleError, match="processing_test_interrupted"):
            console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
        assert calls == [PARENT, FOLLOWING]
        assert console.snapshot_objects(sid) == []
        reference = console._envelope(sid)["processing_attempts"][-1]["diagnostic"]["validator_input_ref"]
        retained = FormationTaskStore(console.workflow_document_store).task_results(reference["context_id"])
        assert len(retained) == 1
        assert retained[0]["proposal"]["objects"][0]["context_evidence"][0]["span"] == table_ref
        console = restart_production(console)
        bind(console)
        attempt, _ = console.reserve_source_selection(
            actor_id=actor, snapshot_id=sid, command_id="resume-context",
            expected_revision=console.objects_revision(sid),
        )
        assert attempt["kind"] == "resume"
    console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)

    assert calls == ([PARENT, FOLLOWING, FOLLOWING] if interrupt else [PARENT, FOLLOWING])
    objects = console.snapshot_objects(sid)
    candidates = [obj for obj in objects if obj.get("proposed_object_type") == "recommendation"]
    by_text = {obj["content"]["clean_text"]: obj for obj in candidates}
    assert set(by_text) == {PARENT, FOLLOWING}
    assert [by_text[text]["metadata"]["admission"]["gate_result"] for text in (PARENT, FOLLOWING)] == ["allowed", "allowed"]
    context = by_text[PARENT]["metadata"]["source_bound_context"]["entries"]
    assert [(entry["role"], entry["span"], entry["text"]) for entry in context] == [
        ("support", table_ref, TABLE)
    ]
    assert context[0]["source_mapping"]
    assert context[0]["source_refs"]
    envelope = console._envelope(sid)
    latest = envelope["processing_attempts"][-1]
    assert latest["state"] == "succeeded"
    store = FormationTaskStore(console.workflow_document_store)
    diagnostic = store.diagnostic(latest)
    reference = latest["diagnostic"]["validator_input_ref"]
    retained = store.task_results(reference["context_id"])
    assert len(retained) == 2
    assert [len(row["proposal"]["objects"]) for row in retained] == [1, 1]
    assert len(diagnostic["task_plan"]["tasks"]) == 3
    progress = console.processing_status(sid)["formation_progress"]
    assert progress["planned_task_count"] == 3
    assert progress["terminal_task_count"] == 3, {
        "progress": progress,
        "provider_progress": (envelope.get("semantic_replay") or {}).get("provider_evidence", {}).get("formation_progress"),
        "provider_keys": sorted((envelope.get("semantic_replay") or {}).get("provider_evidence", {})),
    }
    assert progress["pending_task_count"] == 0
    execution_progress = {"planned_task_count": 3, "terminal_task_count": 2, "pending_task_count": 1}
    assert store.progress(reference["context_id"], attempt={**latest, "state": "running"}) == execution_progress
    assert store.progress(reference["context_id"], attempt={
        **latest, "attempt_id": "another-attempt-without-accounted-source", "state": "incomplete_budget",
    }) == execution_progress
    restored = restart_production(console)
    bind(restored)
    assert restored.snapshot_objects(sid) == objects
    for target in (console, restored):
        summary = next(row for row in target.source_selection_documents(actor_id=actor)
                       if row["snapshot_id"] == sid)
        card = summary_projection(target, envelope=summary, observations={})
        assert card["progress"]["planned_task_count"] == 3
        assert card["progress"]["terminal_task_count"] == 3
        assert card["progress"]["pending_task_count"] == 0
