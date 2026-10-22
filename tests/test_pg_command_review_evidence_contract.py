"""#803 P1: the command-local review reader is Rewrite risk: high (shared review read boundary).

# release-control-evidence: scope/belofte
# release-control-evidence: releasebewijs
"""
from pathlib import Path

from scripts.validate_change_contract import parse_fields, validate_change_contract

CONTRACT = Path(__file__).resolve().parents[1] / 'docs' / 'change-contracts' / 'pg-command-review-evidence.md'


def test_command_review_contract_is_high_risk_and_complete():
    text = CONTRACT.read_text(encoding='utf-8')
    fields = {k.lower(): v for k, v in parse_fields(text).items()}
    assert fields.get('rewrite risk', '').strip().lower() == 'high'
    assert validate_change_contract(text) == []
    assert '## Adversariële review' in text
