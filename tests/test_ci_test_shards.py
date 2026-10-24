"""Scheduling must never omit tests or turn partial execution into proof.

# release-control-evidence: scope/belofte slop releasebewijs
"""
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from scripts.ci_test_shards import collection_digest, distribute, merge


def test_balances_files_and_includes_unknown_tests_once():
    files = ['tests/test_long.py', 'tests/test_short.py', 'tests/test_new.py']
    plan = distribute(files, {'tests/test_long.py': 10, 'tests/test_short.py': 2}, 2)
    assert set(plan) == set(files)
    assert plan[files[0]] != plan[files[1]]
    assert plan == distribute(reversed(files), {'tests/test_long.py': 10, 'tests/test_short.py': 2}, 2)


def shard(tmp_path, index, nodes, *, collected=None, exit_code=0):
    directory = tmp_path / f'shard-{index}'
    directory.mkdir()
    all_nodes = collected or ['tests/test_a.py::test_a', 'tests/test_b.py::test_b']
    report = dict(commit='a'*40, python='3.12.14', shard_index=index, shard_count=2,
                  collection_digest=collection_digest(all_nodes), collected=len(all_nodes),
                  selected=nodes, finished=nodes, exit_code=exit_code, seconds=2,
                  postgres_skips=[], postgres_version=160015)
    (directory / 'result.json').write_text(json.dumps(report))
    suite = ET.Element('testsuite')
    for node in nodes:
        path, name = node.split('::')
        ET.SubElement(suite, 'testcase', classname=path[:-3].replace('/', '.'), name=name, time='1')
    ET.ElementTree(suite).write(directory / 'result.xml')
    return directory


def test_merge_requires_exact_partition_and_preserves_junit(tmp_path):
    shard(tmp_path, 0, ['tests/test_a.py::test_a'])
    shard(tmp_path, 1, ['tests/test_b.py::test_b'])
    output = tmp_path / 'merged.json'
    report = merge(tmp_path, output, count=2, python_version='3.12', commit='a'*40)
    assert report['seconds'] == 4 and report['wall_seconds'] == 2
    assert report['tests'] == 2 and report['postgres_skips'] == []
    assert len(list(ET.parse(output.with_suffix('.xml')).iter('testcase'))) == 2


@pytest.mark.parametrize('corruption', ['missing', 'duplicate', 'commit', 'python', 'collection', 'unfinished', 'failed', 'pg_skip'])
def test_merge_refuses_partial_or_unrelated_execution(tmp_path, corruption):
    shard(tmp_path, 0, ['tests/test_a.py::test_a'])
    directory = shard(tmp_path, 1, ['tests/test_b.py::test_b'])
    path = directory / 'result.json'
    report = json.loads(path.read_text())
    if corruption == 'missing':
        path.unlink()
    else:
        if corruption == 'duplicate': report['selected'] = report['finished'] = ['tests/test_a.py::test_a']
        if corruption == 'commit': report['commit'] = 'b'*40
        if corruption == 'python': report['python'] = '3.13.1'
        if corruption == 'collection': report['collection_digest'] = 'wrong'
        if corruption == 'unfinished': report['finished'] = []
        if corruption == 'failed': report['exit_code'] = 1
        if corruption == 'pg_skip': report['postgres_skips'] = ['test_database']
        path.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        merge(tmp_path, tmp_path/'merged.json', count=2, python_version='3.12', commit='a'*40)


def test_digest_detects_missing_test_and_ignores_collection_order():
    assert collection_digest(['b', 'a']) == collection_digest(['a', 'b'])
    assert collection_digest(['a']) != collection_digest(['a', 'b'])


def test_actual_pytest_plugin_partitions_new_files_and_records_execution(tmp_path):
    """Run real pytest, including setup skips and xfails, outside repo fixtures."""
    (tmp_path/'pytest.ini').write_text('[pytest]\n')
    (tmp_path/'test_new_a.py').write_text('import pytest\ndef test_a(): pass\n@pytest.mark.xfail(reason="known")\ndef test_x(): assert False\n')
    (tmp_path/'test_new_b.py').write_text('import pytest\n@pytest.mark.skip(reason="optional")\ndef test_b(): pass\n')
    reports = []
    for index in range(2):
        path = tmp_path/f'selection-{index}.json'
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'scripts.ci_test_shards',
            '-c', str(tmp_path/'pytest.ini'), '--confcutdir', str(tmp_path), str(tmp_path),
            '--metis-shard-index', str(index), '--metis-shard-count', '2',
            '--metis-shard-manifest', str(path)], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout+result.stderr
        reports.append(json.loads(path.read_text()))
    assert reports[0]['collection_digest'] == reports[1]['collection_digest']
    selected = [node for r in reports for node in r['selected']]
    assert len(selected) == len(set(selected)) == 3
    assert all(sorted(r['selected']) == sorted(r['finished']) for r in reports)
