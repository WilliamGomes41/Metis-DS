#!/usr/bin/env python3
"""Measure real source preparation; a failing budget is not a production repro."""
import argparse
import json
import platform
import statistics
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter

from src.vorming.extract_html_v1 import extract
from src.vorming.prepared_source_views_v1 import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', nargs='+', type=int, default=[150, 300, 600, 1200])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--assert-budget', action='store_true',
                        help='fail if 4x input exceeds the proposed 6x median runtime')
    args = parser.parse_args()
    if len(args.sizes) < 2 or min(args.sizes) <= 0 or args.repeats < 1:
        parser.error('at least two positive sizes and one repetition are required')
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, check=True).stdout.strip())
    results = []
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'source.html'
        for continued in (False, True):
            for size in args.sizes:
                text = 'de patiënt heeft ondersteuning nodig bij dagelijkse verzorging' + ('' if continued else '.')
                source.write_text('<html><body>' + ('<p>' + text + '</p>') * size + '</body></html>', encoding='utf-8')
                fragments = extract(source, document_id='synthetic-document', source_id='synthetic-source')
                times = []
                for _ in range(args.repeats):
                    start = perf_counter()
                    prepared = prepare(fragments)
                    times.append(perf_counter() - start)
                blocks = len(prepared.fragments.blocks)
                if continued and blocks != 1:
                    raise RuntimeError('fixture no longer exercises a single continued source block')
                results.append({'continued': continued, 'fragments': len(fragments), 'blocks': blocks,
                                'samples_seconds': times, 'median_seconds': statistics.median(times)})
    print(json.dumps({'commit': commit, 'working_tree_dirty': dirty, 'python': platform.python_version(),
                      'scope': 'synthetic source preparation only; no HTTP, PostgreSQL or production data',
                      'results': results}, indent=2))
    if args.assert_budget:
        rows = [row for row in results if row['continued']]
        first, last = rows[0], rows[-1]
        if last['fragments'] != 4 * first['fragments']:
            parser.error('budget requires last size to be four times the first')
        if last['median_seconds'] > 6 * first['median_seconds']:
            raise SystemExit('RED: 4x continued fragments exceeded 6x median preparation time')


if __name__ == '__main__':
    main()
