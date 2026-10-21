"""Fail-closed tests for the production Step 9 operator route.

# release-control-evidence: opslag
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from src.azure_step9_cutover_v1 import (
    BLOB_ROLE,
    Step9Error,
    activate_phase,
    assert_phase_transition,
    observe_production,
    phase_state,
)


SUBSCRIPTION = "11111111-2222-3333-4444-555555555555"
GROUP = "AI_Dataservice"
APP = "vvn-metis-console"
PRINCIPAL = "71935544-7e34-443d-8782-9221eeb08419"
STORAGE_ID = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{GROUP}/providers/Microsoft.Storage/storageAccounts/aidataservice"
CONTAINER_SCOPE = f"{STORAGE_ID}/blobServices/default/containers/canonical-sources"


class FakeCli:
    def __init__(self, *, active_subscription: str = SUBSCRIPTION, flags: dict[str, str] | None = None) -> None:
        self.active_subscription = active_subscription
        self.flags = dict(flags or {})
        self.calls: list[list[str]] = []

    def json(self, arguments: Sequence[str]) -> Any:
        args = list(arguments)
        self.calls.append(args)
        if args[:2] == ["account", "show"]:
            return {"id": self.active_subscription, "name": "Microsoft Azure"}
        if args[:2] == ["group", "show"]:
            return {"name": GROUP}
        if args[:2] == ["webapp", "show"]:
            return {
                "name": APP,
                "defaultHostName": f"{APP}.azurewebsites.net",
                "identity": {"principalId": PRINCIPAL},
            }
        if args[:4] == ["webapp", "config", "appsettings", "list"]:
            values = {
                "WEB_CONCURRENCY": "1",
                "CONSOLE_INSTANCE_COUNT": "1",
                "METIS_CANONICAL_STORE": "postgres",
                "METIS_CANONICAL_DB_HOST": "metis-db.postgres.database.azure.com",
                "METIS_CANONICAL_DB_NAME": "metis",
                "METIS_CANONICAL_DB_USER": APP,
                "CONSOLE_IMMUTABLE_SOURCE_STORE": "azure",
                "G2_STORAGE_ACCOUNT": "aidataservice",
                "G2_BLOB_CONTAINER": "canonical-sources",
                "UNRELATED_SECRET": "must-not-appear",
                **self.flags,
            }
            return [{"name": key, "value": value} for key, value in values.items()]
        if args[:2] == ["provider", "show"]:
            return {"registrationState": "Registered"}
        if args[:3] == ["storage", "account", "show"]:
            return {"id": STORAGE_ID, "name": "aidataservice"}
        if args[:3] == ["storage", "container", "show"]:
            return {"name": "canonical-sources"}
        if args[:3] == ["role", "assignment", "list"]:
            return [{"roleDefinitionName": BLOB_ROLE, "scope": CONTAINER_SCOPE}]
        if args[:3] == ["postgres", "flexible-server", "list"]:
            return [
                {
                    "name": "metis-db",
                    "resourceGroup": GROUP,
                    "fullyQualifiedDomainName": "metis-db.postgres.database.azure.com",
                }
            ]
        if args[:4] == ["webapp", "config", "appsettings", "set"]:
            setting = args[args.index("--settings") + 1]
            name, value = setting.split("=", 1)
            self.flags[name] = value
            return [{"name": name, "value": value}]
        if args[:2] == ["webapp", "restart"]:
            return None
        raise AssertionError(args)


def test_read_only_preflight_resolves_exact_existing_authorities_without_secret_output() -> None:
    cli = FakeCli()
    report = observe_production(
        cli,
        subscription_id=SUBSCRIPTION,
        resource_group=GROUP,
        webapp=APP,
    )
    assert report["status"] == "PASS"
    assert report["mutation"] == "none"
    assert report["selection"]["postgres_server"] == "metis-db"
    assert report["selection"]["blob_scope"] == CONTAINER_SCOPE
    assert "must-not-appear" not in str(report)
    assert not any("set" in call[:4] or "create" in call[:4] or "delete" in call[:4] for call in cli.calls)


def test_preflight_blocks_when_active_subscription_differs() -> None:
    report = observe_production(
        FakeCli(active_subscription="wrong"),
        subscription_id=SUBSCRIPTION,
        resource_group=GROUP,
        webapp=APP,
    )
    assert report["status"] == "BLOCKED"
    check = next(row for row in report["checks"] if row["name"] == "active_subscription")
    assert check["status"] == "BLOCKED"


def test_workflow_flags_must_be_a_prefix_in_fixed_dependency_order() -> None:
    assert phase_state({"METIS_WORKFLOW_STORE": "postgres"}) == {
        "identity": "postgres",
        "documents": "inactive",
        "review": "inactive",
        "remaining": "inactive",
    }
    with pytest.raises(Step9Error, match="workflow_phase_order_invalid"):
        phase_state({"METIS_WORKFLOW_DOCUMENT_STORE": "postgres"})
    with pytest.raises(Step9Error, match="workflow_phase_prerequisite_missing:documents"):
        assert_phase_transition({"METIS_WORKFLOW_STORE": "postgres"}, "review")


def test_activation_changes_one_setting_restarts_and_never_auto_rolls_back() -> None:
    cli = FakeCli(flags={"METIS_WORKFLOW_STORE": "postgres"})
    result = activate_phase(
        cli,
        subscription_id=SUBSCRIPTION,
        resource_group=GROUP,
        webapp=APP,
        phase_name="documents",
        confirmation=f"{SUBSCRIPTION}/{GROUP}/{APP}/documents",
        health_probe=lambda _url: {"status": "BLOCKED", "error": "http_503"},
    )
    assert result["status"] == "BLOCKED"
    assert result["setting_changed"] == {"METIS_WORKFLOW_DOCUMENT_STORE": "postgres"}
    assert result["automatic_rollback"] is False
    set_calls = [call for call in cli.calls if call[:4] == ["webapp", "config", "appsettings", "set"]]
    assert len(set_calls) == 1
    assert "METIS_WORKFLOW_DOCUMENT_STORE=postgres" in set_calls[0]
    assert sum(call[:2] == ["webapp", "restart"] for call in cli.calls) == 1


def test_activation_requires_exact_target_and_phase_confirmation() -> None:
    with pytest.raises(Step9Error, match="phase_confirmation_mismatch"):
        activate_phase(
            FakeCli(),
            subscription_id=SUBSCRIPTION,
            resource_group=GROUP,
            webapp=APP,
            phase_name="identity",
            confirmation="yes",
            health_probe=lambda _url: {"status": "PASS"},
        )
