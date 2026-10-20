"""P0 evidence: published source bytes are authoritative only when Blob verifies.

# release-control-evidence: opslag azure blob source authority readback sha256
# release-control-evidence: scope/belofte
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from src.azure_authoritative_publication_console_v1 import AzureAuthoritativePublicationConsole
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_v1 import ConsoleError

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_releasebewijs,
]


class _SourceStore:
    def __init__(self, data: bytes | None) -> None:
        self.data = data
        self.reads: list[str] = []

    def load_verified(self, locator: str) -> bytes:
        self.reads.append(locator)
        if self.data is None:
            raise G2SourceStoreError("canonical_source_missing")
        return self.data


def _console(tmp_path: Path, *, expected: bytes, actual: bytes | None, production_console):
    digest = hashlib.sha256(expected).hexdigest()
    source = _SourceStore(actual)
    console = production_console(root=tmp_path, azure=True,
        processing_binder=lambda console: None, immutable_source_store=source)
    from tests.test_logical_document_withdrawal_v1 import _object
    console.canonical_publication_store.persist_published_release(
        logical_document_id='fixture-logical', working_revision_id='fixture-working',
        snapshot_id='snap-0123456789abcdef-01234567', release_id='fixture-release',
        release_version='1', release_owner='fixture-publisher',
        source_sha256=digest, source_locator=build_g2_locator(sha256=digest, filename='source.pdf'),
        published_at='2026-10-20T12:00:00+00:00',
        objects=[_object(object_id='fixture-object', version='1', document_id='fixture-document',
                         checksum=digest, text='Canonical fixture object')])
    return console, source


def test_active_publication_source_is_read_back_from_blob_and_sha256_verified(tmp_path: Path, *, production_console) -> None:
    expected = b"published canonical source bytes"
    console, source = _console(tmp_path, expected=expected, actual=expected, production_console=production_console)

    assert console._verify_active_authority_sources() == 1
    assert len(source.reads) == 1


def test_missing_blob_blocks_authoritative_publication_rebuild(tmp_path: Path, *, production_console) -> None:
    console, _source = _console(tmp_path, expected=b"expected", actual=None, production_console=production_console)

    with pytest.raises(ConsoleError) as caught:
        console._verify_active_authority_sources()
    assert caught.value.code == "azure_blob_source_readback_failed"


def test_sha256_mismatch_blocks_authoritative_publication_rebuild(tmp_path: Path, *, production_console) -> None:
    console, _source = _console(tmp_path, expected=b"expected", actual=b"different", production_console=production_console)

    with pytest.raises(ConsoleError) as caught:
        console._verify_active_authority_sources()
    assert caught.value.code == "azure_blob_source_sha256_mismatch"


def test_missing_blob_store_blocks_authoritative_publication_rebuild(tmp_path: Path, *, production_console) -> None:
    console, _source = _console(tmp_path, expected=b"expected", actual=b"expected", production_console=production_console)
    console.immutable_source_store = None

    with pytest.raises(ConsoleError) as caught:
        console._verify_active_authority_sources()
    assert caught.value.code == "azure_blob_source_store_required"
