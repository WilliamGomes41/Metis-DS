#!/usr/bin/env python3
"""Validate the machine-readable Metis Change Contract on pull requests.

The validator deliberately checks presence and consistency only. The normative
meaning of lifecycle and rewrite fields remains in docs/agents/*.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

BASE_FIELDS = (
    "Change class",
    "Promise",
    "Proof",
    "Touches lifecycle invariants",
    "Rewrite risk",
)

HIGH_RISK_FIELDS = (
    "Rewrite target",
    "Why local patching is insufficient",
    "Current authority/writer/reader map",
    "Supported runtime topologies",
    "Persisted-state impact",
    "Compatibility/migration plan",
    "Rollback/recovery plan",
    "Cutover trigger",
    "Cleanup/decommission criteria",
    "Failure blast radius",
    "Adversarial proof matrix",
)

LIFECYCLE_FIELDS = (
    "Lifecycle entity",
    "Lifecycle transition",
    "Initial durable state",
    "Trigger",
    "Authorization",
    "Validation",
    "Mutable entities",
    "Immutable entities",
    "Workflow state before",
    "Workflow state after",
    "Release state before",
    "Release state after",
    "Serving state before",
    "Serving state after",
    "Expected API result",
    "Expected UI result",
    "Failure result",
    "Restart result",
    "Recovery result",
    "Legacy-data result",
    "Required black-box scenario",
    "Explicit non-goals",
)

# Supports plain fields (`Promise: ...`) and the existing PR-template form
# (`- **Change class**: B`).
_FIELD_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\*\*)?([^:*\n]+?)(?:\*\*)?\s*:\s*(.*?)\s*$"
)


def _key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def parse_fields(text: str) -> dict[str, str]:
    """Return recognized contract fields keyed case-insensitively.

    First occurrence wins so a later prose example cannot silently override the
    contract stated at the top of the PR.
    """
    wanted = {_key(name): name for name in (*BASE_FIELDS, *HIGH_RISK_FIELDS, *LIFECYCLE_FIELDS)}
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = _FIELD_RE.match(line)
        if not match:
            continue
        canonical = wanted.get(_key(match.group(1)))
        if canonical and canonical not in fields:
            fields[canonical] = match.group(2).strip()
    return fields


def _missing(fields: dict[str, str], names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not fields.get(name, "").strip()]


def _placeholder(value: str) -> bool:
    lowered = value.strip().casefold()
    return (
        not lowered
        or lowered in {"a | b | c", "none | high", "yes | no"}
        or lowered.startswith("<") and lowered.endswith(">")
    )


def validate_change_contract(text: str) -> list[str]:
    fields = parse_fields(text)
    errors: list[str] = []

    for name in BASE_FIELDS:
        if name not in fields or _placeholder(fields[name]):
            errors.append(f"missing or placeholder field: {name}")

    if errors:
        return errors

    change_class = fields["Change class"].strip().upper()
    rewrite_risk = fields["Rewrite risk"].strip().casefold()
    touches = fields["Touches lifecycle invariants"].strip().casefold()

    if change_class not in {"A", "B", "C"}:
        errors.append("Change class must be exactly A, B, or C")
    if rewrite_risk not in {"none", "high"}:
        errors.append("Rewrite risk must be exactly none or high")
    if touches not in {"yes", "no"}:
        errors.append("Touches lifecycle invariants must be exactly yes or no")

    if change_class == "A":
        for name in _missing(fields, LIFECYCLE_FIELDS):
            errors.append(f"Class A requires lifecycle field: {name}")
        # The lifecycle contract itself requires its rewrite-risk field; the base
        # contract already supplies and validates that one value.

    if rewrite_risk == "high":
        for name in _missing(fields, HIGH_RISK_FIELDS):
            errors.append(f"high rewrite risk requires field: {name}")

    return errors


def _pr_body_from_event(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    body = payload.get("pull_request", {}).get("body")
    return body if isinstance(body, str) else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-file", type=Path, help="Validate contract text from a file")
    args = parser.parse_args(argv)

    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8")
    else:
        event_name = os.environ.get("GITHUB_EVENT_NAME", "")
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if event_name != "pull_request":
            print("Change-contract validation skipped: current event is not pull_request")
            return 0
        if not event_path:
            print("Change-contract validation failed: GITHUB_EVENT_PATH is missing", file=sys.stderr)
            return 2
        text = _pr_body_from_event(Path(event_path))

    errors = validate_change_contract(text)
    if errors:
        print("Change-contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Change-contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
