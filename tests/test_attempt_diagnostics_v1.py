"""Rejected evidence, exact replay and finite recovery regression proof.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
from datetime import timedelta
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.attempt_diagnostics_v1 import classification, replay_diagnostic, comparable_envelope
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.processing_retry_v1 import reserve, finish, now, status
from src.pre_review_semantic_v1 import semantic_spec_from_fragments
from src.semantic_passage_v1 import semantic_source_blocks, semantic_units_from_proposal, SemanticPassageError
from src.processing_evidence_export_v1 import processing_evidence_tables
from tests.test_pre_review_semantic_v1 import _fragment, _response


def recorded_failure(code="strength"):
    fragments = [_fragment("p1", "Sterk – voor. Bespreek de behandeling.")]
    block = semantic_source_blocks(fragments)[0]
    span = {"block_id": block["block_id"], "start": 0, "end": len(block["text"])}
    proposal = {"objects": [{"spans": [span], "proposed_object_type": "recommendation",
        "recommendation_semantics": {"direction": "for", "direction_evidence": span,
             "strength": "weak", "strength_status": "explicit", "strength_evidence": span}}], "abstain_reason": None}
    if code == "bounds":
        proposal["objects"][0]["spans"] = [{**span, "end": len(block["text"])+1}]
    if code == "unknown":
        proposal["objects"][0]["spans"] = [{**span, "block_id": "missing"}]
    attempt = {"state": "running", "diagnostic": {"version": "attempt-diagnostics-v1", "checkpoints": []}}
    from src.attempt_diagnostics_v1 import checkpoint
    def capture(phase, values):
        checkpoint(attempt, phase, values)
    with pytest.raises(ConsoleError):
        semantic_spec_from_fragments(document_id="doc", title="Title", family="test", class_="richtlijn",
            fragments=fragments, content_kind="html", api_key="DO_NOT_STORE_SECRET", model="test",
            formation_context={"diagnostic_checkpoint": capture},
            post_json=lambda *_: {**_response(proposal), "reasoning": "DO_NOT_STORE_REASONING", "headers": {"Authorization": "secret"}})
    return attempt


@pytest.mark.parametrize("case,reason", [("strength", "recommendation_strength_literal_mismatch"),
    ("bounds", "semantic_span_bounds_invalid"), ("unknown", "semantic_span_unknown_block")])
def test_rejected_proposal_exact_replay_and_safe_evidence(case, reason):
    attempt = recorded_failure(case)
    before = deepcopy(attempt)
    replay = replay_diagnostic(attempt)
    assert replay["status"] == "rejected" and replay["reason_code"] == reason
    assert replay["finding"]["candidate_index"] == 0
    assert attempt == before
    encoded = json.dumps(attempt)
    assert "DO_NOT_STORE_SECRET" not in encoded and "DO_NOT_STORE_REASONING" not in encoded
    assert "Authorization" not in encoded
    if case == "strength":
        finding = replay["finding"]
        assert finding["proposed_value"] == "weak" and finding["observed_value"] == "strong"
        assert finding["reconstructed_text"] == "Sterk – voor. Bespreek de behandeling."
    else:
        assert "reconstructed_text" not in replay["finding"]
    tables, manifest = processing_evidence_tables(snapshot_id="snap", revision="r", envelope={"processing_attempts": [dict(attempt, attempt_id="pa_test")]}, objects=[])
    assert tables["attempt_diagnostics"][0]["diagnostic"] == attempt["diagnostic"]
    assert next(m for m in manifest if m["dataset"] == "attempt_diagnostics.csv")["availability"] == "recorded"


def test_replay_refuses_missing_changed_version_or_corrupted_input():
    assert replay_diagnostic({})["reason_code"] == "diagnostic_input_not_recorded"
    attempt = recorded_failure()
    attempt["diagnostic"]["validator_input"]["document_id"] = "changed"
    assert replay_diagnostic(attempt)["reason_code"] == "diagnostic_input_integrity_failed"
    attempt = recorded_failure()
    attempt["diagnostic"]["proposal"]["objects"] = []
    assert replay_diagnostic(attempt)["reason_code"] == "diagnostic_input_integrity_failed"
    attempt["diagnostic"]["validator_identity"] = {}
    assert replay_diagnostic(attempt)["reason_code"] == "diagnostic_validator_version_unavailable"


@pytest.mark.parametrize("text,direction,strength", [("Sterk – voor", "for", "strong"),
    ("Sterk-tegen", "against", "strong"), ("Zwak – voor", "for", "weak"), ("Zwak-tegen", "against", "weak")])
def test_existing_literal_labels_remain_accepted(text, direction, strength):
    fragments = [_fragment("p", text + ". Bespreek dit.")]
    block = semantic_source_blocks(fragments)[0]
    span = {"block_id": block["block_id"], "start": 0, "end": len(block["text"])}
    proposal = {"objects": [{"spans": [span], "proposed_object_type": "recommendation",
        "recommendation_semantics": {"direction": direction, "direction_evidence": span,
             "strength": strength, "strength_status": "explicit", "strength_evidence": span}}]}
    assert semantic_units_from_proposal(fragments, document_id="d", proposal=proposal)


@pytest.mark.parametrize("code,category", [
    ("semantic_span_not_candidate_selectable", "validation"), ("source_bound_context_required", "validation"),
    ("pre_review_llm_connection_timeout", "transport"), ("pre_review_llm_inactivity_timeout", "transport"),
    ("pre_review_llm_processing_timeout", "transport"), ("pre_review_llm_provider_unavailable", "transport"),
    ("pre_review_llm_response_invalid", "model_output"), ("pre_review_llm_abstained", "model_output"),
    ("pre_review_llm_output_limit_exceeded", "model_output"), ("freeze_bytes_missing", "source"),
    ("researcher_role_required", "authorization"), ("snapshot_object_write_conflict", "workflow"),
    ("processing_attempt_expired", "workflow"), ("database_write_failed", "persistence"),
    ("unrecognized_failure", "unknown")])
def test_operator_categories_keep_exact_reason(code, category):
    assert classification(code)[0] == category


def exhausted():
    envelope = {"sha256": "a"*64, "version": "1", "publication_eligibility": "blocked_pending_pre_review"}
    for i in range(4):
        attempt, _ = reserve(envelope, command_id=str(i), actor_id="a", revision="r", clock=now())
        finish(envelope, attempt["attempt_id"], state="failed", error=ConsoleError("pre_review_llm_response_invalid"))
    return envelope


def test_recovery_is_one_time_source_revision_bound_and_command_idempotent():
    envelope = exhausted()
    with pytest.raises(ConsoleError, match="processing_attempt_limit_reached"):
        reserve(envelope, command_id="next", actor_id="a", revision="r", clock=now())
    envelope["processing_recovery"] = {"authorization_id": "grant", "source_hash": envelope["sha256"], "source_version": "1", "revision": "r", "consumed_by": None}
    assert status(envelope)["retry_allowed"]
    for revision in ["changed"]:
        with pytest.raises(ConsoleError, match="processing_attempt_limit_reached"):
            reserve(envelope, command_id="next", actor_id="a", revision=revision, clock=now())
    attempt, fresh = reserve(envelope, command_id="next", actor_id="a", revision="r", clock=now())
    assert fresh and len(envelope["processing_attempts"]) == 5
    assert envelope["processing_recovery"]["consumed_by"] == attempt["attempt_id"]
    assert not reserve(envelope, command_id="next", actor_id="a", revision="r", clock=now())[1]
    finish(envelope, attempt["attempt_id"], state="failed", error=ConsoleError("pre_review_llm_response_invalid"))
    assert not status(envelope)["retry_allowed"]
    with pytest.raises(ConsoleError, match="processing_attempt_limit_reached"):
        reserve(envelope, command_id="sixth", actor_id="a", revision="r", clock=now())


def test_only_diagnostic_metadata_is_excluded_from_activation_comparison():
    envelope = exhausted()
    changed = deepcopy(envelope)
    changed["processing_attempts"][-1]["diagnostic"]["finding"] = {"reason_code": "x"}
    assert comparable_envelope(changed) == comparable_envelope(envelope)
    changed["sha256"] = "b"*64
    assert comparable_envelope(changed) != comparable_envelope(envelope)
    changed = deepcopy(envelope)
    changed["processing_attempts"][-1]["state"] = "succeeded"
    assert comparable_envelope(changed) != comparable_envelope(envelope)


def test_file_adapter_restart_replay_and_activation(tmp_path, monkeypatch):
    from tests import test_attempt_diagnostics_postgres as proof
    monkeypatch.setattr(proof, "_console", lambda root, _: OperationsConsole(root=root, source_store=root/"sources", runtime=root/"runtime"))
    proof.test_failed_initial_ingest_evidence_restart_http_replay_and_success_activation(None, tmp_path)


def test_file_adapter_recovery_http_and_concurrent_consumption(tmp_path, monkeypatch):
    from tests import test_attempt_diagnostics_postgres as proof
    monkeypatch.setattr(proof, "_console", lambda root, _: OperationsConsole(root=root, source_store=root/"sources", runtime=root/"runtime"))
    proof.test_recovery_permission_http_restart_and_concurrent_consumption(None, tmp_path)


def test_diagnostic_evidence_is_bounded_and_missing_data_is_explicit(monkeypatch):
    import src.attempt_diagnostics_v1 as diagnostics
    monkeypatch.setattr(diagnostics, "MAX_DIAGNOSTIC_BYTES", 1000)
    attempt = {}
    diagnostics.checkpoint(attempt, "request", {"provider_evidence": {"request": "x"*2000}})
    assert "provider_evidence" not in attempt["diagnostic"]
    assert attempt["diagnostic"]["omitted_evidence"] == ["provider_evidence"]
    assert "diagnostic_input_not_recorded" == diagnostics.replay_diagnostic({})["reason_code"]


def test_v2_field_failure_identifies_the_field_without_changing_validation():
    from src.source_bound_fields_v2 import FIELDS, bind_fields
    raw = {f: {"span": None, "missing_reason": "not_stated"} for f in FIELDS}
    raw["recommended_action"] = {"span": {"block_id": "b", "start": -1, "end": 2}, "missing_reason": None}
    with pytest.raises(ValueError, match="source_bound_field_bounds_invalid") as caught:
        bind_fields(raw, selected=[{"block_id": "b", "start": 0, "end": 4, "text": "Text"}], candidate_text="Text", proposed_type="recommendation")
    assert caught.value.finding["field"] == "recommended_action"
    assert caught.value.finding["evidence_ref"] == raw["recommended_action"]
    assert "reconstructed_text" not in caught.value.finding


def test_malformed_json_output_survives_before_parsing():
    from src.attempt_diagnostics_v1 import checkpoint
    attempt = {}
    with pytest.raises(ConsoleError, match="pre_review_llm_response_invalid"):
        semantic_spec_from_fragments(document_id="d", title="t", family="f", class_="richtlijn",
            fragments=[_fragment("p", "Bespreek dit.")], content_kind="html", api_key="DO_NOT_STORE_SECRET", model="test",
            formation_context={"diagnostic_checkpoint": lambda phase, values: checkpoint(attempt, phase, values)},
            post_json=lambda *_: {"output": [{"type": "message", "content": [{"type": "output_text", "text": "{invalid json"}]}]})
    assert attempt["diagnostic"]["provider_evidence"]["response"]["output_text"] == "{invalid json"
    assert replay_diagnostic(attempt)["reason_code"] == "diagnostic_input_not_recorded"


def test_expired_attempt_is_interrupted_and_late_checkpoint_is_rejected(tmp_path):
    from tests.test_attempt_diagnostics_postgres import bound, ingest
    console = OperationsConsole(root=tmp_path, source_store=tmp_path/"sources", runtime=tmp_path/"runtime")
    bound(console)
    sid, actor, reviewer = ingest(console)
    with console._reprocessing_transaction(sid):
        envelope = deepcopy(console._envelope(sid))
        attempt, _ = reserve(envelope, command_id="expired", actor_id=actor, revision=console.objects_revision(sid), clock=now()-timedelta(hours=2))
        console._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    with pytest.raises(ConsoleError, match="processing_attempt_expired"):
        console._diagnostic_writer(sid, attempt["attempt_id"])("late", {"proposal": {}})
    assert "proposal" not in console._envelope(sid)["processing_attempts"][-1]["diagnostic"]


def test_failed_diagnostic_write_stops_before_provider(tmp_path, monkeypatch):
    from tests.test_attempt_diagnostics_postgres import bound, ingest
    console = OperationsConsole(root=tmp_path, source_store=tmp_path/"sources", runtime=tmp_path/"runtime")
    bound(console)
    sid, actor, reviewer = ingest(console)
    with console._reprocessing_transaction(sid):
        envelope = deepcopy(console._envelope(sid))
        attempt, _ = reserve(envelope, command_id="write-failed", actor_id=actor, revision=console.objects_revision(sid), clock=now())
        console._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    def fail(**kwargs):
        raise RuntimeError("must not expose exception prose")
    monkeypatch.setattr(console, "_commit_prepared_store", fail)
    with pytest.raises(ConsoleError, match="processing_diagnostic_write_failed") as caught:
        console._diagnostic_writer(sid, attempt["attempt_id"])("model_request", {})
    assert "exception prose" not in str(caught.value)
