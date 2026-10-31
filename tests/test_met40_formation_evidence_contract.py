"""Check the design handoff; this is not proof of the proposed runtime boundary.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import re

from scripts.validate_change_contract import (
    HIGH_RISK_FIELDS,
    LIFECYCLE_FIELDS,
    parse_fields,
    validate_change_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/change-contracts/met40-formation-evidence-context.md'


def test_design_and_future_runtime_contracts_are_distinct_and_complete():
    text = CONTRACT.read_text(encoding='utf-8')
    fields = parse_fields(text)
    assert validate_change_contract(text) == []
    assert (fields['Change class'], fields['Rewrite risk'],
            fields['Touches lifecycle invariants']) == ('C', 'none', 'no')
    # A documentation-only PR must still hand over all mandatory fields for
    # the future high-risk/lifecycle implementation; presence is not acceptance.
    assert all(fields.get(name) for name in (*HIGH_RISK_FIELDS, *LIFECYCLE_FIELDS))


def test_concrete_source_inventory_resolves_to_repository_files():
    text = CONTRACT.read_text(encoding='utf-8')
    references = re.findall(r'`(src/[^`\s]+\.py)(?::([0-9,]+))?`', text)
    assert references, 'The contract must ground its inventory in repository sources'
    for relative, anchors in references:
        path = ROOT / relative
        assert path.is_file(), relative
        if anchors:
            line_count = len(path.read_text(encoding='utf-8').splitlines())
            assert all(1 <= int(line) <= line_count for line in anchors.split(',')), relative
