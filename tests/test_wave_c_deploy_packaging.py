"""Protocol v2.22 wave C: finish PR #82 faults; do not activate deploy."""
from __future__ import annotations

import os
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

from src.azure_deploy_package import (
    CONSOLE_REQUIREMENTS_NAME,
    FORBIDDEN_CONSOLE_PACKAGES,
    RUNTIME_DATA_MARKERS,
    DeployPackageError,
    default_console_requirements,
    package_contains_runtime_data,
    write_deploy_zip,
)
from src.deploy_identity_v1 import (
    PRODUCTION_APP,
    TEST_APP,
    DeployIdentityError,
    assert_deploy_allowed,
    require_deploy_activation,
    storage_app_settings,
)
from src.g2_source_store import (
    build_g2_locator,
    effective_g2_store,
    g2_gate_status,
    load_g2_store,
)
from src.operations_console_v1 import OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
DIGEST = "b" * 64


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_packaging_defaults_to_console_requirements_not_retrieval_extra() -> None:
    assert default_console_requirements(ROOT) == ROOT / CONSOLE_REQUIREMENTS_NAME
    assert default_console_requirements(ROOT).is_file()
    script = _read(ROOT / "scripts" / "create_azure_deploy_package.sh")
    assert "requirements-console.txt" in script
    assert "MUST NOT vendor numpy, sklearn, scipy" in script


def test_packaging_script_is_invoked_via_bash_and_is_executable() -> None:
    script = ROOT / "scripts" / "create_azure_deploy_package.sh"
    assert script.is_file()
    text = _read(script)
    assert "#!/usr/bin/env bash" in text
    assert "git archive" not in text
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR
    for name in ("deploy-test.yml", "deploy-production.yml"):
        workflow = _read(ROOT / ".github" / "workflows" / name)
        assert "bash scripts/create_azure_deploy_package.sh" in workflow
        assert 'run: scripts/create_azure_deploy_package.sh' not in workflow


def test_packaging_produces_fully_deployable_zip_with_dependencies(tmp_path: Path) -> None:
    output = tmp_path / "metis-console.zip"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "create_azure_deploy_package.sh"), str(output)],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "METIS_PACKAGE_ROOT": str(ROOT)},
    )
    assert result.returncode == 0
    assert output.is_file()
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    assert any(name.startswith(".python_packages/") for name in names)
    assert any(name.endswith("gunicorn/__init__.py") or "/gunicorn/" in name for name in names)
    assert any("fastapi" in name for name in names)
    assert "scripts/azure_console_startup.sh" in names
    assert "src/console_asgi.py" in names
    assert "requirements.txt" in names
    assert CONSOLE_REQUIREMENTS_NAME in names
    assert "requirements-retrieval.txt" not in names
    assert not any(package_contains_runtime_data(name) for name in names)
    assert not any("git archive" in name for name in names)
    forbidden_hits = [
        name
        for name in names
        if name.startswith(".python_packages/")
        and any(
            part.split("-", 1)[0].split(".", 1)[0].lower().replace("_", "-")
            in FORBIDDEN_CONSOLE_PACKAGES
            or part.lower().startswith("scikit_learn")
            or part.lower().startswith("scikit-learn")
            for part in name.replace("\\", "/").split("/")
        )
    ]
    assert forbidden_hits == [], f"console ZIP vendored forbidden packages: {forbidden_hits[:20]}"


def test_packaging_excludes_runtime_data_and_does_not_overwrite_home_data(tmp_path: Path) -> None:
    home_data = tmp_path / "home" / "data" / "metis-console"
    home_data.mkdir(parents=True)
    sentinel = home_data / "accounts.json"
    sentinel.write_text('{"keep": true}\n', encoding="utf-8")
    planted = ROOT / "output" / "runtime" / "operations-console" / "accounts.json"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text('{"secret_runtime": true}\n', encoding="utf-8")
    tiny_reqs = tmp_path / "tiny-requirements.txt"
    tiny_reqs.write_text("packaging==26.3\n", encoding="utf-8")
    try:
        output = tmp_path / "pkg.zip"
        write_deploy_zip(output, root=ROOT, requirements=tiny_reqs)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        assert not any(package_contains_runtime_data(name) for name in names)
        assert not any(name.endswith("accounts.json") and "operations-console" in name for name in names)
        assert not any(name.startswith("home/data") or name.startswith("/home/data") for name in names)
        assert sentinel.read_text(encoding="utf-8") == '{"keep": true}\n'
    finally:
        if planted.exists():
            planted.unlink()

    with pytest.raises(DeployPackageError, match="must_not_write_home_data"):
        write_deploy_zip(home_data / "metis-console.zip", root=ROOT)


def test_runtime_data_markers_cover_home_data_and_console_state() -> None:
    assert any("home/data" in marker or marker == "home/data" for marker in RUNTIME_DATA_MARKERS)
    assert any("operations-console" in marker for marker in RUNTIME_DATA_MARKERS)
    assert package_contains_runtime_data("output/runtime/operations-console/accounts.json")
    assert package_contains_runtime_data("home/data/metis-console/accounts.json")
    assert not package_contains_runtime_data("src/console_asgi.py")


def test_no_secrets_in_git_and_storage_via_app_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    store = load_g2_store()
    assert "AccountKey" not in _read(ROOT / "config" / "g2_source_store.v1.json")
    assert store["identity_secret_boundary"].startswith("no storage keys")
    for path in (
        ROOT / ".github" / "workflows" / "deploy-test.yml",
        ROOT / ".github" / "workflows" / "deploy-production.yml",
        ROOT / "docs" / "TEST_AND_RELEASE_RUNBOOK.md",
    ):
        text = _read(path)
        assert "AccountKey=" not in text
        assert "DefaultEndpointsProtocol" not in text
        assert ".publishsettings" not in text
        assert "client-secret" not in text.lower()
        assert "AZURE_CLIENT_SECRET" not in text

    monkeypatch.setenv("G2_STORAGE_ACCOUNT", "aidataservicetest")
    monkeypatch.setenv("G2_BLOB_CONTAINER", "canonical-sources-test")
    monkeypatch.setenv("G2_STATUS", "PASS")
    effective = effective_g2_store()
    assert effective["storage_account"] == "aidataservicetest"
    assert effective["container"] == "canonical-sources-test"
    assert effective["g2_status"] == "BLOCKED"
    assert g2_gate_status() == "BLOCKED"
    locator = build_g2_locator(sha256=DIGEST, filename="source.html")
    assert locator == f"azure://aidataservicetest/canonical-sources-test/{DIGEST}/source.html"
    file_store = load_g2_store()
    assert file_store["container"] == "canonical-sources"
    assert file_store["storage_account"] == "aidataservice"

    test_settings = storage_app_settings("test")
    prod_settings = storage_app_settings("production")
    assert test_settings["G2_BLOB_CONTAINER"] == "canonical-sources-test"
    assert prod_settings["G2_BLOB_CONTAINER"] == "canonical-sources"
    assert test_settings["CONSOLE_DATA_ROOT"] == "/home/data/metis-console-test"
    assert prod_settings["CONSOLE_DATA_ROOT"] == "/home/data/metis-console"
    assert "AccountKey" not in str(test_settings)
    assert "CONSOLE_IMMUTABLE_SOURCE_STORE" not in test_settings
    assert "CONSOLE_IMMUTABLE_SOURCE_STORE" not in prod_settings
    assert "AZURE_STORAGE_KEY" not in test_settings


def test_test_and_production_identities_cannot_cross() -> None:
    assert_deploy_allowed(environment="test", identity="metis-deploy-test", target_app=TEST_APP)
    assert_deploy_allowed(
        environment="production",
        identity="metis-deploy-production",
        target_app=PRODUCTION_APP,
    )
    with pytest.raises(DeployIdentityError, match="test_cannot_production"):
        assert_deploy_allowed(
            environment="test",
            identity="metis-deploy-test",
            target_app=PRODUCTION_APP,
        )
    with pytest.raises(DeployIdentityError, match="production_cannot_test"):
        assert_deploy_allowed(
            environment="production",
            identity="metis-deploy-production",
            target_app=TEST_APP,
        )
    with pytest.raises(DeployIdentityError, match="identity_environment_mismatch"):
        assert_deploy_allowed(
            environment="test",
            identity="metis-deploy-production",
            target_app=TEST_APP,
        )


def test_test_stays_inactive_but_production_has_manual_production_only_path() -> None:
    test_text = _read(ROOT / ".github" / "workflows" / "deploy-test.yml")
    prod_text = _read(ROOT / ".github" / "workflows" / "deploy-production.yml")

    assert "AZURE_TEST_CLIENT_ID" in test_text
    assert "AZURE_PRODUCTION_CLIENT_ID" not in test_text
    assert "AZURE_PRODUCTION_CLIENT_ID" in prod_text
    assert "AZURE_TEST_CLIENT_ID" not in prod_text
    assert TEST_APP in test_text
    assert "AZURE_PRODUCTION_WEBAPP_NAME" not in test_text
    assert "AZURE_TEST_WEBAPP_NAME" not in prod_text
    assert "AZURE_PRODUCTION_WEBAPP_NAME" in prod_text
    assert "AZURE_TEST_WEBAPP_NAME" in test_text
    assert "vars.METIS_TEST_APP_READY == 'true'" in test_text
    assert "vars.METIS_TEST_APP_READY == 'true'" not in prod_text
    assert "assert_deploy_allowed" in prod_text
    assert "Validate exact main commit" in prod_text
    assert "workflow_dispatch" in prod_text
    assert "workflow_dispatch" in test_text
    assert "branches: [main]" not in prod_text
    assert "branches: [main]" not in test_text
    assert "\n  push:" not in test_text
    assert "\n  push:" not in prod_text
    assert "exit 1" in test_text
    assert "az webapp deploy" in prod_text
    assert "Fail-closed until vvn-metis-console-test exists" in test_text
    assert "Fail-closed until vvn-metis-console-test exists" not in prod_text
    assert "require_deploy_activation" in test_text
    assert "require_deploy_activation" not in prod_text

    with pytest.raises(DeployIdentityError, match="test_app_missing"):
        require_deploy_activation(ready_flag="", declared_app=TEST_APP)
    with pytest.raises(DeployIdentityError, match="test_app_missing"):
        require_deploy_activation(ready_flag="false", declared_app=TEST_APP)
    with pytest.raises(DeployIdentityError, match="unexpected_test_app"):
        require_deploy_activation(ready_flag="true", declared_app="some-other-app")
    require_deploy_activation(ready_flag="true", declared_app=TEST_APP)


def test_merge_to_main_does_not_auto_deploy_while_test_app_missing() -> None:
    test_text = _read(ROOT / ".github" / "workflows" / "deploy-test.yml")
    prod_text = _read(ROOT / ".github" / "workflows" / "deploy-production.yml")
    ci_text = _read(ROOT / ".github" / "workflows" / "ci.yml")
    assert "branches: [main]" not in test_text
    assert "branches: [main]" not in prod_text
    assert "\n  push:" not in test_text
    assert "\n  push:" not in prod_text
    assert "on:\n  push:" in ci_text or "on:\n  push:" in ci_text.replace("\r\n", "\n")
    assert "az webapp deploy" in test_text
    assert "az webapp deploy" in prod_text
    assert "METIS_TEST_APP_READY" in test_text
    assert "vvn-metis-console-test" in test_text
    assert "if: ${{ vars.METIS_TEST_APP_READY == 'true' }}" in test_text
    assert os.environ.get("METIS_TEST_APP_READY", "") != "true"
    with pytest.raises(DeployIdentityError, match="test_app_missing"):
        require_deploy_activation(
            ready_flag=os.environ.get("METIS_TEST_APP_READY", ""),
            declared_app=os.environ.get("AZURE_TEST_WEBAPP_NAME", TEST_APP),
        )


def test_runbook_requires_separate_service_principals_and_app_settings() -> None:
    runbook = _read(ROOT / "docs" / "TEST_AND_RELEASE_RUNBOOK.md")
    assert "separate" in runbook.lower() or "gescheiden" in runbook.lower()
    assert "metis-deploy-test" in runbook
    assert "metis-deploy-production" in runbook
    assert "Website Contributor" in runbook
    assert "canonical-sources-test" in runbook
    assert "G2_BLOB_CONTAINER" in runbook
    assert "geen secrets" in runbook.lower() or "no secrets" in runbook.lower() or "geen Azure-keys" in runbook
    assert "MUST NOT" in runbook or "niet activeren" in runbook.lower() or "inactief" in runbook.lower()
    assert "vvn-metis-console-test" in runbook
    assert "METIS_TEST_APP_READY" in runbook
    assert "geen" in runbook and "on.push" in runbook
    assert "v2.29" in runbook


def test_wave_c_does_not_open_publish(tmp_path: Path) -> None:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    researcher = console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher", "reviewer"),
        display_name="Anne",
    )
    reviewer = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer", "publisher"),
        display_name="Bert",
    )
    html = (
        b"<!doctype html><html><body><h1>Test</h1>"
        b"<p>Dit is een aanbeveling voor de praktijk.</p></body></html>"
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="richtlijn.html",
        data=html,
        content_type="text/html",
        ingest_kind="new",
        title="Wave C",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/richtlijn",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[researcher["account_id"], reviewer["account_id"]],
    )
    published = console.publish(actor_id=reviewer["account_id"], snapshot_id=receipt["snapshot_id"])
    assert published["status"] == "BLOCKED"
    assert published["g2"] == "BLOCKED"
    assert published["cutover"] is False
    assert g2_gate_status() == "BLOCKED"
    assert load_g2_store()["g2_status"] == "BLOCKED"
