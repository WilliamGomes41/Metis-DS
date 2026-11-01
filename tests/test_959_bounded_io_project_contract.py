"""Check the #959 project-design handoff; this is not proof of the bounded runtime.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path

from scripts.validate_change_contract import parse_fields, validate_change_contract


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/change-contracts/959-bounded-io-project-redesign.md'


def test_project_design_is_a_documentation_only_contract():
    text = CONTRACT.read_text(encoding='utf-8')
    fields = parse_fields(text)
    assert validate_change_contract(text) == []
    assert (fields['Change class'], fields['Rewrite risk'],
            fields['Touches lifecycle invariants']) == ('C', 'none', 'no')


def test_proof_links_every_named_project_issue():
    text = CONTRACT.read_text(encoding='utf-8')
    for issue in (959, 729, 942, 952, 953, 931):
        assert f'#{issue}' in text, issue
