"""Explicit identity cut-over guard for PostgreSQL workflow mode.

The original identity store retains its one-shot legacy importer for the operator
migration command. Runtime startup never reads identity files (D6b); this subclass
additionally refuses the importer so no runtime path can promote local files into
PostgreSQL authority.
"""
from __future__ import annotations

from typing import Any

from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore


class CutoverPostgresWorkflowIdentityStore(PostgresWorkflowIdentityStore):
    """Runtime identity store with the legacy importer disabled."""

    def migrate_legacy_if_empty(
        self,
        accounts: dict[str, dict[str, Any]],
        sessions: dict[str, dict[str, Any]],
    ) -> bool:
        return False
