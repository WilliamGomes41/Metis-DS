"""Require the named behaviors from the already executed, commit-checked suite."""
import sys
import xml.etree.ElementTree as ET
from collections import Counter

REQUIRED = {
    "test_seven_day_consumer",
    "test_exact_release_and_recovery",
    "test_scope_and_disclosure",
    "test_publication_snapshot_during_cutover[forward]",
    "test_publication_snapshot_during_cutover[reverse]",
    "test_parallel_tenants",
    "test_access_change_during_read[revocation]",
    "test_access_change_during_read[unstable]",
    "test_authority_failure_and_restart[postgres]",
    "test_authority_failure_and_restart[blob]",
    "test_authority_failure_and_restart[access]",
    "test_limits_order_and_repeat",
    "test_check_does_not_mutate_publication_or_access",
    "test_evidence_gate_rejects_missing_variant",
}


def require_cases(root):
    cases = list(root.iter("testcase"))
    counts = Counter(c.get("name") for c in cases if c.get("classname") == "tests.test_publication_references_v1")
    missing = sorted(name for name in REQUIRED if counts[name] != 1)
    if missing:
        raise ValueError(f"Missing or duplicate publication reference evidence: {missing}")
    if any(c.find(tag) is not None for c in cases for tag in ("skipped", "error", "failure")):
        raise ValueError("Unsuccessful publication reference evidence")


if __name__ == "__main__":
    require_cases(ET.parse(sys.argv[1]).getroot())
