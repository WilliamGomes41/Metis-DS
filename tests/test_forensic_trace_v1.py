"""Forensic trace v1. The Smetten background case stays a RED baseline."""
import csv
import io
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

from src.forensic_trace_v1 import (
    UNKNOWN, compare_traces, load_evidence, load_gold, trace, write_outputs,
)
from src.processing_evidence_export_v1 import processing_evidence_tables, processing_evidence_zip


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "tests/fixtures/forensic/smetten_background_v3.json"
GOLD = ROOT / "tests/fixtures/forensic/smetten-gold.json"
QUIZ = "Om de implementatie van de richtlijn te bevorderen heeft de werkgroep vijf vragen voor de kennisquiz opgesteld."


def _graded():
    return trace(load_evidence(EVIDENCE), load_gold(GOLD))


def test_background_is_not_answer_bearing():
    """Diagnostic baseline stays RED. This test must fail if V3 is silently painted green."""
    result = _graded()
    row = result["divergences"][0]
    assert row["case_id"] == "SMETTEN-BG-QUIZ"
    assert row["verdict"] == "FAIL"
    assert row["first_divergence_stage"] == "provider_decision"
    assert row["divergence_class"] == "semantic"
    assert row["actual_provider_decision"] == "selected"
    assert row["actual_proposed_object_type"] == "explanation"
    assert row["expected_function"] == "background"
    assert row["expected_object_type"] is None
    record = next(item for item in result["records"] if item["expectation"])
    assert record["provider"]["proposed_object_type"] == "explanation"
    assert record["validation"]["validator_result"] == "accepted"
    assert record["transformation"]["object_id"] == "obj-quiz"
    assert record["admission"]["gate_result"] == "allowed"
    assert record["review_projection"]["shown_as_review_candidate"] is True
    assert record["source"]["raw_text"] == QUIZ
    assert result["summary"]["comparison"] == "compared"
    assert result["summary"]["identity"]["passage_formation_mode"] == "semantic-source-bound-v3"
    assert result["summary"]["identity"]["deployed_commit"] == "8007b11d1f662f0151551b6647280d21d0ae9603"


def test_same_trace_three_times_is_byte_identical(tmp_path):
    payloads = []
    for index in range(3):
        directory = tmp_path / str(index)
        result = _graded()
        write_outputs(result, directory)
        payloads.append((directory / "forensic_trace.jsonl").read_bytes())
        payloads.append((directory / "forensic_summary.json").read_bytes())
        payloads.append((directory / "first_divergence.csv").read_bytes())
    assert payloads[0] == payloads[3] == payloads[6]
    assert payloads[1] == payloads[4] == payloads[7]
    assert payloads[2] == payloads[5] == payloads[8]
    text = payloads[0].decode()
    assert "UNKNOWN" not in text.split("provider")[0]
    assert QUIZ in text


def test_definition_control_can_pass_without_clearing_the_background_defect():
    evidence = load_evidence(EVIDENCE)
    gold = load_gold(GOLD)
    gold["cases"].append({
        "case_id": "SMETTEN-DEF-CONTROL",
        "source_sha256": evidence["identity"]["source_sha256"],
        "source_reconstruction_hash": evidence["identity"]["source_reconstruction_hash"],
        "source_fragment_ids": ["smetten-definition"],
        "start": 0,
        "end": 83,
        "expected_source_function": "answer_bearing",
        "expected_answer_bearing": True,
        "expected_object_type": "definition",
    })
    rows = {row["case_id"]: row for row in trace(evidence, gold)["divergences"]}
    assert rows["SMETTEN-BG-QUIZ"]["verdict"] == "FAIL"
    assert rows["SMETTEN-DEF-CONTROL"]["verdict"] == "PASS"
    assert rows["SMETTEN-DEF-CONTROL"]["first_divergence_stage"] is None


def test_identity_mismatch_stops_before_content_comparison():
    gold = load_gold(GOLD)
    gold["expected_identity"]["passage_formation_mode"] = "semantic-source-bound-v4"
    result = trace(load_evidence(EVIDENCE), gold)
    assert result["summary"]["comparison"] == "TRACE_IDENTITY_MISMATCH"
    assert result["summary"]["mismatched_identity_fields"] == ["passage_formation_mode"]
    assert result["divergences"][0]["verdict"] == "TRACE_IDENTITY_MISMATCH"
    assert result["divergences"][0]["first_divergence_stage"] == "identity"
    assert result["divergences"][0]["actual_proposed_object_type"] is None
    assert all(record["first_divergence"] is None for record in result["records"])


def test_same_text_with_another_fragment_is_not_a_match():
    evidence = load_evidence(EVIDENCE)
    decoy = deepcopy(evidence["spans"][0])
    decoy["source_fragment_ids"] = ["smetten-quiz-decoy"]
    decoy["source"]["source_fragment_ids"] = ["smetten-quiz-decoy"]
    decoy["transformation"]["object_id"] = "obj-decoy"
    evidence["spans"] = [decoy]
    result = trace(evidence, load_gold(GOLD))
    assert result["divergences"][0]["verdict"] == "UNLOCATED"
    assert result["divergences"][0]["first_divergence_stage"] == "source"
    assert "obj-decoy" not in json.dumps(result["divergences"])


def test_changed_reconstruction_is_not_compared_by_text():
    gold = load_gold(GOLD)
    gold["cases"][0]["source_reconstruction_hash"] = "other-reconstruction"
    result = trace(load_evidence(EVIDENCE), gold)
    assert result["divergences"][0]["verdict"] == "INCOMPATIBLE_RECONSTRUCTION"
    assert result["divergences"][0]["actual_proposed_object_type"] is None


def test_missing_provider_evidence_stays_incomplete():
    evidence = load_evidence(EVIDENCE)
    evidence["evidence_completeness"] = "partial"
    evidence["omitted_evidence"] = ["provider"]
    evidence["spans"][0]["provider"] = {"status": "unknown"}
    result = trace(evidence, load_gold(GOLD))
    row = result["divergences"][0]
    assert row["verdict"] == "INCOMPLETE"
    assert row["first_divergence_stage"] == "provider_decision"
    assert row["actual_proposed_object_type"] is None
    assert result["summary"]["trace_evidence_status"] == "partial"
    assert result["summary"]["omitted_evidence"] == ["provider"]


def test_correct_background_assessment_passes_and_does_not_invent_an_object():
    evidence = load_evidence(EVIDENCE)
    span = evidence["spans"][0]
    span["provider"] = {
        "status": "recorded", "provider_call_id": "call-1", "selected": False,
        "proposed_object_type": None, "source_assessment_role": "background",
        "proposal_ref": "proposal.source_assessments[0]",
    }
    span["transformation"] = {
        "status": "recorded", "object_id": None, "object_version": None,
        "canonical_object_hash": None, "proposed_object_type": None,
    }
    span["source_accountability"] = {
        "status": "recorded", "source_role": "background", "passage_disposition": "excluded_with_reason",
    }
    span["review_projection"] = {
        "status": "recorded", "shown_as_review_candidate": False,
        "review_status": None, "review_decision": None,
    }
    result = trace(evidence, load_gold(GOLD))
    assert result["divergences"][0]["verdict"] == "PASS"
    assert result["divergences"][0]["actual_provider_decision"] == "not_selected"


def test_differential_reports_object_removed_without_coupling_other_text(tmp_path):
    evidence = load_evidence(EVIDENCE)
    gold = load_gold(GOLD)
    base = trace(evidence, gold)
    candidate_evidence = deepcopy(evidence)
    candidate_evidence["notes"] = "synthetic candidate recording, not a product run and not V4"
    span = candidate_evidence["spans"][0]
    span["provider"]["selected"] = False
    span["provider"]["proposed_object_type"] = None
    span["provider"]["source_assessment_role"] = "background"
    span["transformation"]["object_id"] = None
    span["transformation"]["proposed_object_type"] = None
    candidate = trace(candidate_evidence, gold)
    diff = compare_traces(base, candidate)
    quiz_id = base["divergences"][0]["source_span_id"]
    assert diff["comparison"] == "differential"
    assert quiz_id in diff["objects_removed"]
    assert quiz_id in diff["first_divergence_changed"]
    assert diff["spans_only_in_candidate"] == []
    other = deepcopy(candidate_evidence)
    other["identity"]["source_reconstruction_hash"] = "different"
    refused = compare_traces(base, trace(other, gold))
    assert refused["comparison"] == "incompatible_reconstruction"


def test_cli_writes_the_red_baseline_offline(tmp_path):
    output = tmp_path / "trace"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/trace_recorded_formation.py"),
         str(EVIDENCE), "--gold", str(GOLD), "--output", str(output)],
        check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((output / "forensic_summary.json").read_text(encoding="utf-8"))
    assert summary["verdicts"] == {"FAIL": 1}
    rows = list(csv.DictReader(io.StringIO((output / "first_divergence.csv").read_text(encoding="utf-8-sig"))))
    assert rows[0]["first_divergence_stage"] == "provider_decision"
    assert rows[0]["verdict"] == "FAIL"
    table = (output / "forensic_trace.csv").read_text(encoding="utf-8-sig")
    assert QUIZ in table
    assert "obj-quiz" in table


def test_export_projection_does_not_invent_a_missing_object_or_source_span():
    envelope = {"semantic_replay": {
        "identity": {"components": {
            "source_sha256": "abc",
            "source_blocks_hash": "reconstruction",
            "semantic_contract_version": "semantic-source-bound-v3",
        }},
        "validation": "passed",
        "proposal": {"objects": [{
            "proposed_object_type": "explanation",
            "spans": [{"block_id": "b1", "start": 0, "end": 111}],
        }], "source_assessments": [{
            "span": {"block_id": "b2", "start": 0, "end": 8},
            "role": "background",
            "reason": "historical_context",
        }]},
        "provider_evidence": {"task_policy": "bounded-formation-v1", "tasks": [{
            "task_id": "task-b1", "phase": "select", "status": "completed",
            "target_spans": [{"block_id": "b1", "start": 0, "end": 111}],
        }]},
    }}
    tables, manifest = processing_evidence_tables(
        snapshot_id="snapshot", revision="rev", envelope=envelope, objects=[])
    by_type = {row["proposed_object_type"]: row for row in tables["forensic_trace"]}
    selected = by_type["explanation"]
    assert selected["provider_decision"] == "selected"
    assert selected["task_id"] == "task-b1"
    assert selected["object_id"] == UNKNOWN
    assert selected["source_text"] == UNKNOWN
    assert selected["source_span_id"] == UNKNOWN
    assessed = by_type[None]
    assert assessed["provider_decision"] == "not_selected"
    assert assessed["source_assessment_role"] == "background"
    status = next(row for row in manifest if row["dataset"] == "forensic_trace.csv")
    assert status["availability"] == "partial"
    assert "not a new authority" in status["limitation"].lower() or "Not a source-span" in status["limitation"] or "Not approval" in status["limitation"]


def test_zip_reload_keeps_partial_status(tmp_path):
    envelope = {"semantic_replay": {
        "validation": "passed",
        "proposal": {"objects": [{"proposed_object_type": "explanation", "spans": [
            {"block_id": "b1", "start": 0, "end": 4}]}]},
        "provider_evidence": {"tasks": []},
    }, "processing_attempts": [{"attempt_id": "a1", "state": "failed", "diagnostic": {
        "omitted_evidence": ["validator_input"], "source_hash": "abc"}}]}
    payload = processing_evidence_zip(snapshot_id="snapshot", revision="rev", envelope=envelope, objects=[])
    path = tmp_path / "evidence.zip"
    path.write_bytes(payload)
    evidence = load_evidence(path)
    assert evidence["evidence_completeness"] == "partial"
    assert "validator_input" in evidence["omitted_evidence"]
    assert evidence["spans"][0]["provider"]["proposed_object_type"] == "explanation"
    assert evidence["spans"][0]["transformation"]["status"] == "unknown"


def test_module_does_not_import_workflow_or_provider_clients():
    text = (ROOT / "src/forensic_trace_v1.py").read_text(encoding="utf-8")
    for banned in ("operations_console", "psycopg", "httpx", "docling", "openai", "requests"):
        assert banned not in text


def test_recorded_zip_roundtrip_joins_one_span_and_keeps_the_provider_divergence(tmp_path):
    """The acceptance path is the real export ZIP, not the handwritten fixture."""
    left = "  - Om de implementatie van de richtlijn te bevorderen"
    right = "heeft de werkgroep vijf vragen voor de kennisquiz opgesteld. "
    exact = left + " " + right
    decoy = exact.strip()
    json_text = '{"a": 1}'
    envelope = {
        "semantic_replay": {
            "identity": {"components": {
                "snapshot_id": "snapshot",
                "source_sha256": "source-sha",
                "source_blocks_hash": "reconstruction-sha",
                "extractor_version": "parser-1",
                "reconstruction_version": "reconstruction-1",
                "semantic_contract_version": "source-bound-fields-v2",
                "prompt_hash": "prompt",
                "schema_hash": "schema",
                "model_id": "model-1",
            }},
            "validation": "passed",
            "proposal": {"objects": [{
                "proposed_object_type": "explanation",
                "spans": [{"block_id": "block-quiz", "start": 120, "end": 190}],
            }]},
            "provider_evidence": {
                "version": "semantic-provider-evidence-v1",
                "deployed_commit": "8007b11d1f662f0151551b6647280d21d0ae9603",
                "task_policy": "bounded-formation-v1",
                "response": {"id": "call-1", "status": "completed", "output_text": "{}"},
                "tasks": [{
                    "task_id": "task-wide", "phase": "initial", "status": "completed",
                    "target_spans": [{"block_id": "block-quiz", "start": 0, "end": 500}],
                }],
            },
        },
        "quality_processing_runs": [{
            "run_id": "run-1", "source_hash": "source-sha",
            "source_fragments": [
                {"fragment_id": "frag-a", "raw_text": left, "clean_text": left, "source_page": 2, "source_locator": "p2"},
                {"fragment_id": "frag-b", "raw_text": right, "clean_text": right, "source_page": 2, "source_locator": "p2"},
                {"fragment_id": "frag-decoy", "raw_text": decoy, "clean_text": decoy, "source_page": 9, "source_locator": "p9"},
                {"fragment_id": "frag-json", "raw_text": json_text, "clean_text": json_text, "source_page": 1, "source_locator": "p1"},
            ],
        }],
    }
    objects = [{
        "object_id": "obj-quiz",
        "object_version": "1",
        "object_type": "explanation",
        "proposed_object_type": "explanation",
        "content": {"clean_text": exact, "raw_text": exact},
        "metadata": {
            "semantic_passage": {
                "selection_origin": "model_proposal",
                "formation_mode": "semantic-source-bound-v3",
                "spans": [{"block_id": "block-quiz", "start": 120, "end": 190}],
                "source_mapping": [
                    {"fragment_id": "frag-a", "raw_start": 0, "raw_end": len(left), "source_page": 2},
                    {"kind": "join_separator", "text": " ", "left_fragment_id": "frag-a", "right_fragment_id": "frag-b"},
                    {"fragment_id": "frag-b", "raw_start": 0, "raw_end": len(right), "source_page": 2},
                ],
            },
            "admission": {
                "gate_result": "allowed", "reason_codes": [],
                "field_formation_mode": "semantic-source-bound-v3",
            },
            "passage_register": {"status": "selected_as_candidate"},
        },
    }]
    payload = processing_evidence_zip(snapshot_id="snapshot", revision="rev", envelope=envelope, objects=objects)
    path = tmp_path / "evidence.zip"
    path.write_bytes(payload)
    gold = {
        "gold_version": "forensic-gold-v1",
        "expected_identity": {
            "passage_formation_mode": "semantic-source-bound-v3",
            "deployed_commit": "8007b11d1f662f0151551b6647280d21d0ae9603",
        },
        "cases": [{
            "case_id": "SMETTEN-BG-QUIZ",
            "source_sha256": "source-sha",
            "source_reconstruction_hash": "reconstruction-sha",
            "fragments": [
                {"fragment_id": "frag-a", "start": 0, "end": len(left)},
                {"fragment_id": "frag-b", "start": 0, "end": len(right)},
            ],
            "exact_raw_text": exact,
            "expected_source_function": "background",
            "expected_answer_bearing": False,
            "expected_object_type": None,
        }],
    }
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps(gold), encoding="utf-8")
    output = tmp_path / "trace"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/trace_recorded_formation.py"),
         str(path), "--gold", str(gold_path), "--output", str(output)],
        check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    result = trace(load_evidence(path), gold)
    row = result["divergences"][0]
    assert row["verdict"] == "FAIL"
    assert row["first_divergence_stage"] == "provider_decision"
    assert row["divergence_class"] == "semantic"
    record = next(item for item in result["records"] if item.get("expectation"))
    assert record["source"]["raw_text"] == exact
    assert record["source"]["raw_text"].startswith("  - ")
    assert record["reconstruction"]["semantic_block_id"] == "block-quiz"
    assert record["reconstruction"]["block_start"] == 120
    assert record["formation"]["task_id"] == "task-wide"
    assert record["formation"]["link"] == "contained"
    assert record["provider"]["proposed_object_type"] == "explanation"
    assert record["validation"]["validator_result"] == "accepted"
    assert record["transformation"]["object_id"] == "obj-quiz"
    assert record["admission"]["gate_result"] == "allowed"
    assert record["review_projection"]["kind"] == "review_queue_projection"
    assert record["review_projection"]["shown_as_review_candidate"] is True
    assert record["review_projection"]["review_decision_status"] == "not_recorded"
    assert result["summary"]["identity"]["deployed_commit"] == "8007b11d1f662f0151551b6647280d21d0ae9603"
    assert result["summary"]["identity"]["passage_formation_mode"] == "semantic-source-bound-v3"
    json_span = next(item for item in result["records"] if (item.get("source") or {}).get("raw_text") == json_text)
    assert isinstance(json_span["source"]["raw_text"], str)
    assert json_span["source_span_id"] != record["source_span_id"]


def test_duplicate_span_evidence_merges_or_conflicts():
    evidence = load_evidence(EVIDENCE)
    other = deepcopy(evidence["spans"][0])
    other["provider"] = {
        "status": "recorded", "provider_call_id": "call-1", "selected": False,
        "proposed_object_type": None, "source_assessment_role": "context",
        "proposal_ref": "proposal.source_assessments[0]",
    }
    evidence["spans"].append(other)
    result = trace(evidence, load_gold(GOLD))
    assert result["summary"]["span_count"] == 2
    assert result["divergences"][0]["verdict"] == "CONFLICT"
    assert result["divergences"][0]["first_divergence_stage"] == "provider_decision"


def test_background_to_context_is_a_source_role_change():
    evidence = load_evidence(EVIDENCE)
    gold = load_gold(GOLD)
    base_evidence = deepcopy(evidence)
    span = base_evidence["spans"][0]
    span["provider"]["selected"] = False
    span["provider"]["proposed_object_type"] = None
    span["provider"]["source_assessment_role"] = "background"
    span["transformation"]["object_id"] = None
    span["transformation"]["proposed_object_type"] = None
    candidate_evidence = deepcopy(base_evidence)
    candidate_evidence["spans"][0]["provider"]["source_assessment_role"] = "context"
    diff = compare_traces(trace(base_evidence, gold), trace(candidate_evidence, gold))
    assert diff["source_role_changed"]
    assert diff["objects_removed"] == []


def test_missing_formation_mode_is_unavailable_not_a_false_mismatch():
    evidence = load_evidence(EVIDENCE)
    evidence["identity"]["passage_formation_mode"] = None
    gold = load_gold(GOLD)
    result = trace(evidence, gold)
    assert result["summary"]["comparison"] == "IDENTITY_UNAVAILABLE"
    assert result["summary"]["unavailable_identity_fields"] == ["passage_formation_mode"]
    assert result["divergences"][0]["actual_proposed_object_type"] is None

