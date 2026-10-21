#!/usr/bin/env python3
"""Report-only G2 Azure Blob preflight. Never mutates. Never publish.

This script prints a JSON report. It does not grant RBAC, enable app
settings, upload or delete blobs, or call publish().
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.g2_azure_preflight import AzureObservation, RoleAssignmentView, run_g2_azure_preflight


def _observation_from_args(args: argparse.Namespace) -> AzureObservation:
    assignments = None
    if args.role_assignments_json:
        raw = json.loads(Path(args.role_assignments_json).read_text(encoding="utf-8"))
        assignments = tuple(
            RoleAssignmentView(
                principal=str(item["principal"]),
                role=str(item["role"]),
                scope=str(item["scope"]),
            )
            for item in raw
        )
    container_present = args.container_present
    if container_present is None and args.container_absent:
        container_present = False
    identity = args.identity_name or None
    return AzureObservation(
        container_present=container_present,
        identity_name=identity,
        role_assignments=assignments,
        observation_error=None if (container_present is not None or assignments is not None or identity) else "live_azure_not_queried",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Report-only G2 Azure Blob preflight. Never mutates.")
    parser.add_argument("--container-present", action="store_true", default=None, help="Stub: container is present")
    parser.add_argument("--container-absent", action="store_true", help="Stub: container is absent")
    parser.add_argument("--identity-name", help="Observed managed identity name")
    parser.add_argument("--role-assignments-json", help="Read-only JSON list of {principal, role, scope}")
    parser.add_argument("--config", type=Path, help="Override g2_source_store config path")
    args = parser.parse_args()
    if args.container_present and args.container_absent:
        print(json.dumps({"status": "BLOCKED", "error": "container_flags_conflict"}, indent=2))
        return 2
    report = run_g2_azure_preflight(
        observation=_observation_from_args(args),
        config_path=args.config,
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 2 if report.fail_closed else 0


if __name__ == "__main__":
    raise SystemExit(main())
