"""#636 P1: the refusal-store change is Rewrite risk: high (persisted schema + new mutation boundary).

# release-control-evidence: scope/belofte
# release-control-evidence: releasebewijs
"""
from pathlib import Path

from scripts.validate_change_contract import parse_fields, validate_change_contract

CONTRACT = Path(__file__).resolve().parents[1] / 'docs' / 'change-contracts' / 'publication-refusal-store.md'


def test_refusal_store_contract_is_high_risk_and_complete():
    text = CONTRACT.read_text(encoding='utf-8')
    fields = {k.lower(): v for k, v in parse_fields(text).items()}
    assert fields.get('rewrite risk', '').strip().lower() == 'high'
    assert validate_change_contract(text) == []
