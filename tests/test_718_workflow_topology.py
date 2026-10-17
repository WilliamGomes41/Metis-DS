"""#718: reject partial authority configurations before touching storage.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from itertools import product

import pytest

from src import console_asgi as asgi

SETTINGS = (
    "METIS_WORKFLOW_STORE", "METIS_WORKFLOW_DOCUMENT_STORE",
    "METIS_WORKFLOW_REVIEW_STORE", "METIS_WORKFLOW_REMAINING_STORE",
    "METIS_CANONICAL_STORE",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch, tmp_path):
    for key in (*SETTINGS, "WEBSITE_SITE_NAME", "CONSOLE_IMMUTABLE_SOURCE_STORE",
                "CONSOLE_BOOTSTRAP_USERNAME", "CONSOLE_BOOTSTRAP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CONSOLE_DATA_ROOT", str(tmp_path / "untouched"))


PARTIAL = [bits for bits in product((False, True), repeat=5) if any(bits) and not all(bits)]


@pytest.mark.parametrize("bits", PARTIAL)
def test_partial_configuration_refused_before_storage(bits, monkeypatch, tmp_path):
    for key, enabled in zip(SETTINGS, bits):
        if enabled:
            monkeypatch.setenv(key, "postgres")
    touched = []

    def forbidden(*args, **kwargs):
        touched.append(True)
        raise AssertionError("storage_or_credentials_opened_before_refusal")

    for name in ("_postgres_credential", "_canonical_store", "_immutable_source_store",
                 "_audit_archive_store", "_workflow_identity_store", "_workflow_document_store",
                 "_workflow_review_store", "_workflow_remaining_store"):
        monkeypatch.setattr(asgi, name, forbidden)
    with pytest.raises(RuntimeError) as exc:
        asgi.build_app()
    assert str(exc.value) in {
        "workflow_review_store_required_for_document_store",
        "complete_postgres_workflow_required",
        "canonical_store_required_for_postgres_workflow",
    }
    assert touched == []
    assert not (tmp_path / "untouched").exists()


@pytest.mark.parametrize("key", SETTINGS)
def test_unknown_store_kind_refused_before_credentials(key, monkeypatch):
    for setting in SETTINGS:
        monkeypatch.setenv(setting, "postgres")
    monkeypatch.setenv(key, "postgress")
    monkeypatch.setattr(asgi, "_postgres_credential", lambda: pytest.fail("credentials opened"))
    with pytest.raises(RuntimeError, match="unsupported_.*store"):
        asgi.build_app()


def test_local_file_harness_still_starts():
    from fastapi.testclient import TestClient
    with TestClient(asgi.build_app()) as client:
        assert client.get("/login").status_code == 200


def test_azure_file_harness_refused_before_storage(monkeypatch):
    monkeypatch.setenv("WEBSITE_SITE_NAME", "test-app")
    monkeypatch.setattr(asgi, "_immutable_source_store", lambda: pytest.fail("storage opened"))
    with pytest.raises(RuntimeError, match="azure_workflow_authorities_required"):
        asgi.build_app()
