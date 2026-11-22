"""Check the #1107 CHANGE_DESIGN for Playwright trace-on-failure; design only, no runtime proof.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import re
from pathlib import Path

from scripts import linear_github_sync as sync

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs' / 'change-contracts' / '1107-playwright-trace-on-failure.md'
SHA = 'b' * 40


def design():
    return DESIGN.read_text(encoding='utf-8')


def test_issue_1107_is_bound_to_met_113_and_the_design_names_both():
    bindings = sync.load_bindings()
    assert sync.Binding(1107, 'MET-113') in bindings
    body = ('Part of MET-113.\n<!-- metis-linear-handoff-v1\n' + json.dumps({
        'version': 1, 'linear_issue': 'MET-113', 'head': SHA, 'remaining_work': True,
        'next_step': 'Beoordeel het ontwerp.', 'evidence': []}) + '\n-->')
    sync.validate_pr_handoff(body, SHA, bindings, branch="chore/issue-proof")
    text = design()
    assert 'https://github.com/WilliamGomes41/Metis-DS/issues/1107' in text
    assert 'https://linear.app/metis-phoenix/issue/MET-113' in text


def test_design_is_a_class_b_design_without_implementation():
    text = design()
    assert text.startswith('# #1107 — CHANGE_DESIGN: Playwright trace-on-failure')
    assert 'Change class: B\n' in text and 'Rewrite risk: none\n' in text
    assert 'Dit bestand is het ontwerp. Het bevat geen code, geen workflowwijziging' in text
    assert 'Geen GO voor PR 1.' in text


def test_design_fixes_the_invariants_of_the_trace_keten():
    text = design()
    for invariant in ('Alleen loopback en synthetische fixtures. Live NOOIT.', 'Trace alleen bij failure.',
                      'Geen cookies of geheimen in een artifact.',
                      'Namen en afhankelijkheden van de required checks blijven identiek.'):
        assert invariant in text, invariant
    policy = json.loads((ROOT / 'config' / 'github_merge_policy.v1.json').read_text())
    assert {c['context'] for c in policy['required_status_checks']} == {'test (3.12)', 'test (3.13)', 'handoff-contract'}


def test_design_keeps_existing_in_memory_storage_state_and_refuses_file_state():
    text = design()
    assert 'Geen `storageState` uit een bestand of omgeving.' in text
    assert '`recordHar` nergens in `tests/` en `scripts/` voorkomt' in text


def test_design_covers_schema_retention_failfirst_tests_and_rollback():
    text = design()
    for heading in ('## 4. Schema `agent-handoff.json` v1', '## 5. Artifact en bewaartermijn',
                    '## 6. Fail-first testplan PR 1', '## 7. Rollback', '## 9. OPENVRAAG'):
        assert heading in text, heading
    assert '"schema": "metis.agent-handoff"' in text and '"version": 1' in text
    assert 'Geen cookies of geheimen in trace.zip.' in text
    assert 'geeft `outcome: incomplete`, nooit `pass`' in text


def test_design_uses_the_formation_text_rule_words():
    quote = re.compile(r'^- 20 november 2026.*$', re.MULTILINE)
    text = quote.sub('', design())
    assert not re.search(r'\b(mag|Mag|kan|Kan)\b', text)
    assert 'MAG NIET' in text and 'MOET' in text and 'NOOIT' in text and 'OPENVRAAG' in text
