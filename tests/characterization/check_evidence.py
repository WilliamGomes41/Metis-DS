"""Check CI characterization evidence against coverage_baseline.json.

Usage:
  python tests/characterization/check_evidence.py coverage <coverage.json>
  python tests/characterization/check_evidence.py mutation review <exitcode> <junit.xml>

coverage: when a product file still has the baseline sha256, its executed and
missing lines/arcs within the range MUST equal the baseline exactly. When the
file changed, the line numbers no longer apply; the check warns and does not
claim coverage evidence (OPENVRAAG in the PR).
mutation: pytest MUST exit 1 with zero errors/skips, and the set of red cases
MUST equal the recorded `<name>-mutation` run.
"""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASELINE = json.loads((HERE / "coverage_baseline.json").read_text(encoding="utf-8"))


def _fail(message):
    print(f"::error::{message}")
    return 1


def check_coverage(report_path):
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))["files"]
    errors = 0
    for item in BASELINE["ranges"]:
        name, (start, end) = item["file"], item["range"]
        digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if digest != item["sha256"]:
            print(f"::warning::{name} differs from baseline {BASELINE['base'][:7]}; "
                  "range coverage NOT verified (re-measure deliberately)")
            continue
        data = report[name]
        within = lambda values: sorted(v for v in values if start <= v <= end)
        arcs = lambda values: sorted(list(a) for a in values if start <= a[0] <= end)
        actual = {
            "executed_lines": within(data["executed_lines"]),
            "missing_lines": within(data["missing_lines"]),
            "executed_arcs": arcs(data.get("executed_branches", [])),
            "missing_arcs": arcs(data.get("missing_branches", [])),
        }
        for key, value in actual.items():
            if value != sorted(item[key]):
                errors += _fail(f"{name}:{start}-{end} {key} differs from baseline")
        print(f"{name}:{start}-{end}: statements {len(actual['executed_lines'])}/"
              f"{len(actual['executed_lines']) + len(actual['missing_lines'])}, "
              f"arcs {len(actual['executed_arcs'])}/"
              f"{len(actual['executed_arcs']) + len(actual['missing_arcs'])}")
    return 1 if errors else 0


def check_mutation(name, exit_code, junit_path):
    expected = BASELINE["runs"][f"{name}-mutation"]
    if int(exit_code) != 1:
        return _fail(f"{name} mutation: pytest exit code {exit_code}, expected 1")
    root = ET.parse(junit_path).getroot()
    cases = list(root.iter("testcase"))
    red, errors, skipped = set(), 0, 0
    for case in cases:
        if case.find("error") is not None:
            errors += 1
        if case.find("skipped") is not None:
            skipped += 1
        if case.find("failure") is not None:
            red.add(case.get("classname") + "::" + case.get("name"))
    if errors or skipped:
        return _fail(f"{name} mutation: {errors} errors, {skipped} skipped; expected 0")
    if len(cases) != expected["tests"] or red != set(expected["failed_cases"]):
        return _fail(f"{name} mutation: {len(red)}/{len(cases)} red, expected "
                     f"{expected['failures']}/{expected['tests']} with the recorded cases")
    print(f"{name} mutation: {len(red)}/{len(cases)} red as recorded, exit code 1")
    return 0


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    sys.exit(check_coverage(*args) if mode == "coverage" else check_mutation(*args))
