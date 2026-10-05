"""Forensic trace v1. The Smetten background case stays a RED baseline."""
import csv
import io
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

from src.forensic_trace_v1 import (
    UNKNOWN, compare_traces, current_reconstruction_identity, load_evidence, load_gold, trace, write_outputs,
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
    assert selected["object_id"] in ("", None)
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
    assert evidence["spans"][0]["transformation"]["object_id"] is None


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


def _source_case(text, fragment_id):
    from src.semantic_passage_v1 import semantic_source_blocks
    fragment = {
        "fragment_id": fragment_id, "raw_text": text, "clean_text": text, "source_page": 1,
    }
    block = semantic_source_blocks([fragment])[0]
    return fragment, block


def _zip_trace(tmp_path, envelope, objects, gold):
    payload = processing_evidence_zip(snapshot_id="snapshot", revision="rev", envelope=envelope, objects=objects)
    path = tmp_path / "evidence.zip"
    path.write_bytes(payload)
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps(gold), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/trace_recorded_formation.py"),
         str(path), "--gold", str(gold_path), "--output", str(tmp_path / "trace")],
        check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    return trace(load_evidence(path), gold)


def test_background_assessment_without_object_is_a_source_span(tmp_path):
    text = "Dit is achtergrond en geen aanbeveling."
    fragment, block = _source_case(text, "frag-bg")
    derived = current_reconstruction_identity([fragment])
    envelope = {
        "semantic_replay": {
            "identity": {"components": {
                "snapshot_id": "snapshot", "source_sha256": "source-sha",
                "source_blocks_hash": derived["source_blocks_hash"],
                "reconstruction_version": derived["reconstruction_version"],
            }},
            "validation": "passed",
            "proposal": {"objects": [], "source_assessments": [{
                "span": {"block_id": block["block_id"], "start": 0, "end": len(block["text"])},
                "role": "background", "reason": "historical_context",
            }]},
            "provider_evidence": {
                "version": "semantic-provider-evidence-v1",
                "task_policy": "bounded-formation-v1",
                "response": {"id": "call-bg", "status": "completed", "output_text": "{}"},
                "tasks": [{"task_id": "task-bg", "phase": "initial", "status": "completed",
                           "target_spans": [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}]}],
            },
        },
        "quality_processing_runs": [{
            "run_id": "run-bg", "source_hash": "source-sha",
            "semantic_identity": {"passage_formation_mode": "semantic-source-bound-v3"},
            "source_fragments": [fragment],
        }],
    }
    gold = {
        "gold_version": "forensic-gold-v1",
        "expected_identity": {"passage_formation_mode": "semantic-source-bound-v3"},
        "cases": [{
            "case_id": "BG-NO-OBJECT",
            "source_sha256": "source-sha",
            "source_reconstruction_hash": derived["source_blocks_hash"],
            "fragments": [{"fragment_id": "frag-bg", "start": 0, "end": len(text)}],
            "exact_raw_text": text,
            "expected_source_function": "background",
            "expected_answer_bearing": False,
            "expected_object_type": None,
        }],
    }
    result = _zip_trace(tmp_path, envelope, [], gold)
    row = result["divergences"][0]
    assert row["verdict"] == "PASS"
    assert row["first_divergence_stage"] is None
    record = next(item for item in result["records"] if item.get("expectation"))
    assert record["source_span_id"] not in (None, UNKNOWN)
    assert record["source"]["status"] == "recorded"
    assert record["source"]["raw_text"] == text
    assert record["reconstruction"]["status"] == "recorded"
    assert record["formation"]["status"] == "recorded"
    assert record["provider"]["selected"] is False
    assert record["provider"]["source_assessment_role"] == "background"
    assert record["transformation"]["object_id"] is None


def test_rejected_provider_proposal_stays_on_the_source_span(tmp_path):
    text = "Dit is achtergrond en geen aanbeveling."
    fragment, block = _source_case(text, "frag-bg")
    derived = current_reconstruction_identity([fragment])
    span = {"block_id": block["block_id"], "start": 0, "end": len(block["text"])}
    envelope = {
        "semantic_replay": {
            "identity": {"components": {
                "snapshot_id": "snapshot", "source_sha256": "source-sha",
                "source_blocks_hash": derived["source_blocks_hash"],
                "reconstruction_version": derived["reconstruction_version"],
            }},
            "validation": "passed",
            "proposal": {"objects": [], "source_assessments": []},
            "provider_evidence": {
                "version": "semantic-provider-evidence-v1",
                "task_policy": "bounded-formation-v1",
                "response": {"id": "call-rej", "status": "completed", "output_text": "{}"},
                "tasks": [{"task_id": "task-bg", "phase": "initial", "status": "completed",
                           "target_spans": [span]}],
                "formation": {"rejections": [{
                    "kind": "object", "index": 0, "reason_code": "semantic_evidence_literal_not_found",
                    "proposed_object_type": "explanation", "spans": [span],
                }]},
            },
        },
        "quality_processing_runs": [{
            "run_id": "run-rej", "source_hash": "source-sha",
            "semantic_identity": {"passage_formation_mode": "semantic-source-bound-v3"},
            "source_fragments": [fragment],
        }],
    }
    gold = {
        "gold_version": "forensic-gold-v1",
        "expected_identity": {"passage_formation_mode": "semantic-source-bound-v3"},
        "cases": [{
            "case_id": "BG-REJECTED-EXPLANATION",
            "source_sha256": "source-sha",
            "source_reconstruction_hash": derived["source_blocks_hash"],
            "fragments": [{"fragment_id": "frag-bg", "start": 0, "end": len(text)}],
            "exact_raw_text": text,
            "expected_source_function": "background",
            "expected_answer_bearing": False,
            "expected_object_type": None,
        }],
    }
    result = _zip_trace(tmp_path, envelope, [], gold)
    row = result["divergences"][0]
    assert row["verdict"] == "FAIL"
    assert row["first_divergence_stage"] == "provider_decision"
    record = next(item for item in result["records"]
                  if (item.get("provider") or {}).get("proposed_object_type") == "explanation")
    assert record["source_span_id"] not in (None, UNKNOWN)
    assert record["validation"]["validator_result"] == "rejected"
    assert record["validation"]["reason_code"] == "semantic_evidence_literal_not_found"
    assert record["transformation"]["object_id"] is None


def test_multi_span_object_keeps_separate_source_identities(tmp_path):
    from src.forensic_trace_v1 import source_span_id
    left = "Eerste zin van de passage."
    right = "Tweede zin van de passage."
    frag_a, block_a = _source_case(left, "frag-a")
    frag_b, block_b = _source_case(right, "frag-b")
    derived = current_reconstruction_identity([frag_a, frag_b])
    envelope = {
        "semantic_replay": {
            "identity": {"components": {
                "snapshot_id": "snapshot", "source_sha256": "source-sha",
                "source_blocks_hash": derived["source_blocks_hash"],
                "reconstruction_version": derived["reconstruction_version"],
            }},
            "validation": "passed",
            "proposal": {"objects": [{
                "proposed_object_type": "explanation",
                "spans": [
                    {"block_id": block_a["block_id"], "start": 0, "end": len(block_a["text"])},
                    {"block_id": block_b["block_id"], "start": 0, "end": len(block_b["text"])},
                ],
            }]},
            "provider_evidence": {"tasks": [], "task_policy": "bounded-formation-v1"},
        },
        "quality_processing_runs": [{
            "run_id": "run-multi", "source_hash": "source-sha",
            "semantic_identity": {"passage_formation_mode": "semantic-source-bound-v3"},
            "source_fragments": [frag_a, frag_b],
        }],
    }
    objects = [{
        "object_id": "obj-both",
        "object_version": "1",
        "object_type": "explanation",
        "proposed_object_type": "explanation",
        "content": {"clean_text": left + " " + right, "raw_text": left + " " + right},
        "metadata": {
            "semantic_passage": {
                "selection_origin": "model_proposal",
                "formation_mode": "semantic-source-bound-v3",
                "spans": [
                    {"block_id": block_a["block_id"], "start": 0, "end": len(block_a["text"])},
                    {"block_id": block_b["block_id"], "start": 0, "end": len(block_b["text"])},
                ],
                "source_mapping": [
                    {"fragment_id": "frag-a", "raw_start": 0, "raw_end": len(left)},
                    {"fragment_id": "frag-b", "raw_start": 0, "raw_end": len(right)},
                ],
            },
            "admission": {"gate_result": "allowed", "reason_codes": []},
            "passage_register": {"status": "selected_as_candidate"},
        },
    }]
    payload = processing_evidence_zip(snapshot_id="snapshot", revision="rev", envelope=envelope, objects=objects)
    path = tmp_path / "multi.zip"
    path.write_bytes(payload)
    evidence = load_evidence(path)
    located = [row for row in trace(evidence)["records"] if row.get("source_span_id")]
    identities = {row["source_span_id"] for row in located}
    assert len(identities) == 2
    texts = {row["source"]["raw_text"] for row in located}
    assert texts == {left, right}
    assert all(row["source"].get("status") != "conflict" for row in located)
    assert all(row["reconstruction"].get("status") != "conflict" for row in located)
    assert source_span_id(
        source_sha256="source-sha", source_reconstruction_hash=derived["source_blocks_hash"],
        fragments=[{"fragment_id": "frag-a", "start": 0, "end": len(left)}],
        block_id=block_a["block_id"], block_start=0, block_end=len(block_a["text"]),
    ) in identities


def test_changed_reconstruction_identity_does_not_link_a_derived_block_map(tmp_path):
    text = "Dit is achtergrond en geen aanbeveling."
    fragment, block = _source_case(text, "frag-bg")
    envelope = {
        "semantic_replay": {
            "identity": {"components": {
                "snapshot_id": "snapshot", "source_sha256": "source-sha",
                "source_blocks_hash": "H",
                "reconstruction_version": "source-reconstruction-v0",
            }},
            "validation": "passed",
            "proposal": {"objects": [], "source_assessments": [{
                "span": {"block_id": block["block_id"], "start": 0, "end": len(block["text"])},
                "role": "background", "reason": "historical_context",
            }]},
            "provider_evidence": {
                "version": "semantic-provider-evidence-v1",
                "task_policy": "bounded-formation-v1",
                "response": {"id": "call-bg", "status": "completed", "output_text": "{}"},
                "tasks": [{"task_id": "task-bg", "phase": "initial", "status": "completed",
                           "target_spans": [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}]}],
            },
        },
        "quality_processing_runs": [{
            "run_id": "run-old", "source_hash": "source-sha",
            "semantic_identity": {"passage_formation_mode": "semantic-source-bound-v3"},
            "source_fragments": [fragment],
        }],
    }
    gold = {
        "gold_version": "forensic-gold-v1",
        "expected_identity": {"passage_formation_mode": "semantic-source-bound-v3"},
        "cases": [{
            "case_id": "BG-OLD-RECONSTRUCTION",
            "source_sha256": "source-sha",
            "source_reconstruction_hash": "H",
            "fragments": [{"fragment_id": "frag-bg", "start": 0, "end": len(text)}],
            "exact_raw_text": text,
            "expected_source_function": "background",
            "expected_answer_bearing": False,
            "expected_object_type": None,
        }],
    }
    tables, _manifest = processing_evidence_tables(
        snapshot_id="snapshot", revision="rev", envelope=envelope, objects=[])
    assert any(row.get("provenance") == "RECONSTRUCTION_IDENTITY_MISMATCH" for row in tables["source_blocks"])
    assert all(row.get("provenance") != "verified_derived" for row in tables["source_blocks"])
    result = _zip_trace(tmp_path, envelope, [], gold)
    evidence = load_evidence(tmp_path / "evidence.zip")
    assert evidence["reconstruction_provenance"]["status"] == "RECONSTRUCTION_IDENTITY_MISMATCH"
    assert not any(
        span.get("fragments") and (span.get("reconstruction") or {}).get("status") == "recorded"
        for span in evidence["spans"])
    assert result["summary"]["comparison"] == "RECONSTRUCTION_IDENTITY_MISMATCH"
    assert result["divergences"][0]["verdict"] == "RECONSTRUCTION_IDENTITY_MISMATCH"
    assert result["divergences"][0]["first_divergence_stage"] == "reconstruction"


def test_recovery_task_is_current_and_not_a_formation_conflict(tmp_path):
    from src.forensic_trace_v1 import _attach_formation
    span = {"block_id": "b1", "start": 0, "end": 8}
    envelope = {"semantic_replay": {
        "validation": "passed",
        "proposal": {"objects": [], "source_assessments": [{
            "span": span, "role": "background", "reason": "historical_context",
        }]},
        "provider_evidence": {"task_policy": "bounded-formation-v1", "tasks": [
            {"task_id": "task-initial", "phase": "initial", "status": "failed", "target_spans": [span]},
            {"task_id": "task-recovery", "phase": "recovery", "status": "completed", "target_spans": [span]},
        ]},
    }}
    payload = processing_evidence_zip(snapshot_id="snapshot", revision="rev", envelope=envelope, objects=[])
    path = tmp_path / "recovery.zip"
    path.write_bytes(payload)
    evidence = load_evidence(path)
    formed = next(row["formation"] for row in evidence["spans"] if (row.get("formation") or {}).get("task_id") == "task-recovery")
    assert formed["status"] == "recorded"
    assert formed["phase"] == "recovery"
    assert formed["history"][0]["task_id"] == "task-initial"
    conflict = {"reconstruction": {"status": "recorded", "semantic_block_id": "b1", "block_start": 0, "block_end": 8}}
    _attach_formation(conflict, [
        {"task_id": "a", "phase": "initial", "status": "completed", "target_spans": [span]},
        {"task_id": "c", "phase": "initial", "status": "completed", "target_spans": [span]},
    ], "bounded-formation-v1")
    assert conflict["formation"]["status"] == "conflict"


def test_recovered_rejection_does_not_conflict_with_the_validated_proposal(tmp_path):
    span = {"block_id": "b1", "start": 0, "end": 8}
    envelope = {"semantic_replay": {
        "validation": "passed",
        "proposal": {"objects": [{
            "proposed_object_type": "explanation", "spans": [span],
        }], "source_assessments": []},
        "provider_evidence": {"task_policy": "bounded-formation-v1", "tasks": [], "formation": {"rejections": [{
            "kind": "object", "reason_code": "semantic_evidence_literal_not_found",
            "proposed_object_type": "definition", "spans": [span],
        }]}},
    }}
    payload = processing_evidence_zip(snapshot_id="snapshot", revision="rev", envelope=envelope, objects=[])
    path = tmp_path / "recovered.zip"
    path.write_bytes(payload)
    evidence = load_evidence(path)
    provider = next(row["provider"] for row in evidence["spans"] if (row.get("provider") or {}).get("proposed_object_type") == "explanation")
    assert provider["status"] == "recorded"
    assert provider["selected"] is True
    assert provider["historical_rejections"][0]["state"] == "historical"
    assert provider["status"] != "conflict"


def test_trace_uses_only_the_producing_run(tmp_path):
    active = "Actieve replayzin over smetten."
    fragment, block = _source_case(active, "frag-active")
    derived = current_reconstruction_identity([fragment])
    identity = {
        "version": "semantic-replay-v1.0.0",
        "hash": "replay-hash",
        "components": {
            "snapshot_id": "snapshot",
            "source_sha256": "source-sha",
            "source_blocks_hash": derived["source_blocks_hash"],
            "reconstruction_version": derived["reconstruction_version"],
            "passage_formation_mode": "semantic-source-bound-v3",
        },
    }
    span = {"block_id": block["block_id"], "start": 0, "end": len(block["text"])}
    envelope = {
        "semantic_replay": {
            "identity": identity,
            "validation": "passed",
            "proposal": {"objects": [], "source_assessments": [{
                "span": span, "role": "background", "reason": "historical_context",
            }]},
            "provider_evidence": {
                "task_policy": "bounded-formation-v1",
                "tasks": [{"task_id": "task-active", "phase": "initial", "status": "completed", "target_spans": [span]}],
            },
        },
        "quality_processing_runs": [
            {
                "run_id": "run-old", "source_hash": "old-sha", "attempt_id": "attempt-1",
                "semantic_identity": {"version": "old", "hash": "old", "components": {
                    "reconstruction_version": "source-reconstruction-v0", "source_blocks_hash": "H",
                }},
                "source_fragments": [{"fragment_id": "frag-old", "raw_text": "Oude reconstructie.", "clean_text": "Oude reconstructie."}],
            },
            {
                "run_id": "run-active", "source_hash": "source-sha", "attempt_id": "attempt-3",
                "semantic_identity": identity,
                "source_fragments": [fragment],
            },
        ],
        "processing_attempts": [
            {"attempt_id": "attempt-1", "state": "failed", "diagnostic": {"omitted_evidence": []}},
            {"attempt_id": "attempt-3", "state": "succeeded", "diagnostic": {}},
        ],
    }
    gold = {
        "gold_version": "forensic-gold-v1",
        "expected_identity": {
            "passage_formation_mode": "semantic-source-bound-v3",
            "attempt_id": "attempt-3",
        },
        "cases": [{
            "case_id": "ACTIVE-RUN",
            "source_sha256": "source-sha",
            "source_reconstruction_hash": derived["source_blocks_hash"],
            "fragments": [{"fragment_id": "frag-active", "start": 0, "end": len(active)}],
            "exact_raw_text": active,
            "expected_source_function": "background",
            "expected_answer_bearing": False,
            "expected_object_type": None,
        }],
    }
    result = _zip_trace(tmp_path, envelope, [], gold)
    evidence = load_evidence(tmp_path / "evidence.zip")
    assert evidence["reconstruction_provenance"]["status"] != "RECONSTRUCTION_IDENTITY_MISMATCH"
    assert evidence["identity"]["attempt_id"] == "attempt-3"
    assert result["summary"]["comparison"] == "compared"
    assert result["divergences"][0]["verdict"] == "PASS"
    texts = [row.get("source", {}).get("raw_text") for row in evidence["spans"]]
    assert active in texts
    assert "Oude reconstructie." not in texts


def test_formula_apostrophe_roundtrips_exactly(tmp_path):
    envelope = {"semantic_replay": {"proposal": {"objects": []}}, "quality_processing_runs": [{
        "run_id": "run-text",
        "source_fragments": [
            {"fragment_id": "plain", "raw_text": "=SUM(1)", "clean_text": "=SUM(1)"},
            {"fragment_id": "quoted", "raw_text": "'=SUM(1)", "clean_text": "'=SUM(1)"},
        ],
    }]}
    payload = processing_evidence_zip(snapshot_id="snapshot", revision="rev", envelope=envelope, objects=[])
    path = tmp_path / "formula.zip"
    path.write_bytes(payload)
    evidence = load_evidence(path)
    texts = {row["source"].get("raw_text") for row in evidence["spans"]}
    assert "=SUM(1)" in texts
    assert "'=SUM(1)" in texts






def test_recorded_run_retains_reconstruction_hash_inputs():
    from src.quality_evidence_v1 import record_processing

    fragment = {
        "fragment_id": "frag-section",
        "fragment_hash": "hash-section",
        "raw_text": "Achtergrondinformatie.",
        "clean_text": "Achtergrondinformatie.",
        "source_page": 1,
        "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:1-1"},
        "section_path": ["Achtergrond"],
        "heading": "Achtergrond",
        "parser_version": "fixture-parser",
    }
    derived = current_reconstruction_identity([fragment])
    identity = {
        "version": "semantic-replay-v1.0.0",
        "hash": "fixture-replay",
        "components": {
            "snapshot_id": "snapshot",
            "source_sha256": "source-sha",
            "source_blocks_hash": derived["source_blocks_hash"],
            "reconstruction_version": derived["reconstruction_version"],
        },
    }
    envelope = {"sha256": "source-sha"}
    record_processing(
        envelope, [], fragments=[fragment],
        replay={"identity": identity, "semantic_execution": "inference"},
        started_at="2026-10-06T00:00:00+00:00",
    )
    stored = envelope["quality_processing_runs"][0]["source_fragments"][0]
    assert stored["section_path"] == ["Achtergrond"]
    assert stored["heading"] == "Achtergrond"
    envelope["semantic_replay"] = {
        "identity": identity,
        "validation": "passed",
        "proposal": {"objects": [], "source_assessments": []},
        "provider_evidence": {"tasks": [], "task_policy": "bounded-formation-v1"},
    }
    tables, _manifest = processing_evidence_tables(
        snapshot_id="snapshot", revision="rev", envelope=envelope, objects=[])
    assert tables["source_blocks"]
    assert all(row.get("provenance") == "verified_derived" for row in tables["source_blocks"])


def test_normalized_whitespace_assessment_maps_back_to_exact_raw_source(tmp_path):
    from src.semantic_passage_v1 import semantic_source_blocks
    from src.source_layout_v1 import text_view

    raw = "Achtergrond.\n   Meer context."
    view = text_view(raw, [])
    fragment = {
        "fragment_id": "frag-layout",
        "fragment_hash": "hash-layout",
        "raw_text": raw,
        "clean_text": view["text"],
        "source_text_view": view,
        "source_page": 1,
    }
    block = semantic_source_blocks([fragment])[0]
    derived = current_reconstruction_identity([fragment])
    identity = {
        "version": "semantic-replay-v1.0.0",
        "hash": "layout-replay",
        "components": {
            "snapshot_id": "snapshot",
            "source_sha256": "source-sha",
            "source_blocks_hash": derived["source_blocks_hash"],
            "reconstruction_version": derived["reconstruction_version"],
        },
    }
    span = {"block_id": block["block_id"], "start": 0, "end": len(block["text"])}
    envelope = {
        "semantic_replay": {
            "identity": identity,
            "validation": "passed",
            "proposal": {"objects": [], "source_assessments": [{
                "span": span, "role": "background", "reason": "historical_context",
            }]},
            "provider_evidence": {
                "task_policy": "bounded-formation-v1",
                "tasks": [{"task_id": "layout-task", "phase": "initial", "status": "completed",
                           "target_spans": [span]}],
            },
        },
        "quality_processing_runs": [{
            "run_id": "run-layout",
            "source_hash": "source-sha",
            "semantic_identity": identity,
            "source_fragments": [fragment],
        }],
    }
    gold = {
        "gold_version": "forensic-gold-v1",
        "expected_identity": {},
        "cases": [{
            "case_id": "RAW-WHITESPACE",
            "source_sha256": "source-sha",
            "source_reconstruction_hash": derived["source_blocks_hash"],
            "fragments": [{"fragment_id": "frag-layout", "start": 0, "end": len(raw)}],
            "exact_raw_text": raw,
            "expected_source_function": "background",
            "expected_answer_bearing": False,
            "expected_object_type": None,
        }],
    }
    result = _zip_trace(tmp_path, envelope, [], gold)
    assert result["divergences"][0]["verdict"] == "PASS"
    record = next(row for row in result["records"] if row.get("expectation"))
    assert record["source"]["raw_text"] == raw


def test_source_span_identity_includes_reconstructed_bounds():
    from src.forensic_trace_v1 import source_span_id

    kwargs = {
        "source_sha256": "source-sha",
        "source_reconstruction_hash": "reconstruction-sha",
        "fragments": [{"fragment_id": "frag-a", "start": 0, "end": 3}],
        "block_id": "semblock-a",
        "block_start": 0,
    }
    before_separator = source_span_id(**kwargs, block_end=3)
    through_separator = source_span_id(**kwargs, block_end=4)
    assert before_separator
    assert through_separator
    assert before_separator != through_separator


def test_write_outputs_removes_stale_divergence_file(tmp_path):
    output = tmp_path / "trace"
    write_outputs(_graded(), output)
    stale = output / "first_divergence.csv"
    assert stale.exists()
    write_outputs(trace(load_evidence(EVIDENCE)), output)
    assert not stale.exists()


def test_cli_removes_stale_differential_without_candidate(tmp_path):
    output = tmp_path / "trace"
    output.mkdir()
    stale = output / "forensic_differential.json"
    stale.write_text('{"stale": true}\n', encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/trace_recorded_formation.py"),
         str(EVIDENCE), "--output", str(output)],
        check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert not stale.exists()
