#!/usr/bin/env python3
"""Compare both isolation strategies on the same committed console test portion.

The rollback experiment lives only in a detached worktree. It borrows the
existing workflow transaction boundary, leaving independent readers/canonical
commits intact so correctness failures cannot be hidden by the benchmark.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.postgres_support import ROOT, database, install_schema

PORTION = [
    'test_console_asgi', 'test_console_workspace_layout', 'test_console_settings_hub_v1',
    'test_console_ingest_names_review_labels', 'test_review_batch_atomic_postgres',
    'test_navigation_reads_postgres', 'test_review_workboard_heading_advance_postgres_v1',
]
ROLLBACK = '''@pytest.fixture
def _isolated_console_postgres(monkeypatch):
    import os
    import psycopg
    from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
    from src.workflows.workflow_transaction_v1 import _ACTIVE_CONNECTION
    config = PostgresCanonicalConfig(dsn=os.environ['METIS_TEST_POSTGRES_DSN'])
    with psycopg.connect(config.dsn, row_factory=psycopg.rows.dict_row) as connection:
        with connection.transaction(force_rollback=True):
            token = _ACTIVE_CONNECTION.set(connection)
            try:
                yield config
            finally:
                _ACTIVE_CONNECTION.reset(token)
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    ref = subprocess.check_output(['git', 'rev-parse', args.ref], cwd=ROOT, text=True).strip()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory(prefix='metis-fixture-benchmark-') as directory:
        worktree = Path(directory) / 'checkout'
        subprocess.run(['git', 'worktree', 'add', '--detach', str(worktree), ref], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
        try:
            for strategy in ('template', 'rollback'):
                if strategy == 'rollback':
                    helper = worktree / 'tests/complete_workflow_support.py'
                    source = helper.read_text()
                    node = next(n for n in ast.parse(source).body
                                if isinstance(n, ast.FunctionDef) and n.name == '_isolated_console_postgres')
                    lines = source.splitlines(keepends=True)
                    lines[min(d.lineno for d in node.decorator_list)-1:node.end_lineno] = [ROLLBACK]
                    helper.write_text(''.join(lines))
                with database(os.environ['METIS_TEST_POSTGRES_DSN']) as config:
                    if strategy == 'rollback':
                        install_schema(config.dsn)
                    xml = output.with_name(output.stem + '-' + strategy + '.xml')
                    log = xml.with_suffix('.log')
                    env = {**os.environ, 'METIS_TEST_POSTGRES_DSN': config.dsn,
                           'PGOPTIONS': '-c lock_timeout=500ms -c statement_timeout=5000ms'}
                    started = time.perf_counter()
                    with log.open('w') as stream:
                        result = subprocess.run([sys.executable, '-m', 'pytest', '-q',
                                                 *['tests/' + name + '.py' for name in PORTION],
                                                 '--junitxml=' + str(xml)], cwd=worktree, env=env,
                                                stdout=stream, stderr=subprocess.STDOUT)
                    cases = list(ET.parse(xml).iter('testcase'))
                    results[strategy] = {
                        'seconds': round(time.perf_counter()-started, 3), 'exit_code': result.returncode,
                        'tests': len(cases),
                        'failures': [c.get('classname') + '::' + c.get('name') for c in cases
                                     if c.find('failure') is not None or c.find('error') is not None],
                        'skipped': sum(c.find('skipped') is not None for c in cases),
                        'xml_sha256': hashlib.sha256(xml.read_bytes()).hexdigest(),
                    }
        finally:
            subprocess.run(['git', 'worktree', 'remove', '--force', str(worktree)], cwd=ROOT, check=True,
                           stdout=subprocess.DEVNULL)
    report = {'commit': ref, 'portion': PORTION, 'postgres_dsn_redacted': True,
              'strategies': results, 'selected': 'template',
              'decision': 'Rollback is eligible only when every existing case passes with independent readers and commits.'}
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return int(bool(results['template']['failures']) or bool(results['template']['skipped']))


if __name__ == '__main__':
    raise SystemExit(main())
