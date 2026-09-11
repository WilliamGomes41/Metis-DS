"""Azure must not silently fall back to console-local publication or source bytes.

# release-control-evidence: opslag durable canonical authority azure blob source authority
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import pytest

from src.console_asgi import _canonical_store, _immutable_source_store

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def test_azure_runtime_refuses_missing_canonical_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSITE_SITE_NAME", "vvn-metis-console")
    monkeypatch.delenv("METIS_CANONICAL_STORE", raising=False)

    with pytest.raises(RuntimeError, match="canonical_store_required_in_azure"):
        _canonical_store()


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


def test_local_runtime_may_run_without_durable_authorities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    monkeypatch.delenv("METIS_CANONICAL_STORE", raising=False)
    monkeypatch.delenv("CONSOLE_IMMUTABLE_SOURCE_STORE", raising=False)

    assert _canonical_store() is None
    assert _immutable_source_store() is None
