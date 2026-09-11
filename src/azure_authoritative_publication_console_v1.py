"""Azure publication boundary: Blob is the mandatory source authority.

PostgreSQL is the durable authority for published knowledge metadata and exact
object versions. Azure Blob remains the independent authority for the source
bytes those versions came from. Before a PostgreSQL-backed publication is
projected or reconciled locally, every active source snapshot is read back from
Blob and verified against its recorded SHA-256.
"""
from __future__ import annotations

from typing import Any

from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.g2_source_store import G2SourceStoreError, is_g2_locator
from src.integrity_kernel import sha256_bytes
from src.operations_console_v1 import ConsoleError


class AzureAuthoritativePublicationConsole(DurablePublicationConsole):
    """Fail closed unless active published source bytes verify from Azure Blob."""

    def _verify_release_source(self, release: dict[str, Any]) -> None:
        source_store = self.immutable_source_store
        if source_store is None:
            raise ConsoleError("azure_blob_source_store_required")

        source_sha256 = str(release.get("source_sha256") or "").strip().lower()
        source_locator = str(release.get("source_locator") or "").strip()
        if not source_sha256 or not is_g2_locator(source_locator):
            raise ConsoleError("azure_blob_source_lineage_invalid")

        try:
            source_bytes = source_store.load_verified(source_locator)
        except (G2SourceStoreError, ValueError) as exc:
            raise ConsoleError("azure_blob_source_readback_failed", str(exc)) from exc

        if sha256_bytes(source_bytes).lower() != source_sha256:
            raise ConsoleError("azure_blob_source_sha256_mismatch")

    def _verify_active_authority_sources(self) -> int:
        """Read back each unique active publication source from Blob once."""
        store = self.canonical_publication_store
        if store is None:
            return 0
        try:
            rows = store.active_publication_rows()
        except CanonicalPublicationStoreError as exc:
            raise ConsoleError("durable_publication_projection_read_failed", str(exc)) from exc

        verified: set[str] = set()
        for row in rows:
            snapshot_id = str(row.get("snapshot_id") or "").strip()
            if not snapshot_id:
                raise ConsoleError("azure_blob_source_lineage_missing")
            if snapshot_id in verified:
                continue
            try:
                release = store.release_for_snapshot(snapshot_id)
            except CanonicalPublicationStoreError as exc:
                raise ConsoleError("durable_publication_lookup_failed", str(exc)) from exc
            if release is None:
                raise ConsoleError("azure_blob_source_lineage_missing")
            self._verify_release_source(release)
            verified.add(snapshot_id)
        return len(verified)

    def _projection_from_authority(self) -> list[dict[str, Any]]:
        # This hook is reached both immediately after durable publication and
        # during startup reconciliation. Local published state is therefore
        # never rebuilt from PostgreSQL unless the referenced source bytes are
        # present in Blob and survive a fresh SHA-256 read-back.
        self._verify_active_authority_sources()
        return super()._projection_from_authority()
