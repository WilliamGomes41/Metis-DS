"""Azure must not silently fall back to console-local publication or source bytes.

# release-control-evidence: opslag durable canonical authority azure blob source authority
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import pytest

from src.console_asgi import _immutable_source_store
from src.workflow_store_configuration import POSTGRES_STORE_SETTINGS, validate_workflow_store_configuration

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def test_azure_runtime_refuses_missing_canonical_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSITE_SITE_NAME", "vvn-metis-console")
    for key in (*POSTGRES_STORE_SETTINGS, *("METIS_CANONICAL_DB_DSN", "METIS_CANONICAL_DB_HOST", "METIS_CANONICAL_DB_NAME", "METIS_CANONICAL_DB_USER")):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="postgres_authority_configuration_required"):
        validate_workflow_store_configuration()


def test_azure_runtime_refuses_missing_blob_source_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSITE_SITE_NAME", "vvn-metis-console")
    monkeypatch.delenv("CONSOLE_IMMUTABLE_SOURCE_STORE", raising=False)

    with pytest.raises(RuntimeError, match="azure_blob_source_store_required_in_azure"):
        _immutable_source_store()


def test_azure_runtime_refuses_non_azure_source_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSITE_SITE_NAME", "vvn-metis-console")
    monkeypatch.setenv("CONSOLE_IMMUTABLE_SOURCE_STORE", "local")

    with pytest.raises(RuntimeError, match="unsupported_immutable_source_store"):
        _immutable_source_store()


def test_local_runtime_requires_postgres_but_may_use_local_source_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """D6b: locally PostgreSQL is required; only the source-byte store may stay local."""
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    for key in (*POSTGRES_STORE_SETTINGS, *("METIS_CANONICAL_DB_DSN", "METIS_CANONICAL_DB_HOST", "METIS_CANONICAL_DB_NAME", "METIS_CANONICAL_DB_USER")):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("CONSOLE_IMMUTABLE_SOURCE_STORE", raising=False)

    with pytest.raises(RuntimeError, match="postgres_authority_configuration_required"):
        validate_workflow_store_configuration()
    monkeypatch.setenv("METIS_CANONICAL_DB_DSN", "postgresql://unused.invalid/metis")
    assert validate_workflow_store_configuration() is None
    assert _immutable_source_store() is None
