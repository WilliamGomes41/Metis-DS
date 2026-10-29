"""B5-a (decided: do not build): exception wording stays inside its own object.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from src.vorming.source_bound_fields_v3 import CONTEXT_FIELDS, FIELDS, bind_fields

HEADING = "Uitzondering bij palliatieve zorg:"
TEXT = "Controleer de huid niet dagelijks."
SELECTED = [{"block_id": "b", "start": 0, "end": len(TEXT), "text": TEXT}]


def context(role):
    return [{"role": role, "span": {"block_id": "h", "start": 0, "end": len(HEADING)},
             "text": HEADING, "unresolved_reason": None}]


def raw(field):
    fields = {name: {"span": None, "missing_reason": "not_applicable"} for name in FIELDS}
    fields[field] = {"span": {"block_id": "h", "start": 0, "end": len(HEADING)}, "missing_reason": None}
    return fields


def test_exception_span_has_no_context_owner():
    assert "exception_span" not in CONTEXT_FIELDS


def test_exception_heading_outside_the_object_is_rejected():
    with pytest.raises(ValueError, match="source_bound_field_outside_candidate"):
        bind_fields(raw("exception_span"), selected=SELECTED, candidate_text=TEXT,
                    proposed_type="exception", context=context("exception"))


def test_condition_context_keeps_binding_as_before():
    # Contrast: the decided condition rule is untouched by B5-a.
    bound = bind_fields(raw("condition_span"), selected=SELECTED, candidate_text=TEXT,
                        proposed_type="condition", context=context("condition"))
    assert bound["values"]["condition_span"] == HEADING
