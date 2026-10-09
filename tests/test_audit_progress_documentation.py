"""Audit tracking cannot silently equate a closed issue with production acceptance.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import importlib.util
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('audit_progress', ROOT / 'docs/audit/sync_progress.py')
progress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(progress)


def snapshot(flags, state='OPEN'):
    return {'number': 551, 'state': state, 'body': 'Audit-ID: A01\n\n## Voortgang\n' + '\n'.join(
        '- [' + ('x' if flag else ' ') + '] ' + stage
        for flag, stage in zip(flags, progress.STAGES)) + '\n\n## Bewijs\n'}


@pytest.mark.parametrize('flags,state,expected', [
    ([0, 0, 0, 0], 'OPEN', 'Open'),
    ([1, 0, 0, 0], 'OPEN', 'In uitvoering'),
    ([1, 1, 0, 0], 'OPEN', 'Code geverifieerd'),
    ([1, 1, 1, 0], 'OPEN', 'Gedeployed'),
    ([1, 1, 1, 1], 'CLOSED', 'Afgerond'),
    ([1, 1, 0, 0], 'CLOSED', 'Gesloten zonder acceptatie'),
    ([0, 1, 0, 0], 'OPEN', 'Status controleren'),
])
def test_issue_progress_distinguishes_code_deployment_and_acceptance(flags, state, expected):
    assert progress.status_of(snapshot(flags, state)) == expected


def test_missing_or_duplicate_issue_cannot_produce_partial_html_snapshot():
    document = '<time id="audit-snapshot">oude datum</time><span data-audit-status="A01">Open</span>'
    mapping = {'issues': {'A01': 551}}
    with pytest.raises(ValueError):
        progress.render(document, mapping, [], 'nieuwe datum')
    with pytest.raises(ValueError):
        progress.render(document, mapping, [snapshot([0]*4), snapshot([0]*4)], 'nieuwe datum')
    wrong = snapshot([1]*4)
    wrong['body'] = wrong['body'].replace('A01', 'A02')
    with pytest.raises(ValueError):
        progress.render(document, mapping, [wrong], 'nieuwe datum')
    updated = progress.render(document, mapping, [snapshot([1, 1, 0, 0])], 'nieuwe datum')
    assert 'Code geverifieerd' in updated and 'nieuwe datum' in updated


def test_repository_overview_has_one_link_per_id_and_no_embedded_sensitive_report():
    root = ROOT / 'docs/audit'
    mapping = json.loads((root / 'issue-links.json').read_text())
    document = (root / 'metis-codeaudit-voortgang.html').read_text()
    assert list(mapping['issues']) == [f'A{i:02}' for i in range(1, 28)]
    assert len(set(mapping['issues'].values())) == 27
    assert len(re.findall(r'data-audit-status="A\d+"', document)) == 27
    for fid, number in mapping['issues'].items():
        assert f'https://github.com/{mapping["repository"]}/issues/{number}' in document
    assert '<article' not in document and 'src/' not in document
    assert 'localStorage' not in document and 'fetch(' not in document
