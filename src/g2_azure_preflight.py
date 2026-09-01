"""Report-only G2 Azure Blob readiness preflight.

Never mutates Azure, never grants roles, never enables app settings,
never uploads or deletes blobs, and never calls ``publish()``.
G2 remains BLOCKED even when every check is present.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from src.g2_source_store import (
    CONFIG_PATH,
    azure_blob_sdk_available,
    g2_gate_status,
    load_g2_store,
)

EXPECTED_IDENTITY = "vvn-metis-console"
REQUIRED_ROLE = "Storage Blob Data Contributor"
REQUIRED_SCOPE = "aidataservice/canonical-sources"
ACTIVATION_SETTING = "CONSOLE_IMMUTABLE_SOURCE_STORE"
ACTIVATION_VALUE = "azure"
ARM_CONTAINER_SCOPE_SUFFIX = (
    "/storageaccounts/aidataservice/blobservices/default/containers/canonical-sources"
)


@dataclass(frozen=True)
class RoleAssignmentView:
    """Read-only view of one role assignment. Never used to grant roles."""

    principal: str
    role: str
    scope: str


@dataclass(frozen=True)
class AzureObservation:
    """Read-only Azure facts supplied by a stub (CI) or a later live probe.

    ``None`` fields mean the fact was not observed. Missing observations
    fail closed: they do not become present.
    """

    container_present: bool | None = None
    identity_name: str | None = None
    role_assignments: tuple[RoleAssignmentView, ...] | None = None
    observation_error: str | None = None


@dataclass
class CheckResult:
    name: str
    status: str
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class G2PreflightReport:
    report_only: bool
    mutates: bool
    g2_status: str
    g2_pass: bool
    fail_closed: bool
    ready_for_later_activation: bool
    checks: list[CheckResult]
    blockers: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_only": self.report_only,
            "mutates": self.mutates,
            "g2_status": self.g2_status,
            "g2_pass": self.g2_pass,
            "fail_closed": self.fail_closed,
            "ready_for_later_activation": self.ready_for_later_activation,
            "checks": [asdict(item) for item in self.checks],
            "blockers": list(self.blockers),
            "notes": list(self.notes),
        }


def scope_matches_required(scope: str, required: str = REQUIRED_SCOPE) -> bool:
    raw = str(scope or "").strip()
    if not raw:
        return False
    if raw == required:
        return True
    return raw.lower().replace(" ", "").endswith(ARM_CONTAINER_SCOPE_SUFFIX)


def role_present_on_required_scope(
    assignments: tuple[RoleAssignmentView, ...] | None,
    *,
    identity: str = EXPECTED_IDENTITY,
    role: str = REQUIRED_ROLE,
    scope: str = REQUIRED_SCOPE,
) -> bool | None:
    if assignments is None:
        return None
    for item in assignments:
        if item.principal != identity:
            continue
        if item.role != role:
            continue
        if scope_matches_required(item.scope, scope):
            return True
    return False


def _config_coordinates(store: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(store or {})
    return {
        "expected_managed_identity": str(data.get("expected_managed_identity") or EXPECTED_IDENTITY),
        "required_rbac_role": str(data.get("required_rbac_role") or REQUIRED_ROLE),
        "required_rbac_scope": str(data.get("required_rbac_scope") or REQUIRED_SCOPE),
        "activation_app_setting": str(data.get("activation_app_setting") or ACTIVATION_SETTING),
        "activation_app_setting_value": str(data.get("activation_app_setting_value") or ACTIVATION_VALUE),
        "storage_account": str(data.get("storage_account") or ""),
        "container": str(data.get("container") or ""),
    }


def load_preflight_config(path: Path | None = None) -> tuple[dict[str, Any] | None, str | None]:
    target = path or CONFIG_PATH
    try:
        store = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "g2_config_missing"
    except (OSError, json.JSONDecodeError):
        return None, "g2_config_invalid"
    if not isinstance(store, dict):
        return None, "g2_config_invalid"
    required = ("storage_account", "container", "g2_status")
    if any(not str(store.get(key) or "").strip() for key in required):
        return None, "g2_config_incomplete"
    return store, None


def run_g2_azure_preflight(
    *,
    observation: AzureObservation | None = None,
    environ: Mapping[str, str] | None = None,
    config_path: Path | None = None,
    sdk_available: bool | None = None,
) -> G2PreflightReport:
    """Build a report-only readiness picture. Never mutates."""

    env = environ if environ is not None else os.environ
    sdk_ok = azure_blob_sdk_available() if sdk_available is None else bool(sdk_available)
    store, config_error = load_preflight_config(config_path)
    coords = _config_coordinates(store)
    observed = observation or AzureObservation()
    activation_raw = str(env.get(coords["activation_app_setting"], "")).strip()
    activation_active = activation_raw.lower() == coords["activation_app_setting_value"].lower()
    identity_expected = coords["expected_managed_identity"]
    identity_observed = observed.identity_name
    if identity_observed is None:
        website = str(env.get("WEBSITE_SITE_NAME", "")).strip()
        identity_observed = website or None
    identity_match = identity_observed == identity_expected if identity_observed else None
    rbac_present = role_present_on_required_scope(
        observed.role_assignments,
        identity=identity_expected,
        role=coords["required_rbac_role"],
        scope=coords["required_rbac_scope"],
    )

    checks: list[CheckResult] = []
    blockers: list[str] = []

    if sdk_ok:
        checks.append(CheckResult("azure_sdk", "present", True, {"packages": ["azure-identity", "azure-storage-blob"]}))
    else:
        checks.append(CheckResult("azure_sdk", "absent", False, {"error": "azure_blob_sdk_missing"}))
        blockers.append("azure_blob_sdk_missing")

    if store is None:
        checks.append(CheckResult("config", "missing" if config_error == "g2_config_missing" else "invalid", False, {"error": config_error}))
        blockers.append(config_error or "g2_config_missing")
    else:
        checks.append(
            CheckResult(
                "config",
                "present",
                True,
                {
                    "path": str(config_path or CONFIG_PATH),
                    "g2_status": str(store.get("g2_status")),
                    "storage_account": coords["storage_account"],
                    "container": coords["container"],
                },
            )
        )

    if observed.container_present is True:
        checks.append(
            CheckResult(
                "container",
                "present",
                True,
                {"scope": coords["required_rbac_scope"], "name": coords["container"]},
            )
        )
    elif observed.container_present is False:
        checks.append(CheckResult("container", "absent", False, {"scope": coords["required_rbac_scope"]}))
        blockers.append("g2_container_absent")
    else:
        checks.append(
            CheckResult(
                "container",
                "unknown",
                False,
                {"scope": coords["required_rbac_scope"], "error": observed.observation_error or "container_not_observed"},
            )
        )
        blockers.append("g2_container_unknown")

    if identity_match is True:
        checks.append(
            CheckResult(
                "managed_identity",
                "match",
                True,
                {"expected": identity_expected, "observed": identity_observed},
            )
        )
    elif identity_observed is None:
        checks.append(
            CheckResult(
                "managed_identity",
                "unknown",
                False,
                {"expected": identity_expected, "observed": None},
            )
        )
        blockers.append("g2_identity_unknown")
    else:
        checks.append(
            CheckResult(
                "managed_identity",
                "mismatch",
                False,
                {"expected": identity_expected, "observed": identity_observed},
            )
        )
        blockers.append("g2_identity_mismatch")

    if rbac_present is True:
        checks.append(
            CheckResult(
                "rbac",
                "present",
                True,
                {
                    "role": coords["required_rbac_role"],
                    "scope": coords["required_rbac_scope"],
                    "principal": identity_expected,
                },
            )
        )
    elif rbac_present is False:
        checks.append(
            CheckResult(
                "rbac",
                "absent",
                False,
                {
                    "role": coords["required_rbac_role"],
                    "scope": coords["required_rbac_scope"],
                    "principal": identity_expected,
                },
            )
        )
        blockers.append("g2_rbac_absent")
    else:
        checks.append(
            CheckResult(
                "rbac",
                "unknown",
                False,
                {
                    "role": coords["required_rbac_role"],
                    "scope": coords["required_rbac_scope"],
                    "principal": identity_expected,
                    "error": "rbac_not_observed",
                },
            )
        )
        blockers.append("g2_rbac_unknown")

    if activation_active:
        checks.append(
            CheckResult(
                "activation_app_setting",
                "active",
                True,
                {"name": coords["activation_app_setting"], "value": activation_raw},
            )
        )
    elif activation_raw:
        checks.append(
            CheckResult(
                "activation_app_setting",
                "inactive",
                False,
                {"name": coords["activation_app_setting"], "value": activation_raw},
            )
        )
        blockers.append("g2_activation_inactive")
    else:
        checks.append(
            CheckResult(
                "activation_app_setting",
                "inactive",
                False,
                {"name": coords["activation_app_setting"], "value": None},
            )
        )
        blockers.append("g2_activation_inactive")

    g2_status = g2_gate_status() if store is not None else "BLOCKED"
    unique_blockers = list(dict.fromkeys(blockers))
    ready = not unique_blockers
    notes = [
        "Report only: this preflight never grants roles, enables settings, uploads, deletes, or publishes.",
        "G2 remains BLOCKED. This is not a G2 PASS.",
        "canonical-sources is treated as empty until a SHA-256-verified source is stored and bound.",
        "publish() remains fail-closed.",
        "G0 Azure DEV remains BLOCKED.",
        "Required RBAC is evaluated on aidataservice/canonical-sources only.",
    ]
    if observed.observation_error:
        notes.append(f"observation_error={observed.observation_error}")
    return G2PreflightReport(
        report_only=True,
        mutates=False,
        g2_status=g2_status,
        g2_pass=False,
        fail_closed=not ready,
        ready_for_later_activation=ready,
        checks=checks,
        blockers=unique_blockers,
        notes=notes,
    )
