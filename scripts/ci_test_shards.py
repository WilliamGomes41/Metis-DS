#!/usr/bin/env python3
"""Partition the complete pytest collection and require complete executed proof."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def collection_digest(nodes):
    return hashlib.sha256(json.dumps(sorted(nodes), separators=(',', ':')).encode()).hexdigest()


def distribute(files, timings, count):
    if count < 1:
        raise ValueError('shard count must be positive')
    loads = [0.0] * count
    plan = {}
    # Longest files first; the timing file is a hint, never an allowlist.
    for path in sorted(set(files), key=lambda p: (-max(float(timings.get(p, 1)), .01), p)):
        index = min(range(count), key=lambda i: (loads[i], i))
        plan[path] = index
        loads[index] += max(float(timings.get(path, 1)), .01)
    return plan


def pytest_addoption(parser):
    parser.addoption('--metis-shard-index', type=int, default=None)
    parser.addoption('--metis-shard-count', type=int, default=None)
    parser.addoption('--metis-shard-manifest', type=Path, default=None)


def pytest_configure(config):
    index, count = config.getoption('--metis-shard-index'), config.getoption('--metis-shard-count')
    if index is None or count is None or not 0 <= index < count:
        raise ValueError('require 0 <= shard index < shard count')
    config._metis_shard_finished = []


def pytest_collection_modifyitems(config, items):
    index, count = config.getoption('--metis-shard-index'), config.getoption('--metis-shard-count')
    timings = json.loads((ROOT/'config/test-suite-timings.json').read_text())['file_seconds']
    nodes = [item.nodeid for item in items]
    if len(nodes) != len(set(nodes)):
        raise ValueError('duplicate test IDs in full collection')
    files = [item.nodeid.split('::', 1)[0] for item in items]
    plan = distribute(files, timings, count)
    selected, deselected = [], []
    for item, path in zip(items, files):
        (selected if plan[path] == index else deselected).append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)
    config._metis_shard_selection = dict(shard_index=index, shard_count=count,
        collection_digest=collection_digest(nodes), collected=len(nodes),
        selected=[item.nodeid for item in selected])


class ExecutionRecorder:
    def __init__(self, config):
        self.config = config

    def pytest_runtest_logfinish(self, nodeid, location):
        self.config._metis_shard_finished.append(nodeid)


def pytest_sessionstart(session):
    session.config.pluginmanager.register(ExecutionRecorder(session.config))


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    selection = getattr(config, '_metis_shard_selection', {})
    selection.update(finished=config._metis_shard_finished, pytest_exit_code=int(exitstatus))
    path = config.getoption('--metis-shard-manifest')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(selection, indent=2)+'\n')


def merge(directory, output, *, count, python_version, commit, baseline=None):
    reports = [json.loads(path.read_text()) for path in sorted(Path(directory).rglob('result.json'))]
    if len(reports) != count or {r['shard_index'] for r in reports} != set(range(count)):
        raise ValueError('missing or duplicate shard')
    all_nodes = []
    suites = ET.Element('testsuites')
    reference = reports[0]
    for report in reports:
        if (report['commit'] != commit or '.'.join(report['python'].split('.')[:2]) != python_version
                or report['shard_count'] != count
                or report['collection_digest'] != reference['collection_digest']
                or report['collected'] != reference['collected']
                or report.get('postgres_version', 0) // 10000 != 16):
            raise ValueError('shards disagree on commit, Python, collection or PostgreSQL 16')
        if report['exit_code'] or report.get('postgres_skips') or report.get('junit_missing'):
            raise ValueError('failed or skipped PostgreSQL execution')
        if (len(report['selected']) != len(set(report['selected']))
                or sorted(report['selected']) != sorted(report['finished'])):
            raise ValueError('incomplete test execution')
        all_nodes.extend(report['selected'])
    if (len(all_nodes) != len(set(all_nodes)) or len(all_nodes) != reference['collected']
            or collection_digest(all_nodes) != reference['collection_digest']):
        raise ValueError('shards are not an exact partition of the complete collection')
    for path in sorted(Path(directory).rglob('result.json')):
        root = ET.parse(path.with_suffix('.xml')).getroot()
        if list(root.iter('failure')) or list(root.iter('error')):
            raise ValueError('JUnit contains failures despite successful shard report')
        suites.extend(deepcopy(list(root)) if root.tag == 'testsuites' else [deepcopy(root)])
    cases = list(suites.iter('testcase'))
    if not cases:
        raise ValueError('no executed JUnit evidence')
    report = dict(commit=commit, python=reference['python'],
        seconds=round(sum(r['seconds'] for r in reports), 3),
        wall_seconds=max(r['seconds'] for r in reports), exit_code=0,
        tests=len(cases), failures=0, errors=0,
        skipped=len(list(suites.iter('skipped'))), postgres_skips=[],
        postgres_version=reference['postgres_version'], collected=len(all_nodes),
        collection_digest=reference['collection_digest'], shards=reports)
    if baseline:
        before = json.loads(Path(baseline).read_text())
        report.update(baseline_seconds=before['seconds'],
            ratio=report['seconds']/before['seconds'],
            within_twice_baseline=report['seconds'] <= 2*before['seconds'])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suites).write(output.with_suffix('.xml'), encoding='utf-8', xml_declaration=True)
    output.write_text(json.dumps(report, indent=2)+'\n')
    if report.get('within_twice_baseline') is False:
        raise ValueError('summed suite cost exceeds twice baseline')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('merge')
    command.add_argument('--directory', type=Path, required=True)
    command.add_argument('--output', type=Path, required=True)
    command.add_argument('--count', type=int, required=True)
    command.add_argument('--python-version', required=True)
    command.add_argument('--commit', required=True)
    command.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    report = merge(args.directory, args.output, count=args.count, python_version=args.python_version,
                   commit=args.commit, baseline=args.baseline)
    print(json.dumps({k: v for k, v in report.items() if k != 'shards'}))


if __name__ == '__main__':
    main()
