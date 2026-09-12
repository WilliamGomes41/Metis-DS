"""Contract tests for the shared PostgreSQL workflow schema.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "002_workflow_schema.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_workflow_schema_is_separate_from_publication_authority() -> None:
    sql = _sql()
    assert "CREATE SCHEMA IF NOT EXISTS workflow" in sql
    assert "workflow.accounts" in sql
    assert "workflow.sessions" in sql
    assert "workflow.documents" in sql
    assert "workflow.document_reviewers" in sql
    assert "workflow.document_objects" in sql
    assert "workflow.review_events" in sql
    assert "workflow.publish_authorizations" in sql
    assert "canonical_object_versions" not in sql
    assert "publication_registry" not in sql


def test_workflow_schema_preserves_shared_state_and_identity_boundaries() -> None:
    sql = _sql()
    assert "username TEXT NOT NULL UNIQUE" in sql
    assert "token_hash TEXT PRIMARY KEY" in sql
    assert "REFERENCES workflow.accounts(account_id)" in sql
    assert "source_sha256 TEXT NOT NULL" in sql
    assert "source_locator TEXT NOT NULL" in sql
    assert "payload JSONB NOT NULL" in sql
    assert "revision BIGINT NOT NULL DEFAULT 1" in sql
    assert "previous_event_hash TEXT" in sql
    assert "event_hash TEXT NOT NULL UNIQUE" in sql


def test_workflow_schema_keeps_review_and_publish_authorization_object_bound() -> None:
    sql = _sql()
    assert "object_id TEXT NOT NULL" in sql
    assert "object_version TEXT NOT NULL" in sql
    assert "canonical_object_hash TEXT NOT NULL" in sql
    assert "confirmed_object_type TEXT NOT NULL" in sql
    assert "reviewer_account_id TEXT NOT NULL" in sql
    assert "valid BOOLEAN NOT NULL" in sql
