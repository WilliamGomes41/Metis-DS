"""Check the #1091 KO-selection guidance design document (#1092); no runtime proof.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs' / 'change-contracts' / '1091-ko-selection-guidance.md'


def test_design_document_exists_with_heading():
    text = DESIGN.read_text(encoding='utf-8')
    assert text.startswith('# #1091 — Domeinontwerp: selectiebegeleiding voor kennisobjecten\n')


def test_design_states_it_is_not_implemented():
    text = DESIGN.read_text(encoding='utf-8')
    assert '**Status:** ontwerp ter besluit; niet geïmplementeerd.' in text


def test_design_keeps_human_decision_and_adds_no_objects():
    text = DESIGN.read_text(encoding='utf-8')
    assert 'De medewerker houdt het inhoudelijke besluit; het systeem maakt geen extra kennisobjecten.' in text
