"""D3.1 recommendation semantics kernel regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from src.integrity_kernel import (
    compute_canonical_object_hash,
    schema_errors,
    stamp_canonical_hashes,
)
from src.operations_console_v1 import SCHEMA_V12
from src.recommendation_semantics_v1 import (
    CONFIRMED_FIELD,
    PROPOSED_FIELD,
    confirmed_recommendation_semantics_of,
    legacy_recommendation_semantics_view,
    recommendation_semantics_errors,
    validate_recommendation_semantics,
)
from src.semantic_transform_generic_v1 import transform


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_V13 = ROOT / "schemas" / "knowledge_object.schema.v1.3.json"


def _semantics(
    direction: str,
    strength: str | None,
    *,
    status: str = "explicit",
    strength_evidence: str | None = "Sterke aanbeveling",
    source_label: str | None = "Sterke aanbeveling",
) -> dict:
    return {
        "version": "recommendation-semantics-v1",
        "direction": direction,
        "strength": strength,
        "strength_status": status,
        "direction_evidence_span": "Adviseer de interventie.",
        "strength_evidence_span": strength_evidence,
        "source_label": source_label,
        "normalization_scheme": "source_literal_v1",
    }


def _base_object() -> dict:
    raw = [
        {
            "fragment_id": "frag-1",
            "source_page": 1,
            "fragment_hash": "a" * 64,
            "bbox": [1.0, 2.0, 3.0, 4.0],
            "source_locator": {
                "locator_type": "page_bbox",
                "locator_value": "page:1;bbox:1,2,3,4",
            },
        }
    ]
    manifest = {
        "canonical_source": {
            "source_id": "source-d31",
            "title": "D3.1 source",
            "publisher": "V&VN",
            "source_url": "https://example.org/d31",
            "source_type": "pdf",
            "source_level": 1,
            "canonicality": "canonical",
            "source_checksum": "b" * 64,
            "checksum_algorithm": "sha256",
            "integrity_status": "verified",
            "publication_date": "2026-09-25",
            "version": "1.0",
        }
    }
    spec = {
        "spec_version": "1.0",
        "document_id": "doc-d31",
        "object_version": "1.0",
        "target_group": ["verpleegkundige"],
        "care_setting": [],
        "topic": ["test"],
        "objects": [
            {
                "object_id": "rec-d31",
                "object_type": "recommendation",
                "proposed_object_type": "recommendation",
                "confirmed_object_type": "recommendation",
                "text": "Adviseer de interventie.",
                "source_fragment_ids": ["frag-1"],
            }
        ],
    }
    return transform(spec, manifest, raw)[0]


def _legacy_hash_object() -> dict:
    return {
        "object_id": "legacy-rec-1",
        "document_id": "doc-1",
        "object_version": "1.0",
        "parent_object_id": None,
        "object_type": "recommendation",
        "source": {},
        "structure": {},
        "content": {"clean_text": "Gebruik de interventie."},
        "logic": {},
        "relations": [],
        "decision_graph": {},
        "risk": {},
        "uncertainty": {},
        "provenance": {
            "canonical_object_hash": "x",
            "content_hash": "y",
            "source_fragments": [],
        },
        "confirmed_object_type": "recommendation",
        "confirmed_recommendation_strength": "doen",
        "metadata": {
            "admission": {"x": 1},
            "passage_register": {"x": 1},
            "candidate_eligibility": {"x": 1},
            "kept": "yes",
        },
    }


def test_direction_and_strength_are_independent_closed_axes() -> None:
    for direction in ("for", "against"):
        for strength in ("strong", "weak"):
            assert validate_recommendation_semantics(
                _semantics(direction, strength)
            ) == []


def test_not_stated_has_no_strength_or_strength_evidence() -> None:
    value = _semantics(
        "for",
        None,
        status="not_stated",
        strength_evidence=None,
        source_label=None,
    )
    assert validate_recommendation_semantics(value) == []

    wrong_strength = {**value, "strength": "weak"}
    assert "recommendation_strength_must_be_null_when_not_stated" in (
        validate_recommendation_semantics(wrong_strength)
    )
    wrong_evidence = {**value, "strength_evidence_span": "niet vermeld"}
    assert "recommendation_strength_evidence_forbidden_when_not_stated" in (
        validate_recommendation_semantics(wrong_evidence)
    )


def test_unmapped_is_proposal_only_and_requires_source_evidence() -> None:
    value = _semantics(
        "against",
        None,
        status="unmapped",
        strength_evidence="Voorwaardelijke aanbeveling",
        source_label="Voorwaardelijke aanbeveling",
    )
    assert validate_recommendation_semantics(value, confirmed=False) == []
    assert "confirmed_recommendation_strength_unmapped" in (
        validate_recommendation_semantics(value, confirmed=True)
    )

    no_evidence = {**value, "strength_evidence_span": None}
    assert "recommendation_strength_evidence_missing" in (
        validate_recommendation_semantics(no_evidence)
    )


def test_direction_requires_literal_source_evidence() -> None:
    value = _semantics("for", "strong")
    value["direction_evidence_span"] = ""
    assert "recommendation_direction_evidence_missing" in (
        validate_recommendation_semantics(value)
    )


def test_schema_v13_accepts_new_confirmed_semantics() -> None:
    obj = _base_object()
    obj[PROPOSED_FIELD] = _semantics("against", "weak")
    obj[CONFIRMED_FIELD] = _semantics("against", "weak")
    stamp_canonical_hashes(obj)

    assert recommendation_semantics_errors(obj) == []
    assert schema_errors(obj, SCHEMA_V13) == []


def test_schema_and_kernel_reject_dual_legacy_and_new_authority() -> None:
    obj = _base_object()
    obj[CONFIRMED_FIELD] = _semantics("for", "strong")
    obj["confirmed_recommendation_strength"] = "doen"

    assert (
        "confirmed_recommendation_semantics_legacy_authority_conflict"
        in recommendation_semantics_errors(obj)
    )
    assert schema_errors(obj, SCHEMA_V13)


def test_confirmed_semantics_is_bound_to_confirmed_recommendation_type() -> None:
    obj = _base_object()
    obj[CONFIRMED_FIELD] = _semantics("for", "weak")
    obj["confirmed_object_type"] = "condition"

    assert (
        "confirmed_recommendation_semantics_requires_recommendation_type"
        in recommendation_semantics_errors(obj)
    )
    assert schema_errors(obj, SCHEMA_V13)


def test_confirmed_accessor_never_promotes_legacy_strength() -> None:
    legacy = {
        "confirmed_object_type": "recommendation",
        "confirmed_recommendation_strength": "overweeg",
    }
    assert confirmed_recommendation_semantics_of(legacy) == {}

    view = legacy_recommendation_semantics_view(legacy)
    assert view == {
        "authority": "legacy_compatibility",
        "persisted": False,
        "legacy_field": "confirmed_recommendation_strength",
        "legacy_value": "overweeg",
        "direction": "for",
        "strength": "weak",
        "strength_status": "explicit",
        "source_label": "OVERWEEG",
    }
    assert CONFIRMED_FIELD not in legacy


def test_legacy_compatibility_mapping_is_closed_and_does_not_invent_against_weak() -> None:
    expected = {
        "doen": ("for", "strong"),
        "overweeg": ("for", "weak"),
        "niet_doen": ("against", "strong"),
    }
    seen = set()
    for legacy, pair in expected.items():
        view = legacy_recommendation_semantics_view(
            {"confirmed_recommendation_strength": legacy}
        )
        seen.add((view["direction"], view["strength"]))
        assert (view["direction"], view["strength"]) == pair
    assert ("against", "weak") not in seen


def test_legacy_canonical_hash_is_frozen_when_new_fields_are_absent() -> None:
    assert compute_canonical_object_hash(_legacy_hash_object()) == (
        "095e6eaee7a479a6e4b59c6b2e9d83ec27a0251f4fb79a73385580e93572b803"
    )


def test_new_semantics_changes_hash_for_direction_strength_and_evidence() -> None:
    base = _base_object()
    base.pop("proposed_object_type", None)
    base["confirmed_object_type"] = "recommendation"

    strong_for = deepcopy(base)
    strong_for[CONFIRMED_FIELD] = _semantics("for", "strong")
    strong_for_hash = compute_canonical_object_hash(strong_for)

    against = deepcopy(strong_for)
    against[CONFIRMED_FIELD]["direction"] = "against"
    assert compute_canonical_object_hash(against) != strong_for_hash

    weak = deepcopy(strong_for)
    weak[CONFIRMED_FIELD]["strength"] = "weak"
    assert compute_canonical_object_hash(weak) != strong_for_hash

    evidence = deepcopy(strong_for)
    evidence[CONFIRMED_FIELD]["direction_evidence_span"] = "Gebruik de interventie."
    assert compute_canonical_object_hash(evidence) != strong_for_hash


def test_schema_v13_is_additive_and_runtime_stays_on_v12() -> None:
    v12 = json.loads(
        (ROOT / "schemas" / "knowledge_object.schema.v1.2.json").read_text(
            encoding="utf-8"
        )
    )
    v13 = json.loads(SCHEMA_V13.read_text(encoding="utf-8"))

    assert v12["$id"].endswith("v1.2.json")
    assert PROPOSED_FIELD not in v12["properties"]
    assert CONFIRMED_FIELD not in v12["properties"]
    assert v13["$id"].endswith("v1.3.json")
    assert PROPOSED_FIELD in v13["properties"]
    assert CONFIRMED_FIELD in v13["properties"]
    assert Path(SCHEMA_V12).name == "knowledge_object.schema.v1.2.json"


def test_decision_tree_outcome_remains_legacy_only_in_d31() -> None:
    outcome = {
        "object_type": "outcome",
        "confirmed_object_type": "outcome",
        "confirmed_recommendation_strength": "niet_doen",
    }
    assert legacy_recommendation_semantics_view(outcome)["direction"] == "against"
    assert confirmed_recommendation_semantics_of(outcome) == {}
