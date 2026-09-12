"""Explicit identity cut-over guard for PostgreSQL workflow mode.

The original identity store retains its one-shot legacy importer for the operator
migration command. Runtime startup uses this subclass so local files can never be
silently promoted back into PostgreSQL authority.
"""
from __future__ import annotations

from typing import Any

from src.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore


class CutoverPostgresWorkflowIdentityStore(PostgresWorkflowIdentityStore):
    """Runtime identity store with legacy startup import disabled."""

    def migrate_legacy_if_empty(
        self,
        accounts: dict[str, dict[str, Any]],
        sessions: dict[str, dict[str, Any]],
    ) -> bool:
        return False
