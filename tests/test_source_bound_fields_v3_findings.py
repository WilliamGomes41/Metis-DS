"""V3 field findings name the v3 field, not the reused v2 validator field.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from src.vorming.source_bound_fields_v3 import FIELDS, bind_fields

TEXT = "Bespreek de voorkeuren."
SELECTED = [{"block_id": "b", "start": 0, "end": len(TEXT), "text": TEXT}]


@pytest.mark.parametrize("field", ["actor_span", "target_group_span", "scope_span"])
def test_outside_candidate_finding_names_the_v3_field(field):
    raw = {name: {"span": None, "missing_reason": "not_applicable"} for name in FIELDS}
    raw[field] = {"span": {"block_id": "elders", "start": 0, "end": 7}, "missing_reason": None}
    with pytest.raises(ValueError, match="source_bound_field_outside_candidate") as caught:
        bind_fields(raw, selected=SELECTED, candidate_text=TEXT, proposed_type="recommendation")
    assert caught.value.finding["field"] == field
