"""Access decisions are part of the same recoverable lifecycle snapshot.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import zipfile

import pytest

from src.api_access_v1 import PostgresApiAccessStore
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.publication_chain_recovery_v1 import PublicationChainRecoveryError
from src.workflows import workflow_chain_recovery_v1 as recovery
from tests.test_api_access_lifecycle_v1 import _provision
from tests.test_api_access_product_v1 import DOC, _client
from tests.test_publication_chain_recovery_v1 import FakeBlobStore
from tests.test_workflow_chain_recovery_v1 import (
    SOURCE_BYTES, SOURCE_LOCATOR, _install_schema, _seed_workflow, recovery_postgres,
)


def _adapter(config):
    return recovery.PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config))


def test_access_archive_restore_preserves_http_decisions_and_exact_evidence(recovery_postgres, tmp_path):
    _seed_workflow(recovery_postgres)
    access = PostgresApiAccessStore(recovery_postgres)
    active = _provision(access, name="Active", tenant_docs=(DOC, "other"), app_docs=(DOC,))
    restricted = _provision(access, name="Restricted", tenant_docs=("other",), app_docs=("other",))
    suspended = _provision(access, name="Suspended")
    revoked = _provision(access, name="Revoked")
    access.set_application_grant(
        actor_id="publisher-test", tenant_id=active.tenant_id, application_id=active.application_id,
        expected_version=1, content_scope="RESOURCE_SET", document_ids=[DOC],
        scopes=["documents:read"], requests_per_minute=80, max_top_k=4,
    )
    access.set_tenant_state(
        actor_id="publisher-test", tenant_id=suspended.tenant_id,
        expected_version=1, target_state="SUSPENDED",
    )
    access.revoke_credential(
        actor_id="publisher-test", tenant_id=revoked.tenant_id,
        application_id=revoked.application_id, credential_id=revoked.credential_id,
    )
    consumers = [active, restricted, suspended, revoked]

    def responses(path):
        with _client(path, PostgresApiAccessStore(recovery_postgres)) as client:
            output = []
            for item in consumers:
                response = client.get("/v1/documents", headers={"Authorization": f"Bearer {item.credential}"})
                output.append((response.status_code, [d["document_id"] for d in response.json().get("documents", [])]))
            return output

    before_http = responses(tmp_path / "before")
    assert before_http == [(200, [DOC]), (200, []), (401, []), (401, [])]
    adapter = _adapter(recovery_postgres)
    before = adapter.export_state()
    archive = tmp_path / "complete.zip"
    recovery.backup_workflow_chain(
        archive, database=adapter, source_store=FakeBlobStore({SOURCE_LOCATOR: SOURCE_BYTES}),
    )
    with zipfile.ZipFile(archive) as zipf:
        data = zipf.read("database.json").decode()
        assert all(item.credential not in data for item in consumers)
        assert set(json.loads(data)["api_access_tables"]) == set(recovery.API_ACCESS_TABLES)
    _install_schema(recovery_postgres.dsn)
    result = recovery.restore_workflow_chain(archive, database=_adapter(recovery_postgres), source_store=FakeBlobStore())
    assert result["ok"] is True
    after = _adapter(recovery_postgres).export_state()
    for group in ("tables", "workflow_tables", "api_access_tables"):
        assert after[group] == before[group]
    assert responses(tmp_path / "after") == before_http


def test_access_only_nonempty_target_is_never_overwritten(recovery_postgres):
    access = PostgresApiAccessStore(recovery_postgres)
    _provision(access, name="Original")
    state = _adapter(recovery_postgres).export_state()
    _install_schema(recovery_postgres.dsn)
    other = _provision(access, name="Existing destination")
    with pytest.raises(PublicationChainRecoveryError, match="target_not_empty.*api_access"):
        _adapter(recovery_postgres).restore_state(state)
    assert access.authenticate(other.credential) is not None
    assert [r["tenant_id"] for r in _adapter(recovery_postgres).export_state()["api_access_tables"]["tenants"]] == [other.tenant_id]


@pytest.mark.parametrize("fault", ["missing_table", "missing_hash", "orphan", "duplicate", "legacy"])
def test_incomplete_access_archive_is_rejected_before_restore(recovery_postgres, fault):
    _provision(PostgresApiAccessStore(recovery_postgres), name="Source")
    state = _adapter(recovery_postgres).export_state()
    tables = state["api_access_tables"]
    if fault == "missing_table":
        del tables["tenant_resources"]
    elif fault == "missing_hash":
        del tables["credentials"][0]["secret_sha256"]
    elif fault == "orphan":
        tables["applications"][0]["tenant_id"] = "absent"
    elif fault == "duplicate":
        tables["credentials"].append(dict(tables["credentials"][0]))
    else:
        state["workflow_recovery_version"] = 2
        del state["api_access_tables"]
    _install_schema(recovery_postgres.dsn)
    with pytest.raises(PublicationChainRecoveryError, match="api_access"):
        _adapter(recovery_postgres).restore_state(state)
    _adapter(recovery_postgres).assert_empty()


def test_access_import_failure_rolls_back_workflow_and_access_together(recovery_postgres, monkeypatch):
    _seed_workflow(recovery_postgres)
    _provision(PostgresApiAccessStore(recovery_postgres), name="Source")
    state = _adapter(recovery_postgres).export_state()
    _install_schema(recovery_postgres.dsn)
    original = recovery._insert_rows

    def fail_during_access(con, **kwargs):
        original(con, **kwargs)
        if kwargs["schema"] == "api_access" and kwargs["table"] == "audit_events":
            raise RuntimeError("interrupted access import")

    monkeypatch.setattr(recovery, "_insert_rows", fail_during_access)
    with pytest.raises(PublicationChainRecoveryError, match="workflow_database_restore_failed"):
        _adapter(recovery_postgres).restore_state(state)
    _adapter(recovery_postgres).assert_empty()
    monkeypatch.setattr(recovery, "_insert_rows", original)
    _adapter(recovery_postgres).restore_state(state)
    assert _adapter(recovery_postgres).export_state()["api_access_tables"] == state["api_access_tables"]


def test_access_export_uses_same_snapshot_despite_concurrent_revocation(recovery_postgres, monkeypatch):
    _seed_workflow(recovery_postgres)
    access = PostgresApiAccessStore(recovery_postgres)
    issued = _provision(access, name="Snapshot")
    before = _adapter(recovery_postgres).export_state()["api_access_tables"]
    original = recovery._json_safe
    changed = False

    def revoke_after_workflow_read(row):
        nonlocal changed
        if not changed and "account_id" in row:
            changed = True
            access.revoke_credential(
                actor_id="publisher-test", tenant_id=issued.tenant_id,
                application_id=issued.application_id, credential_id=issued.credential_id,
            )
        return original(row)

    monkeypatch.setattr(recovery, "_json_safe", revoke_after_workflow_read)
    exported = _adapter(recovery_postgres).export_state()
    assert changed
    assert exported["api_access_tables"] == before
    assert access.authenticate(issued.credential) is None


def test_restore_never_reports_success_when_access_roundtrip_differs(recovery_postgres, tmp_path, monkeypatch):
    _provision(PostgresApiAccessStore(recovery_postgres), name="Source")
    adapter = _adapter(recovery_postgres)
    archive = tmp_path / "access.zip"
    recovery.backup_workflow_chain(archive, database=adapter, source_store=FakeBlobStore())
    _install_schema(recovery_postgres.dsn)
    original = adapter.export_state

    def different_access():
        state = original()
        state["api_access_tables"]["tenants"][0]["policy_version"] += 1
        return state

    monkeypatch.setattr(adapter, "export_state", different_access)
    with pytest.raises(PublicationChainRecoveryError, match="api_access_tables_restore_roundtrip_mismatch"):
        recovery.restore_workflow_chain(archive, database=adapter, source_store=FakeBlobStore())
