"""D4.1 version-bound KnowledgeRelation kernel regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.integrity_kernel import compute_canonical_object_hash, schema_errors, stamp_canonical_hashes
from src.knowledge_relations_v1 import (
    CONFIRMED_FIELD,
    PROPOSED_FIELD,
    SEMANTIC_RELATION_TYPES,
    STRUCTURAL_RELATION_TYPES,
    build_knowledge_relation,
    canonicalize_knowledge_relation_set,
    confirmed_knowledge_relations_of,
    knowledge_relation_errors,
    knowledge_relation_set_hash,
    legacy_knowledge_relations_view,
    legacy_relation_mirror_matches,
    proposed_knowledge_relations_of,
    relation_id_for,
    relation_kind,
    validate_knowledge_relation,
    validate_knowledge_relation_set,
)
from src.operations_console_v1 import SCHEMA_V13
from src.semantic_transform_generic_v1 import transform
from src.serving_relations_v1 import CLOSED_RELATION_SET, binding_relations


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_V14 = ROOT / "schemas" / "knowledge_object.schema.v1.4.json"


def _base_object() -> dict:
    raw = [
        {
            "fragment_id": "frag-d41",
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
            "source_id": "source-d41",
            "title": "D4.1 source",
            "publisher": "V&VN",
            "source_url": "https://example.org/d41",
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
        "document_id": "doc-d41",
        "object_version": "1.0",
        "target_group": ["verpleegkundige"],
        "care_setting": [],
        "topic": ["test"],
        "objects": [
            {
                "object_id": "rec-d41",
                "object_type": "recommendation",
                "proposed_object_type": "recommendation",
                "confirmed_object_type": "recommendation",
                "text": "Adviseer de interventie.",
                "source_fragment_ids": ["frag-d41"],
            }
        ],
    }
    return transform(spec, manifest, raw)[0]


def _relation(
    relation_type: str = "applies_if",
    target_id: str = "condition-a",
    target_version: str = "1.0",
    *,
    source_id: str = "rec-d41",
    source_version: str = "1.0",
) -> dict:
    return build_knowledge_relation(
        source_object_id=source_id,
        source_object_version=source_version,
        relation_type=relation_type,
        target_object_id=target_id,
        target_object_version=target_version,
    )


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


def test_relation_id_is_deterministic_and_binds_both_endpoint_versions() -> None:
    kwargs = dict(
        source_object_id="rec-a",
        source_object_version="1.2",
        relation_type="applies_if",
        target_object_id="cond-a",
        target_object_version="3.4",
    )
    first = relation_id_for(**kwargs)
    assert first == relation_id_for(**kwargs)
    assert first.startswith("rel-")
    assert len(first) == 68

    for field, replacement in (
        ("source_object_id", "rec-b"),
        ("source_object_version", "1.3"),
        ("relation_type", "except_if"),
        ("target_object_id", "cond-b"),
        ("target_object_version", "3.5"),
    ):
        changed = dict(kwargs)
        changed[field] = replacement
        assert relation_id_for(**changed) != first


def test_new_format_accepts_only_the_existing_closed_relation_types() -> None:
    for relation_type in CLOSED_RELATION_SET:
        value = _relation(relation_type)
        assert value["relation_type"] == relation_type
        assert validate_knowledge_relation(
            value,
            source_object_id="rec-d41",
            source_object_version="1.0",
        ) == []

    assert SEMANTIC_RELATION_TYPES | STRUCTURAL_RELATION_TYPES == CLOSED_RELATION_SET
    assert SEMANTIC_RELATION_TYPES.isdisjoint(STRUCTURAL_RELATION_TYPES)
    assert relation_kind("applies_if") == "semantic"
    assert relation_kind("parent") == "structural"

    for historical in ("conditioned_by", "exception_to", "supports", "child_of", "superseded_by"):
        with pytest.raises(ValueError, match="knowledge_relation_type_invalid"):
            _relation(historical)


def test_relation_requires_exact_target_version_and_forbids_self_relation() -> None:
    with pytest.raises(ValueError, match="knowledge_relation_target_object_version_missing"):
        _relation(target_version="")
    with pytest.raises(ValueError, match="knowledge_relation_self_relation"):
        _relation(target_id="rec-d41")

    valid = _relation()
    missing = {**valid, "target_object_version": ""}
    assert "knowledge_relation_target_object_version_missing" in validate_knowledge_relation(
        missing,
        source_object_id="rec-d41",
        source_object_version="1.0",
    )


def test_relation_id_must_match_the_exact_value_object() -> None:
    value = _relation()
    forged = {**value, "relation_id": "rel-" + "0" * 64}
    assert "knowledge_relation_id_mismatch" in validate_knowledge_relation(
        forged,
        source_object_id="rec-d41",
        source_object_version="1.0",
    )


def test_many_to_many_is_representable_without_duplicating_target_objects() -> None:
    source_a = [
        _relation("applies_if", "condition-shared", source_id="rec-a"),
        _relation("supported_by", "support-shared", source_id="rec-a"),
    ]
    source_b = [
        _relation("applies_if", "condition-shared", source_id="rec-b"),
        _relation("supported_by", "support-shared", source_id="rec-b"),
    ]

    assert source_a[0]["target_object_id"] == source_b[0]["target_object_id"]
    assert source_a[0]["relation_id"] != source_b[0]["relation_id"]
    assert source_a[1]["target_object_id"] == source_b[1]["target_object_id"]
    assert source_a[1]["relation_id"] != source_b[1]["relation_id"]


def test_relation_set_has_deterministic_order_and_order_independent_hash() -> None:
    a = _relation("supported_by", "support-b")
    b = _relation("applies_if", "condition-a")
    unsorted = [a, b]

    assert "knowledge_relation_set_not_canonical_order" in validate_knowledge_relation_set(
        unsorted,
        source_object_id="rec-d41",
        source_object_version="1.0",
    )
    canonical = canonicalize_knowledge_relation_set(
        unsorted,
        source_object_id="rec-d41",
        source_object_version="1.0",
    )
    assert canonical == [b, a]
    assert knowledge_relation_set_hash(
        [a, b],
        source_object_id="rec-d41",
        source_object_version="1.0",
    ) == knowledge_relation_set_hash(
        [b, a],
        source_object_id="rec-d41",
        source_object_version="1.0",
    )


def test_duplicate_relation_semantics_are_rejected() -> None:
    row = _relation()
    errors = validate_knowledge_relation_set(
        [row, deepcopy(row)],
        source_object_id="rec-d41",
        source_object_version="1.0",
        require_canonical_order=False,
    )
    assert any("knowledge_relation_duplicate" in error for error in errors)


def test_schema_v14_accepts_new_relation_sets_and_v13_remains_runtime_contract() -> None:
    obj = _base_object()
    obj[PROPOSED_FIELD] = [_relation("applies_if", "condition-a")]
    obj[CONFIRMED_FIELD] = [_relation("supported_by", "support-a")]
    stamp_canonical_hashes(obj)

    assert knowledge_relation_errors(obj) == []
    assert schema_errors(obj, SCHEMA_V14) == []
    assert schema_errors(obj, Path(SCHEMA_V13))

    v13 = json.loads(Path(SCHEMA_V13).read_text(encoding="utf-8"))
    v14 = json.loads(SCHEMA_V14.read_text(encoding="utf-8"))
    assert v13["$id"].endswith("v1.3.json")
    assert PROPOSED_FIELD not in v13["properties"]
    assert CONFIRMED_FIELD not in v13["properties"]
    assert v14["$id"].endswith("v1.4.json")
    assert PROPOSED_FIELD in v14["properties"]
    assert CONFIRMED_FIELD in v14["properties"]

    # D4.1 is kernel only: the OperationsConsole still validates v1.3.
    assert Path(SCHEMA_V13).name == "knowledge_object.schema.v1.3.json"


def test_exact_legacy_compatibility_mirror_may_coexist_during_staged_cutover() -> None:
    new_row = _relation()
    legacy_row = {
        "relation_type": "applies_if",
        "target_object_id": "condition-a",
        "target_object_version": "1.0",
        "confirmed": True,
    }
    assert legacy_relation_mirror_matches([new_row], [legacy_row])

    obj = _base_object()
    obj[CONFIRMED_FIELD] = [new_row]
    obj["confirmed_relations"] = [legacy_row]
    assert knowledge_relation_errors(obj) == []
    assert schema_errors(obj, SCHEMA_V14) == []


def test_divergent_or_unversioned_legacy_relation_is_not_a_valid_mirror() -> None:
    new_row = _relation()
    divergent = {
        "relation_type": "applies_if",
        "target_object_id": "condition-b",
        "target_object_version": "1.0",
        "confirmed": True,
    }
    unversioned = {
        "relation_type": "applies_if",
        "target_object_id": "condition-a",
        "confirmed": True,
    }
    assert not legacy_relation_mirror_matches([new_row], [divergent])
    assert not legacy_relation_mirror_matches([new_row], [unversioned])

    obj = _base_object()
    obj[CONFIRMED_FIELD] = [new_row]
    obj["confirmed_relations"] = [divergent]
    assert (
        "confirmed_knowledge_relations_legacy_authority_conflict"
        in knowledge_relation_errors(obj)
    )


def test_empty_legacy_containers_do_not_block_additive_new_format() -> None:
    obj = _base_object()
    assert obj["relations"] == []
    assert obj["confirmed_relations"] == []
    obj[PROPOSED_FIELD] = [_relation()]
    obj[CONFIRMED_FIELD] = [_relation("supported_by", "support-a")]
    assert knowledge_relation_errors(obj) == []
    assert schema_errors(obj, SCHEMA_V14) == []


def test_new_accessors_never_promote_legacy_relations() -> None:
    legacy = {
        "relations": [
            {
                "relation_type": "conditioned_by",
                "target_object_id": "condition-a",
                "confirmed": False,
            }
        ],
        "confirmed_relations": [
            {
                "relation_type": "supports",
                "target_object_id": "support-a",
                "target_object_version": "2.0",
                "confirmed": True,
            }
        ],
    }
    assert proposed_knowledge_relations_of(legacy) == []
    assert confirmed_knowledge_relations_of(legacy) == []

    proposed_view = legacy_knowledge_relations_view(legacy, confirmed=False)
    confirmed_view = legacy_knowledge_relations_view(legacy, confirmed=True)
    assert proposed_view == [
        {
            "authority": "legacy_compatibility",
            "persisted": False,
            "legacy_field": "relations",
            "relation_type": "applies_if",
            "relation_kind": "semantic",
            "target_object_id": "condition-a",
            "target_object_version": None,
        }
    ]
    assert confirmed_view == [
        {
            "authority": "legacy_compatibility",
            "persisted": False,
            "legacy_field": "confirmed_relations",
            "relation_type": "supported_by",
            "relation_kind": "semantic",
            "target_object_id": "support-a",
            "target_object_version": "2.0",
        }
    ]
    assert "relation_id" not in proposed_view[0]
    assert "relation_id" not in confirmed_view[0]


def test_legacy_canonical_hash_is_frozen_when_d4_fields_are_absent() -> None:
    assert compute_canonical_object_hash(_legacy_hash_object()) == (
        "095e6eaee7a479a6e4b59c6b2e9d83ec27a0251f4fb79a73385580e93572b803"
    )


def test_new_relation_identity_and_target_version_change_canonical_hash() -> None:
    base = _base_object()
    base_hash = compute_canonical_object_hash(base)

    linked = deepcopy(base)
    linked[CONFIRMED_FIELD] = [_relation()]
    linked_hash = compute_canonical_object_hash(linked)
    assert linked_hash != base_hash

    target_revision = deepcopy(base)
    target_revision[CONFIRMED_FIELD] = [_relation(target_version="1.1")]
    assert compute_canonical_object_hash(target_revision) != linked_hash


def test_d41_does_not_cut_serving_over_to_new_relation_fields() -> None:
    obj = _base_object()
    obj[CONFIRMED_FIELD] = [_relation()]
    assert confirmed_knowledge_relations_of(obj)
    assert binding_relations(obj) == []


def test_confirmed_relation_field_is_a_list_copy_not_mutable_alias() -> None:
    row = _relation()
    obj = {CONFIRMED_FIELD: [row]}
    read = confirmed_knowledge_relations_of(obj)
    read[0]["target_object_id"] = "mutated"
    assert obj[CONFIRMED_FIELD][0]["target_object_id"] == "condition-a"
