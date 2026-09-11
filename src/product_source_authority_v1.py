"""Fail-closed source-byte authority checks for REAL Product API serving."""
from __future__ import annotations

from typing import Any

from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError
from src.g2_source_store import G2SourceStoreError, is_g2_locator
from src.integrity_kernel import sha256_bytes


class ProductSourceAuthorityError(RuntimeError):
    """Raised when PostgreSQL publication metadata cannot be proven against Blob."""


def verify_active_publication_sources(
    authority_rows: list[dict[str, Any]],
    *,
    canonical_store: Any,
    source_store: Any,
) -> int:
    """Verify each unique active source snapshot by fresh Blob read-back.

    PostgreSQL decides which object versions/releases are active. Azure Blob
    decides whether the exact source bytes still exist. REAL serving requires
    both authorities to agree; no cached/local file is accepted as fallback.
    """
    if source_store is None:
        raise ProductSourceAuthorityError("product_source_store_required")

    verified: set[str] = set()
    for row in authority_rows:
        snapshot_id = str(row.get("snapshot_id") or "").strip()
        if not snapshot_id:
            raise ProductSourceAuthorityError("product_source_snapshot_missing")
        if snapshot_id in verified:
            continue
        try:
            release = canonical_store.release_for_snapshot(snapshot_id)
        except CanonicalPublicationStoreError as exc:
            raise ProductSourceAuthorityError("product_source_lineage_unavailable") from exc
        except Exception as exc:
            raise ProductSourceAuthorityError("product_source_lineage_unavailable") from exc
        if release is None:
            raise ProductSourceAuthorityError("product_source_lineage_missing")

        expected = str(release.get("source_sha256") or "").strip().lower()
        locator = str(release.get("source_locator") or "").strip()
        if len(expected) != 64 or not is_g2_locator(locator):
            raise ProductSourceAuthorityError("product_source_lineage_invalid")
        try:
            data = source_store.load_verified(locator)
        except (G2SourceStoreError, ValueError, KeyError) as exc:
            raise ProductSourceAuthorityError("product_source_readback_failed") from exc
        except Exception as exc:
            raise ProductSourceAuthorityError("product_source_readback_failed") from exc
        if sha256_bytes(data).lower() != expected:
            raise ProductSourceAuthorityError("product_source_sha256_mismatch")
        verified.add(snapshot_id)
    return len(verified)
