"""Publication registry is the single serving-eligibility authority.

# release-control-evidence: opslag
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore

ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _published_view(sql: str) -> str:
    return sql.split("CREATE OR REPLACE VIEW published_knowledge_objects AS", 1)[1].strip()


def _normalized(sql: str) -> str:
    return " ".join(sql.split())


def test_postgres_schema_and_migration_use_registry_as_only_serving_gate() -> None:
    schema = (ROOT / "db" / "schema_v2.sql").read_text(encoding="utf-8")
    migration = (ROOT / "db" / "migrations" / "007_publication_registry_serving_authority.sql").read_text(
        encoding="utf-8"
    )

    schema_view = _published_view(schema)
    migration_view = _published_view(migration)

    assert "WHERE r.state = 'active';" in schema_view
    assert "rel.status" not in schema_view
    assert "WHERE r.state = 'active';" in migration_view
    assert "rel.status" not in migration_view
    assert _normalized(schema_view) == _normalized(migration_view)


def test_active_publication_rows_uses_registry_state_without_release_status_gate() -> None:
    source = inspect.getsource(PostgresCanonicalPublicationStore.active_publication_rows)

    assert "WHERE r.state='active'" in source
    assert "rel.status" not in source
    assert "emergency_unpublished" not in source


def test_source_lineage_lookup_does_not_reintroduce_release_status_as_serving_gate() -> None:
    source = inspect.getsource(PostgresCanonicalPublicationStore.release_for_snapshot)

    assert "event_type='release_published'" in source
    assert "rel.status" not in source
