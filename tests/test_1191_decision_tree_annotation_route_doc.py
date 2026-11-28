"""Check the #1191 decision-tree annotation route contract; no runtime proof.

The contract maps the current model route by symbol. These checks fail when
that map, the verification list or the contract header drift apart.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import re
from pathlib import Path

from scripts.validate_change_contract import validate_change_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / 'docs' / 'change-contracts'
CONTRACT = CONTRACTS / '1191-decision-tree-annotation-route.md'
VERIFICATION = CONTRACTS / '1191-decision-tree-annotation-route-verification.md'


def test_contract_header_is_a_valid_class_a_high_risk_contract():
    assert validate_change_contract(CONTRACT.read_text(encoding='utf-8')) == []


def test_contract_records_the_implementation_stage():
    assert '**Status:** Fase 2 is gestart' in CONTRACT.read_text(encoding='utf-8')


def test_every_claim_cited_in_the_contract_is_defined_in_the_verification_list():
    cited = set(re.findall(r'\bV\d\d\b', CONTRACT.read_text(encoding='utf-8')))
    defined = set(re.findall(r'^\| (V\d\d) \|', VERIFICATION.read_text(encoding='utf-8'), re.MULTILINE))
    assert cited and cited <= defined


def test_mapped_model_route_is_removed_and_historical_readers_remain():
    route = (ROOT / 'src' / 'vorming' / 'decision_tree_route_v1.py').read_text(encoding='utf-8')
    for symbol in ('def llm_proposer', 'def request_proposal', 'def request_input',
                   'PROPOSER_PROMPT', 'EXPORT_PROMPT'):
        assert symbol not in route
    for symbol in ('def verify_export_preserved', 'def finalize', 'def has_recorded_route'):
        assert symbol in route
    binding = (ROOT / 'src' / 'vorming' / 'pre_review_semantic_v1.py').read_text(encoding='utf-8')
    assert '_decision_tree_proposer' not in binding


def test_reused_proposal_contract_still_offers_the_mapped_roles_and_uncertainty_codes():
    from src.vorming.decision_tree_proposal_v1 import ROLES, SELECTIONS, UNRESOLVED_CODES
    text = CONTRACT.read_text(encoding='utf-8')
    assert ROLES == ('start', 'question', 'action', 'outcome', 'context')
    assert SELECTIONS == ('single', 'multiple')
    for code in UNRESOLVED_CODES:
        assert f'`{code}`' in text
