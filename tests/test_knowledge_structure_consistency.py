"""Regression tests for one relation contract and coherent hierarchy."""
from __future__ import annotations

from src.beslisboom_path_v1 import outcome_review_errors
from src.integrity_kernel import validate_parent_relations
from src.serving_relations_v1 import binding_relations


def _relation(*, confirmed: bool) -> dict:
    return {
        "relation_type": "applies_if",
        "target_object_id": "condition-1",
        "confirmed": confirmed,
    }


def test_explicit_confirmed_relations_is_authoritative() -> None:
    proposed = _relation(confirmed=True)

    assert binding_relations(
        {"relations": [proposed], "confirmed_relations": []}
    ) == []
    assert binding_relations(
        {"relations": [proposed], "confirmed_relations": [_relation(confirmed=False)]}
    ) == []


def test_legacy_confirmed_proposal_only_falls_back_when_explicit_field_absent() -> None:
    assert binding_relations({"relations": [_relation(confirmed=True)]}) == [
        _relation(confirmed=True)
    ]


def test_beslisboom_uses_the_shared_relation_contract() -> None:
    outcome = {
        "content": {"clean_text": "Verwijs naar de huisarts."},
        "relations": [_relation(confirmed=True)],
        "confirmed_relations": [],
    }
    assert "outcome_relation_unconfirmed" in outcome_review_errors(outcome)

    outcome.pop("confirmed_relations")
    assert "outcome_relation_unconfirmed" not in outcome_review_errors(outcome)


def _object(object_id: str, *, parent: str | None = None) -> dict:
    return {
        "object_id": object_id,
        "object_type": "explanation",
        "parent_object_id": parent,
        "relations": [],
        "confirmed_relations": [],
    }


def test_hierarchy_rejects_self_parent_and_cycles() -> None:
    self_parent = _object("self", parent="self")
    errors = validate_parent_relations([self_parent])
    assert "self_parent:self" in errors
    assert "parent_cycle:self" in errors

    first = _object("first", parent="second")
    second = _object("second", parent="first")
    errors = validate_parent_relations([first, second])
    assert any(error.startswith("parent_cycle:") for error in errors)


def test_confirmed_child_relation_must_match_canonical_parent() -> None:
    child = _object("child", parent="parent-a")
    child["confirmed_relations"] = [
        {
            "relation_type": "child",
            "target_object_id": "parent-b",
            "confirmed": True,
        }
    ]
    errors = validate_parent_relations(
        [child, _object("parent-a"), _object("parent-b")]
    )
    assert "parent_relation_mismatch:child" in errors


def test_numbered_heading_parent_must_be_structurally_valid() -> None:
    child = {
        **_object("heading-5-4-1", parent="heading-2"),
        "object_type": "heading",
        "heading_role": "body",
        "content": {"clean_text": "5.4.1 Anamnese"},
    }
    wrong_parent = {
        **_object("heading-2"),
        "object_type": "heading",
        "heading_role": "body",
        "content": {"clean_text": "2 Doel"},
    }
    assert (
        "invalid_parent_structure:heading-5-4-1:heading-2"
        in validate_parent_relations([child, wrong_parent])
    )


def test_hierarchy_validation_marks_heading_roles_once(monkeypatch) -> None:
    import src.heading_parent_list_v1 as headings

    calls = 0
    original = headings.mark_heading_roles

    def counted(rows):
        nonlocal calls
        calls += 1
        return original(rows)

    monkeypatch.setattr(headings, "mark_heading_roles", counted)
    parent = {
        **_object("heading-5"),
        "object_type": "heading",
        "content": {"clean_text": "5 Aanbevelingen"},
    }
    child = {
        **_object("heading-5-4", parent="heading-5"),
        "object_type": "heading",
        "content": {"clean_text": "5.4 Diagnostiek"},
    }

    assert validate_parent_relations([parent, child]) == []
    assert calls == 1
