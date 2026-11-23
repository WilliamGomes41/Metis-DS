#!/usr/bin/env python3
"""Check a G1 API snapshot or print a scoped PUT plan without making API writes."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

POLICY = Path(__file__).resolve().parents[1] / "config/github_merge_policy.v1.json"
WRITABLE = ("name", "target", "enforcement", "conditions", "rules", "bypass_actors")


def rule_parameters(snapshot: dict, policy: dict) -> tuple[dict, dict]:
    if policy["version"] != 1:
        raise ValueError("unsupported policy version")
    if (snapshot["id"], snapshot["source"], snapshot["source_type"]) != (
        policy["ruleset_id"], policy["repository"], "Repository"
    ):
        raise ValueError("snapshot is not the configured repository ruleset")
    if snapshot["target"] != "branch" or snapshot["enforcement"] != "active":
        raise ValueError("G1 must already be an active branch ruleset")
    if snapshot["conditions"] != {
        "ref_name": {"include": ["refs/heads/main"], "exclude": []}
    }:
        raise ValueError("G1 must cover main without exclusions")
    if snapshot["bypass_actors"] != []:
        raise ValueError("G1 has bypass actors; reconcile explicitly before planning")
    rules = snapshot["rules"]
    for kind in ("deletion", "non_fast_forward", "required_status_checks", "pull_request"):
        if sum(rule["type"] == kind for rule in rules) != 1:
            raise ValueError(f"G1 must contain exactly one {kind} rule")
    checks = next(r["parameters"] for r in rules if r["type"] == "required_status_checks")
    review = next(r["parameters"] for r in rules if r["type"] == "pull_request")
    contexts = [c["context"] for c in checks["required_status_checks"]]
    if len(contexts) != len(set(contexts)):
        raise ValueError("duplicate required check contexts")
    return checks, review


def validate_ruleset(snapshot: dict, policy: dict) -> list[str]:
    checks, review = rule_parameters(snapshot, policy)
    errors = []
    if checks["strict_required_status_checks_policy"] is not True:
        errors.append("required checks must require an up-to-date branch")
    if checks["do_not_enforce_on_create"] is not False:
        errors.append("required checks must also apply on branch creation")
    current = {c["context"]: c for c in checks["required_status_checks"]}
    for expected in policy["required_status_checks"]:
        name = expected["context"]
        if name not in current:
            errors.append(f"missing required check: {name}")
        elif current[name].get("integration_id") != expected["integration_id"]:
            errors.append(f"required check must come from GitHub Actions: {name}")
    for retired in policy.get("retired_status_checks", []):
        if retired["context"] in current:
            errors.append(f"retired check is still required: {retired['context']}")
    if review["required_review_thread_resolution"] is not True:
        errors.append("review threads must be resolved")
    return errors


def plan_ruleset(snapshot: dict, policy: dict, *, retire_legacy_test_checks: bool = False) -> dict:
    planned = deepcopy(snapshot)
    checks, review = rule_parameters(planned, policy)
    checks["strict_required_status_checks_policy"] = True
    checks["do_not_enforce_on_create"] = False
    current = {c["context"]: c for c in checks["required_status_checks"]}
    for expected in policy["required_status_checks"]:
        existing = current.get(expected["context"])
        if existing is None:
            checks["required_status_checks"].append(deepcopy(expected))
        elif existing.get("integration_id") not in (None, expected["integration_id"]):
            raise ValueError(f"unexpected check integration: {expected['context']}")
        else:
            existing["integration_id"] = expected["integration_id"]
    if retire_legacy_test_checks:
        retired = {
            check["context"]: check["integration_id"] for check in policy["retired_status_checks"]
        }
        for name, integration in retired.items():
            if name in current and current[name].get("integration_id") != integration:
                raise ValueError(f"unexpected legacy check integration: {name}")
        checks["required_status_checks"] = [
            check for check in checks["required_status_checks"] if check["context"] not in retired
        ]
    review["required_review_thread_resolution"] = True
    return {key: planned[key] for key in WRITABLE}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ruleset", type=Path, required=True, help="fresh GitHub GET response")
    parser.add_argument("--plan", action="store_true", help="print PUT JSON; never apply it")
    parser.add_argument(
        "--retire-legacy-test-checks", action="store_true",
        help="explicitly replace the two verified legacy contexts in a cutover plan",
    )
    args = parser.parse_args(argv)
    if args.retire_legacy_test_checks and not args.plan:
        parser.error("--retire-legacy-test-checks requires --plan")
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        snapshot = json.loads(args.ruleset.read_text(encoding="utf-8"))
        if args.plan:
            payload = plan_ruleset(snapshot, policy, retire_legacy_test_checks=args.retire_legacy_test_checks)
            print(json.dumps(payload, indent=2))
            print("PLAN ONLY: apply separately, then GET and validate live state.", file=sys.stderr)
            return 0
        errors = validate_ruleset(snapshot, policy)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(f"FAIL: invalid ruleset or policy: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: supplied ruleset snapshot meets G1 policy; freshness is caller-owned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
