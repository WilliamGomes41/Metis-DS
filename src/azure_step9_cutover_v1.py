"""Fail-closed Azure observations and phased workflow cut-over controls.

The module deliberately separates read-only discovery from mutation.  It never
creates Azure resources, changes RBAC, writes Blob data, or modifies database
contents.  The only supported mutation is enabling one already-prepared
workflow store setting followed by an App Service restart.
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


POSTGRES_PROVIDER = "Microsoft.DBforPostgreSQL"
BLOB_ROLE = "Storage Blob Data Contributor"
CANONICAL_SETTINGS = (
    "METIS_CANONICAL_STORE",
    "METIS_CANONICAL_DB_HOST",
    "METIS_CANONICAL_DB_NAME",
    "METIS_CANONICAL_DB_USER",
)
@dataclass(frozen=True)
class WorkflowPhase:
    name: str
    setting: str


WORKFLOW_PHASES = (
    WorkflowPhase("identity", "METIS_WORKFLOW_STORE"),
    WorkflowPhase("documents", "METIS_WORKFLOW_DOCUMENT_STORE"),
    WorkflowPhase("review", "METIS_WORKFLOW_REVIEW_STORE"),
    WorkflowPhase("remaining", "METIS_WORKFLOW_REMAINING_STORE"),
)
class Step9Error(RuntimeError):
    """A fail-closed precondition or Azure operation failure."""


class AzureCli:
    """Small Azure CLI adapter whose JSON boundary is easy to test."""

    def __init__(self, executable: str = "az") -> None:
        self.executable = executable

    def json(self, arguments: Sequence[str]) -> Any:
        command = [self.executable, *arguments, "--output", "json", "--only-show-errors"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise Step9Error(f"azure_command_failed:{arguments[0]}:{detail[:500]}")
        try:
            return json.loads(result.stdout or "null")
        except json.JSONDecodeError as exc:
            raise Step9Error(f"azure_command_invalid_json:{arguments[0]}") from exc


def _setting_map(rows: Any) -> dict[str, str]:
    if not isinstance(rows, list):
        raise Step9Error("azure_app_settings_invalid")
    return {
        str(row.get("name") or ""): str(row.get("value") or "")
        for row in rows
        if isinstance(row, dict) and row.get("name")
    }


def phase_state(settings: Mapping[str, str]) -> dict[str, str]:
    """Validate that workflow settings form a postgres prefix, never a gap."""
    state: dict[str, str] = {}
    inactive_seen = False
    for phase in WORKFLOW_PHASES:
        value = str(settings.get(phase.setting, "") or "").strip().lower()
        if value not in ("", "postgres"):
            raise Step9Error(f"unsupported_workflow_setting:{phase.setting}")
        if value == "postgres" and inactive_seen:
            raise Step9Error(f"workflow_phase_order_invalid:{phase.setting}")
        if not value:
            inactive_seen = True
        state[phase.name] = value or "inactive"
    return state


def assert_phase_transition(settings: Mapping[str, str], phase_name: str) -> WorkflowPhase:
    state = phase_state(settings)
    try:
        index = next(i for i, phase in enumerate(WORKFLOW_PHASES) if phase.name == phase_name)
    except StopIteration as exc:
        raise Step9Error(f"unknown_workflow_phase:{phase_name}") from exc
    phase = WORKFLOW_PHASES[index]
    if state[phase.name] == "postgres":
        raise Step9Error(f"workflow_phase_already_active:{phase.name}")
    for required in WORKFLOW_PHASES[:index]:
        if state[required.name] != "postgres":
            raise Step9Error(f"workflow_phase_prerequisite_missing:{required.name}")
    for later in WORKFLOW_PHASES[index + 1 :]:
        if state[later.name] != "inactive":
            raise Step9Error(f"workflow_phase_order_invalid:{later.setting}")
    return phase


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {"name": name, "status": "PASS" if passed else "BLOCKED", "detail": detail}


def _host_matches(server: Mapping[str, Any], expected_host: str) -> bool:
    fqdn = str(server.get("fullyQualifiedDomainName") or "").strip().lower().rstrip(".")
    name = str(server.get("name") or "").strip().lower()
    expected = expected_host.strip().lower().rstrip(".")
    return fqdn == expected or (name and expected == f"{name}.postgres.database.azure.com")


def observe_production(
    cli: AzureCli,
    *,
    subscription_id: str,
    resource_group: str,
    webapp: str,
) -> dict[str, Any]:
    """Observe the selected production path without changing Azure."""
    account = cli.json(["account", "show"])
    active_id = str(account.get("id") or "") if isinstance(account, dict) else ""
    group = cli.json(
        ["group", "show", "--subscription", subscription_id, "--name", resource_group]
    )
    app = cli.json(
        [
            "webapp",
            "show",
            "--subscription",
            subscription_id,
            "--resource-group",
            resource_group,
            "--name",
            webapp,
        ]
    )
    rows = cli.json(
        [
            "webapp",
            "config",
            "appsettings",
            "list",
            "--subscription",
            subscription_id,
            "--resource-group",
            resource_group,
            "--name",
            webapp,
        ]
    )
    settings = _setting_map(rows)
    provider = cli.json(
        ["provider", "show", "--subscription", subscription_id, "--namespace", POSTGRES_PROVIDER]
    )

    storage_name = settings.get("G2_STORAGE_ACCOUNT", "").strip()
    container = settings.get("G2_BLOB_CONTAINER", "").strip()
    storage: Mapping[str, Any] = {}
    container_row: Mapping[str, Any] = {}
    assignments: list[Mapping[str, Any]] = []
    principal_id = str(((app.get("identity") or {}) if isinstance(app, dict) else {}).get("principalId") or "")
    if storage_name:
        storage = cli.json(
            ["storage", "account", "show", "--subscription", subscription_id, "--name", storage_name]
        )
    if storage and container:
        container_row = cli.json(
            [
                "storage",
                "container",
                "show",
                "--subscription",
                subscription_id,
                "--account-name",
                storage_name,
                "--name",
                container,
                "--auth-mode",
                "login",
            ]
        )
    storage_id = str(storage.get("id") or "")
    container_scope = (
        f"{storage_id}/blobServices/default/containers/{container}" if storage_id and container else ""
    )
    if principal_id and container_scope:
        raw_assignments = cli.json(
            [
                "role",
                "assignment",
                "list",
                "--subscription",
                subscription_id,
                "--assignee-object-id",
                principal_id,
                "--scope",
                container_scope,
                "--all",
            ]
        )
        if isinstance(raw_assignments, list):
            assignments = [row for row in raw_assignments if isinstance(row, dict)]

    servers: list[Mapping[str, Any]] = []
    if str(provider.get("registrationState") or "") == "Registered":
        raw_servers = cli.json(["postgres", "flexible-server", "list", "--subscription", subscription_id])
        if isinstance(raw_servers, list):
            servers = [row for row in raw_servers if isinstance(row, dict)]

    db_host = settings.get("METIS_CANONICAL_DB_HOST", "").strip()
    matching_servers = [row for row in servers if _host_matches(row, db_host)] if db_host else []
    exact_blob_role = any(
        str(row.get("roleDefinitionName") or "") == BLOB_ROLE
        and str(row.get("scope") or "").lower().rstrip("/") == container_scope.lower().rstrip("/")
        for row in assignments
    )

    checks = [
        _check("active_subscription", active_id == subscription_id, active_id or "not_logged_in"),
        _check("resource_group", str(group.get("name") or "") == resource_group, str(group.get("name") or "missing")),
        _check("production_webapp", str(app.get("name") or "") == webapp, str(app.get("name") or "missing")),
        _check("system_managed_identity", bool(principal_id), principal_id or "missing"),
        _check("single_worker", settings.get("WEB_CONCURRENCY") == "1", settings.get("WEB_CONCURRENCY", "missing")),
        _check("single_instance", settings.get("CONSOLE_INSTANCE_COUNT") == "1", settings.get("CONSOLE_INSTANCE_COUNT", "missing")),
        _check("canonical_store", settings.get("METIS_CANONICAL_STORE", "").lower() == "postgres", settings.get("METIS_CANONICAL_STORE", "missing")),
        _check("canonical_db_coordinates", all(settings.get(name, "").strip() for name in CANONICAL_SETTINGS[1:]), "configured" if all(settings.get(name, "").strip() for name in CANONICAL_SETTINGS[1:]) else "incomplete"),
        _check("postgres_provider", str(provider.get("registrationState") or "") == "Registered", str(provider.get("registrationState") or "unknown")),
        _check("postgres_server_unique", len(matching_servers) == 1, str(len(matching_servers))),
        _check("immutable_source_store", settings.get("CONSOLE_IMMUTABLE_SOURCE_STORE", "").lower() == "azure", settings.get("CONSOLE_IMMUTABLE_SOURCE_STORE", "missing")),
        _check("blob_container", bool(container_row), f"{storage_name}/{container}" if container_row else "missing_or_unreadable"),
        _check("blob_role_exact_scope", exact_blob_role, container_scope or "scope_unresolved"),
    ]
    try:
        workflow_state = phase_state(settings)
        checks.append(_check("workflow_phase_order", True, json.dumps(workflow_state, sort_keys=True)))
    except Step9Error as exc:
        workflow_state = {}
        checks.append(_check("workflow_phase_order", False, str(exc)))

    selected_server = matching_servers[0] if len(matching_servers) == 1 else {}
    return {
        "status": "PASS" if all(row["status"] == "PASS" for row in checks) else "BLOCKED",
        "mutation": "none",
        "selection": {
            "subscription_id": active_id,
            "subscription_name": str(account.get("name") or ""),
            "resource_group": str(group.get("name") or ""),
            "webapp": str(app.get("name") or ""),
            "webapp_hostname": str(app.get("defaultHostName") or ""),
            "managed_identity_principal_id": principal_id,
            "postgres_server": str(selected_server.get("name") or ""),
            "postgres_resource_group": str(selected_server.get("resourceGroup") or ""),
            "postgres_host": db_host,
            "postgres_database": settings.get("METIS_CANONICAL_DB_NAME", ""),
            "postgres_runtime_user": settings.get("METIS_CANONICAL_DB_USER", ""),
            "storage_account": storage_name,
            "blob_container": container,
            "blob_scope": container_scope,
        },
        "workflow_phases": workflow_state,
        "checks": checks,
    }


def health_url(report: Mapping[str, Any]) -> str:
    host = str((report.get("selection") or {}).get("webapp_hostname") or "").strip()
    if not host:
        raise Step9Error("webapp_hostname_missing")
    return f"https://{host}/health"


def wait_for_health(
    url: str,
    *,
    attempts: int = 18,
    delay_seconds: float = 5.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "metis-step9/1"})
            with opener(request, timeout=15) as response:
                body = response.read().decode("utf-8", errors="replace")
                status = int(getattr(response, "status", 200))
            if 200 <= status < 300:
                return {"status": "PASS", "http_status": status, "attempt": attempt, "body": body[:2000]}
            last_error = f"http_{status}"
        except (OSError, urllib.error.URLError) as exc:
            last_error = type(exc).__name__
        if attempt < attempts:
            time.sleep(delay_seconds)
    return {"status": "BLOCKED", "attempt": attempts, "error": last_error or "health_unavailable"}


def activate_phase(
    cli: AzureCli,
    *,
    subscription_id: str,
    resource_group: str,
    webapp: str,
    phase_name: str,
    confirmation: str,
    health_probe: Callable[[str], dict[str, Any]] = wait_for_health,
) -> dict[str, Any]:
    """Enable exactly one workflow flag, restart, and wait for health."""
    report = observe_production(
        cli,
        subscription_id=subscription_id,
        resource_group=resource_group,
        webapp=webapp,
    )
    if report["status"] != "PASS":
        raise Step9Error("azure_preflight_blocked")
    rows = cli.json(
        ["webapp", "config", "appsettings", "list", "--subscription", subscription_id, "--resource-group", resource_group, "--name", webapp]
    )
    phase = assert_phase_transition(_setting_map(rows), phase_name)
    expected = f"{subscription_id}/{resource_group}/{webapp}/{phase.name}"
    if confirmation != expected:
        raise Step9Error("phase_confirmation_mismatch")
    cli.json(
        ["webapp", "config", "appsettings", "set", "--subscription", subscription_id, "--resource-group", resource_group, "--name", webapp, "--settings", f"{phase.setting}=postgres"]
    )
    cli.json(
        ["webapp", "restart", "--subscription", subscription_id, "--resource-group", resource_group, "--name", webapp]
    )
    health = health_probe(health_url(report))
    result = {
        "status": "PASS" if health.get("status") == "PASS" else "BLOCKED",
        "phase": phase.name,
        "setting_changed": {phase.setting: "postgres"},
        "automatic_rollback": False,
        "health": health,
    }
    if result["status"] != "PASS":
        result["operator_action"] = "stop_and_analyse;do_not_change_later_phases"
    return result
