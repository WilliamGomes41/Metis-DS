"""Classify retained D5 native lifecycle observations with Bend, without product imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PHASES = ["startup", "accounts-and-session", "ingest-v1", "review-v1-four-eyes", "publish-v1",
          "build-app-startup", "successor-v2", "review-v2-four-eyes", "publish-v2", "successor-v3",
          "withdraw", "restart", "resume-successor", "ingest-delete", "delete-unpublished"]


def capture(inputs):
    observations = []
    for specification in inputs:
        version, path = specification.split('=', 1)
        data = Path(path).read_bytes()
        root = ET.fromstring(data)
        passed = not list(root.iter('failure')) and not list(root.iter('error')) and not list(root.iter('skipped'))
        cases = [case for case in root.iter('testcase') if case.get('name', '').startswith('test_pg_console_without_disk_mirrors[')]
        assert len(cases) == 2, 'Durable and Azure lifecycle evidence required'
        kinds = set()
        for case in cases:
            kind = case.get('name').split('[')[1].rstrip(']')
            kinds.add(kind)
            props = [p for p in case.iter('property') if p.get('name') == 'pg_mirror_map']
            assert len(props) == 1
            reports = json.loads(props[0].get('value'))
            assert set(reports) == {'control', 'guarded', 'poisoned'}
            for mode, report in reports.items():
                completed = report['completed']
                observations.append(dict(python=version, console=kind, mode=mode,
                    outcome='pass' if passed and not report.get('blocked') else 'fail',
                    accesses=sum(row['count'] for row in report['accesses']),
                    phases=[phase in completed for phase in PHASES],
                    exact_phases=completed == PHASES, junit_sha256=hashlib.sha256(data).hexdigest()))
        assert kinds == {'durable', 'azure'}
    assert {row['python'] for row in observations} == {'3.12', '3.13'}
    return dict(required_phases=PHASES, observations=observations,
        limits='Supplied JUnit classification only; not exhaustive I/O, Python correctness or merge/deploy approval')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--junit', action='append', help='Capture PYTHON=PATH (both 3.12 and 3.13 required)')
    args = parser.parse_args()
    if args.junit:
        (HERE / 'evidence.json').write_text(json.dumps(capture(args.junit), indent=2) + '\n')
    data = (HERE / 'evidence.json').read_bytes()
    evidence = json.loads(data)
    assert len(evidence['observations']) == 12
    facts = ['import Base', 'import ./Evidence.bend as E', '', 'def results() -> List<Bool>:', '  [']
    for row in evidence['observations']:
        outcome = 'Passed' if row['outcome'] == 'pass' and row['exact_phases'] else 'Failed'
        phases = ', '.join('True{}' if value else 'False{}' for value in row['phases'])
        facts.append(f"    E.strict(E.{outcome}{{}}, {row['accesses']}, [{phases}]),")
    facts += ['  ]']
    with tempfile.TemporaryDirectory(prefix='metis-d5-bend-') as directory:
        target = Path(directory)
        for name in ('Evidence.bend', 'LAWS.bend', 'PROOF.bend'):
            shutil.copyfile(HERE / name, target / name)
        (target / 'Facts.bend').write_text('\n'.join(facts) + '\n')
        def run():
            return subprocess.run(['bend', 'PROOF.bend'], cwd=target, capture_output=True, text=True,
                env={**os.environ, 'BEND_NO_TELEMETRY': '1'}, timeout=60)
        result = run()
        report = dict(evidence_sha256=hashlib.sha256(data).hexdigest(), checker='standard Bend checker',
                      proof_exit=result.returncode, proof_output=result.stdout + result.stderr,
                      limits=evidence['limits'])
        if result.returncode or 'ALL PROOFS CHECK' not in result.stdout + result.stderr:
            print(json.dumps(report, indent=2)); return 1
        # A false PASS with one access must fail on the Boolean law, not syntax.
        with (target / 'LAWS.bend').open('a') as handle:
            handle.write('\nlaw false_clean_claim:\n  {E.strict(E.Passed{}, 1, [True{}]) == True{} : Bool}\n')
        with (target / 'PROOF.bend').open('a') as handle:
            handle.write('\ndef Laws.false_clean_claim():\n  {==}\n')
        negative = run()
        output = negative.stdout + negative.stderr
        rejected = negative.returncode != 0 and all(fragment in output for fragment in (
            'SOME PROOFS FAIL', 'false_clean_claim', 'expected : False{}', 'observed : True{}'))
        report.update(false_clean_claim_rejected=rejected, negative_output=output)
        print(json.dumps(report, indent=2))
        return 0 if rejected else 1


if __name__ == '__main__':
    raise SystemExit(main())
