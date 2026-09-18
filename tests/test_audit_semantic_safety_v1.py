"""Frozen semantic safety audit evidence."""
from __future__ import annotations

import json
from pathlib import Path

from src.audit_semantic_safety_v1 import (
    REQUIRED_RISK_CATEGORIES,
    load_frozen_safety_suite,
    run_frozen_semantic_safety_suite,
)

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "data" / "audit" / "semantic_passage_safety_v1.json"
EVALUATED_COMMIT = "79b35616725da3a1f42a938c2f5a874ca16cfad0"


def _response(proposal: dict) -> dict:
    return {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(proposal)}],
            }
        ]
    }


def _full_source_model(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
    block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
    return _response(
        {
            "objects": [
                {
                    "spans": [
                        {
                            "block_id": block["block_id"],
                            "start": 0,
                            "end": len(block["text"]),
                        }
                    ],
                    "proposed_object_type": "unclassified",
                }
            ],
            "abstain_reason": None,
        }
    )


def test_checked_in_suite_is_frozen_hash_valid_and_covers_required_risks() -> None:
    suite = load_frozen_safety_suite(SUITE)

    assert suite["suite_id"] == "semantic-passage-safety-v1"
    assert suite["evaluated_baseline_commit"] == EVALUATED_COMMIT
    assert {case["risk_category"] for case in suite["cases"]} == REQUIRED_RISK_CATEGORIES
    assert len(suite["suite_hash"]) == 64


def test_full_source_semantic_candidate_passes_frozen_machine_safety_checks() -> None:
    suite = load_frozen_safety_suite(SUITE)

    report = run_frozen_semantic_safety_suite(
        suite,
        api_key="audit-secret",
        model="test-model",
        evaluated_commit=EVALUATED_COMMIT,
        post_json=_full_source_model,
    )

    assert report["machine_safety_pass"] is True
    assert report["candidate_pass_count"] == 5
    assert report["kernel_reject_count"] == 0
    assert report["requires_human_review"] is True
    assert "audit-secret" not in json.dumps(report, ensure_ascii=False)


def test_source_bound_candidate_still_fails_audit_when_condition_is_omitted() -> None:
    suite = load_frozen_safety_suite(SUITE)

    def omit_condition(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        if block["text"].startswith("Als de eGFR"):
            selected = "gebruik middel X niet."
            start = block["text"].index(selected)
            end = start + len(selected)
        else:
            start = 0
            end = len(block["text"])
        return _response(
            {
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": start,
                                "end": end,
                            }
                        ],
                        "proposed_object_type": "unclassified",
                    }
                ],
                "abstain_reason": None,
            }
        )

    report = run_frozen_semantic_safety_suite(
        suite,
        api_key="audit-secret",
        model="test-model",
        evaluated_commit=EVALUATED_COMMIT,
        post_json=omit_condition,
    )

    condition = next(row for row in report["results"] if row["risk_category"] == "condition")
    assert condition["candidate"]["kernel_reject"] is None
    assert condition["candidate"]["pass"] is False
    assert condition["candidate"]["evaluation"]["missing_anchors"] == [
        "Als de eGFR lager is dan 30 ml/min"
    ]
    assert condition["candidate"]["evaluation"]["broken_co_location_groups"] == [
        ["Als de eGFR lager is dan 30 ml/min", "gebruik middel X niet"]
    ]
    assert condition["candidate"]["coverage_remainders"]
    assert report["machine_safety_pass"] is False


def test_kernel_reject_is_reported_as_failure_not_as_safety_pass() -> None:
    suite = load_frozen_safety_suite(SUITE)

    def invalid_model(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        return _response(
            {
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": len(block["text"]),
                            }
                        ],
                        "proposed_object_type": "unclassified",
                        "candidate_text": "vrije modeltekst",
                    }
                ],
                "abstain_reason": None,
            }
        )

    report = run_frozen_semantic_safety_suite(
        suite,
        api_key="audit-secret",
        model="test-model",
        evaluated_commit=EVALUATED_COMMIT,
        post_json=invalid_model,
    )

    assert report["machine_safety_pass"] is False
    assert report["kernel_reject_count"] == 5
    assert all(
        row["candidate"]["kernel_reject"] == "pre_review_llm_proposal_rejected"
        for row in report["results"]
    )
