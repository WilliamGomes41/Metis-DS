from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.g2_azure_preflight import (
    EXPECTED_IDENTITY,
    REQUIRED_ROLE,
    REQUIRED_SCOPE,
    AzureObservation,
    RoleAssignmentView,
    run_g2_azure_preflight,
    scope_matches_required,
)
from src.g2_source_store import (
    AzureBlobSourceStore,
    G2SourceStoreError,
    g2_gate_status,
    load_g2_store,
)

ROOT = Path(__file__).resolve().parents[1]


def _present_observation() -> AzureObservation:
    return AzureObservation(
        container_present=True,
        identity_name=EXPECTED_IDENTITY,
        role_assignments=(
            RoleAssignmentView(
                principal=EXPECTED_IDENTITY,
                role=REQUIRED_ROLE,
                scope=REQUIRED_SCOPE,
            ),
        ),
    )


def test_config_declares_expected_identity_role_and_activation() -> None:
    store = load_g2_store()
    assert store["expected_managed_identity"] == EXPECTED_IDENTITY
    assert store["required_rbac_role"] == REQUIRED_ROLE
    assert store["required_rbac_scope"] == REQUIRED_SCOPE
    assert store["activation_app_setting"] == "CONSOLE_IMMUTABLE_SOURCE_STORE"
    assert store["activation_app_setting_value"] == "azure"
    assert store["g2_status"] == "BLOCKED"
    assert g2_gate_status() == "BLOCKED"


def test_preflight_never_claims_g2_pass_when_infra_looks_ready() -> None:
    report = run_g2_azure_preflight(
        observation=_present_observation(),
        environ={"CONSOLE_IMMUTABLE_SOURCE_STORE": "azure"},
        sdk_available=True,
    )
    assert report.report_only is True
    assert report.mutates is False
    assert report.g2_pass is False
    assert report.g2_status == "BLOCKED"
    assert report.ready_for_later_activation is True
    assert report.fail_closed is False
    names = {item.name: item.status for item in report.checks}
    assert names["azure_sdk"] == "present"
    assert names["container"] == "present"
    assert names["managed_identity"] == "match"
    assert names["rbac"] == "present"
    assert names["activation_app_setting"] == "active"


def test_preflight_fail_closed_missing_sdk() -> None:
    report = run_g2_azure_preflight(
        observation=_present_observation(),
        environ={"CONSOLE_IMMUTABLE_SOURCE_STORE": "azure"},
        sdk_available=False,
    )
    assert report.fail_closed is True
    assert report.ready_for_later_activation is False
    assert "azure_blob_sdk_missing" in report.blockers
    assert report.g2_pass is False
    assert report.g2_status == "BLOCKED"
    sdk = next(item for item in report.checks if item.name == "azure_sdk")
    assert sdk.status == "absent"
    assert sdk.ok is False


def test_preflight_fail_closed_missing_rbac() -> None:
    report = run_g2_azure_preflight(
        observation=AzureObservation(
            container_present=True,
            identity_name=EXPECTED_IDENTITY,
            role_assignments=(),
        ),
        environ={"CONSOLE_IMMUTABLE_SOURCE_STORE": "azure"},
        sdk_available=True,
    )
    assert report.fail_closed is True
    assert "g2_rbac_absent" in report.blockers
    rbac = next(item for item in report.checks if item.name == "rbac")
    assert rbac.status == "absent"
    assert rbac.detail["scope"] == REQUIRED_SCOPE
    assert report.g2_pass is False


def test_preflight_ignores_rbac_on_broader_scope() -> None:
    report = run_g2_azure_preflight(
        observation=AzureObservation(
            container_present=True,
            identity_name=EXPECTED_IDENTITY,
            role_assignments=(
                RoleAssignmentView(
                    principal=EXPECTED_IDENTITY,
                    role=REQUIRED_ROLE,
                    scope="aidataservice",
                ),
            ),
        ),
        environ={"CONSOLE_IMMUTABLE_SOURCE_STORE": "azure"},
        sdk_available=True,
    )
    assert "g2_rbac_absent" in report.blockers
    assert scope_matches_required("aidataservice") is False
    assert scope_matches_required(
        "/subscriptions/x/resourceGroups/AI_Dataservice/providers/Microsoft.Storage"
        "/storageAccounts/aidataservice/blobServices/default/containers/canonical-sources"
    )


def test_preflight_fail_closed_missing_config(tmp_path: Path) -> None:
    report = run_g2_azure_preflight(
        observation=_present_observation(),
        environ={"CONSOLE_IMMUTABLE_SOURCE_STORE": "azure"},
        config_path=tmp_path / "missing.json",
        sdk_available=True,
    )
    assert report.fail_closed is True
    assert "g2_config_missing" in report.blockers
    assert report.g2_status == "BLOCKED"
    assert report.g2_pass is False


def test_preflight_fail_closed_inactive_activation_setting() -> None:
    report = run_g2_azure_preflight(
        observation=_present_observation(),
        environ={},
        sdk_available=True,
    )
    assert report.fail_closed is True
    assert "g2_activation_inactive" in report.blockers
    setting = next(item for item in report.checks if item.name == "activation_app_setting")
    assert setting.status == "inactive"
    assert report.g2_pass is False
    assert report.mutates is False


def test_preflight_fail_closed_invalid_config(tmp_path: Path) -> None:
    path = tmp_path / "g2.json"
    path.write_text("{", encoding="utf-8")
    report = run_g2_azure_preflight(
        observation=_present_observation(),
        environ={"CONSOLE_IMMUTABLE_SOURCE_STORE": "azure"},
        config_path=path,
        sdk_available=True,
    )
    assert "g2_config_invalid" in report.blockers
    assert report.fail_closed is True


def test_adapter_fail_closed_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> tuple[object, object]:
        raise G2SourceStoreError("azure_blob_sdk_missing")

    monkeypatch.setattr("src.g2_source_store.load_azure_blob_sdk", boom)
    with pytest.raises(G2SourceStoreError, match="azure_blob_sdk_missing"):
        AzureBlobSourceStore()


def test_pyproject_and_lock_files_pin_the_same_azure_sdk() -> None:
    pins = ("azure-identity==1.25.3", "azure-storage-blob==12.30.1")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    dev_lock = (ROOT / "requirements-dev.lock").read_text(encoding="utf-8")
    for pin in pins:
        assert pin in pyproject
        assert pin in lock
        assert pin in requirements
    assert "-r requirements.lock" in dev_lock


def test_activation_runbook_is_docs_only() -> None:
    text = (ROOT / "docs" / "G2_BLOB_ACTIVATION_RUNBOOK.md").read_text(encoding="utf-8")
    assert "not a live flip" in text.replace("*", "").lower()
    assert "Storage Blob Data Contributor" in text
    assert "vvn-metis-console" in text
    assert "aidataservice/canonical-sources" in text
    assert "CONSOLE_IMMUTABLE_SOURCE_STORE=azure" in text
    assert "Wait for RBAC" in text or "Wait for RBAC propagation" in text
    assert "Restart" in text
    assert "NEVER" in text and "delete" in text.lower()
    assert "Do not store storage keys" in text or "Do not store storage keys, connection strings or SAS" in text
    assert "SMOKE_INERT" in text
    assert "G2 remains **BLOCKED**" in text
    assert "publish()" in text


def test_roadmap_and_changelog_record_readiness_not_pass() -> None:
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "de Azure Blob-adapter bestaat" in roadmap
    assert "azure-identity==1.25.3" in roadmap
    assert "canonical-sources` is leeg" in roadmap
    assert "G2 blijft BLOCKED" in roadmap
    assert "publish()` blijft fail-closed" in roadmap
    assert "G0 Azure DEV blijft BLOCKED" in roadmap
    assert "G2-readiness (not G2 PASS)" in changelog
    assert "inert synthetic SHA-256 smoke" in changelog
    assert "G2 remains BLOCKED" in changelog
