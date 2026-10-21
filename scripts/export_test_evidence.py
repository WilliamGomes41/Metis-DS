#!/usr/bin/env python3
"""Export native proof cases from the executed full suite without rerunning them."""
import argparse
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET


def export(source: Path, output: Path, modules: list[str]) -> int:
    cases = list(ET.parse(source).iter("testcase"))
    selected = []
    for module in modules:
        prefix = module.removesuffix(".py").replace("/", ".")
        matching = [case for case in cases
                    if case.get("classname", "") == prefix
                    or case.get("classname", "").startswith(prefix + ".")]
        if not matching:
            raise ValueError(f"No executed evidence for {module}")
        selected.extend(matching)
    suite = ET.Element("testsuite", name="native-proof", tests=str(len(selected)),
                       time=str(sum(float(case.get("time", "0")) for case in selected)))
    for tag, attribute in (("failure", "failures"), ("error", "errors"), ("skipped", "skipped")):
        suite.set(attribute, str(sum(case.find(tag) is not None for case in selected)))
    suite.extend(deepcopy(selected))
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(output, encoding="utf-8", xml_declaration=True)
    for case in selected:
        status = "FAILED" if case.find("failure") is not None or case.find("error") is not None else "SKIPPED" if case.find("skipped") is not None else "PASSED"
        print(f"{status} {case.get('classname')}::{case.get('name')}")
    return int(any(case.find(tag) is not None for case in selected
                   for tag in ("failure", "error", "skipped")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("modules", nargs="+")
    args = parser.parse_args()
    return export(args.source, args.output, args.modules)


if __name__ == "__main__":
    raise SystemExit(main())
