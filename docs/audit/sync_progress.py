"""Read GitHub progress into an explicitly dated HTML snapshot; never mutate issues."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

STAGES = ('In uitvoering', 'Code geverifieerd', 'Gedeployed', 'Afgerond')
ROOT = Path(__file__).resolve().parent


def status_of(issue: dict) -> str:
    body = issue.get('body') or ''
    section = re.search(r'^## Voortgang\s*\n(.*?)(?=^## |\Z)', body, re.M | re.S)
    if not section:
        return 'Status controleren'
    flags = []
    for stage in STAGES:
        matches = re.findall(r'^- \[([ xX])\] ' + re.escape(stage) + r'\s*$', section[1], re.M)
        if len(matches) != 1:
            return 'Status controleren'
        flags.append(matches[0].lower() == 'x')
    if flags != sorted(flags, reverse=True):
        return 'Status controleren'
    # Closing a code issue cannot silently certify deployment or acceptance.
    state = str(issue.get('state', '')).upper()
    if state not in ('OPEN', 'CLOSED'):
        return 'Status controleren'
    if state == 'CLOSED' and not all(flags):
        return 'Gesloten zonder acceptatie'
    return STAGES[sum(flags) - 1] if any(flags) else 'Open'


def render(document: str, mapping: dict, issues: list[dict], checked_at: str) -> str:
    expected = mapping['issues']
    by_number = {i['number']: i for i in issues}
    if len(by_number) != len(issues) or set(by_number) != set(expected.values()):
        raise ValueError('Alle gekoppelde issues moeten precies eenmaal aanwezig zijn.')
    for fid, number in expected.items():
        issue = by_number[number]
        if not re.search(r'^Audit-ID: ' + re.escape(fid) + r'\s*$', issue.get('body') or '', re.M):
            raise ValueError(f'Issue #{number} hoort niet aantoonbaar bij {fid}.')
        pattern = r'(<span data-audit-status="' + re.escape(fid) + r'">)[^<]*(</span>)'
        document, count = re.subn(pattern, lambda m: m[1] + html.escape(status_of(issue)) + m[2], document)
        if count not in (1, 2):
            raise ValueError(f'Ontbrekend of dubbel HTML-statusveld: {fid}.')
    document, count = re.subn(r'(<time id="audit-snapshot">)[^<]*(</time>)',
                               lambda m: m[1] + html.escape(checked_at) + m[2], document)
    if count != 1:
        raise ValueError('Peildatum ontbreekt of is dubbel.')
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, default=ROOT / 'metis-codeaudit-voortgang.html')
    parser.add_argument('--issues-json', type=Path, help='Optioneel: volledige gh-issue snapshots; anders alleen-lezen gh issue view.')
    args = parser.parse_args()
    mapping = json.loads((ROOT / 'issue-links.json').read_text())
    if args.issues_json:
        issues = json.loads(args.issues_json.read_text())
    else:
        issues = []
        for number in mapping['issues'].values():
            response = subprocess.run(['gh', 'issue', 'view', str(number), '--repo', mapping['repository'],
                                       '--json', 'number,body,state'], check=True, capture_output=True, text=True)
            issues.append(json.loads(response.stdout))
    updated = render(args.html.read_text(), mapping, issues,
                     datetime.now(timezone.utc).isoformat(timespec='seconds'))
    # No partial snapshot: fetch and validate all issues before changing the file.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=args.html.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(updated)
        os.replace(temporary, args.html)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    print(f'{len(issues)} issue-statussen bijgewerkt: {args.html}')


if __name__ == '__main__':
    main()
