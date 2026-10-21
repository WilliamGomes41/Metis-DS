# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs

from pathlib import Path

from fastapi.testclient import TestClient

from src.api_access_v1 import ApiAccessPrincipal, ApiAccessStoreError
from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import TenantRegistry
from src.usage_ledger_v1 import UsageLedger

ROOT = Path(__file__).resolve().parents[1]
DOC = "vvn-osteoporose-fractuurpreventie-2024"
KEY_A = "metis-test-a"
KEY_B = "metis-test-b"


class MutableAccessStore:
    def __init__(self):
        self.principals = {}

    def verify_schema(self):
        return None

    def authenticate(self, api_key):
        return self.principals.get(api_key)


class BrokenAccessStore:
    def verify_schema(self):
        return None

    def authenticate(self, api_key):
        raise ApiAccessStoreError("database_down")


def _paths(tmp_path: Path) -> ProductPaths:
    p = ProductPaths.defaults(ROOT)
    return ProductPaths(
        real_records=p.real_records,
        fixture_records=p.fixture_records,
        real_published=p.real_published,
        lexical_config=p.lexical_config,
        vector_config=p.vector_config,
        hybrid_config=p.hybrid_config,
        tenant_config=tmp_path / "unused.json",
        usage_db=tmp_path / "usage.sqlite",
    )


def _principal(*, tenant, app, credential, docs, scopes):
    return ApiAccessPrincipal(
        tenant_id=tenant,
        application_id=app,
        credential_id=credential,
        scopes=frozenset(scopes),
        allowed_document_ids=frozenset(docs),
        requests_per_minute=100,
        max_top_k=5,
    )


def _client(tmp_path: Path, store) -> TestClient:
    p = _paths(tmp_path)
    app = create_product_app(
        "fixture",
        paths=p,
        tenant_registry=TenantRegistry([]),
        api_access_store=store,
        api_access_mode="postgres",
        usage_ledger=UsageLedger(p.usage_db),
        allow_fixture=True,
    )
    return TestClient(app)


def test_new_consumer_is_visible_to_same_running_api_without_restart(tmp_path):
    store = MutableAccessStore()
    client = _client(tmp_path, store)

    assert client.get("/v1/documents", headers={"Authorization": f"Bearer {KEY_A}"}).status_code == 401

    store.principals[KEY_A] = _principal(
        tenant="tenant-a",
        app="app-a",
        credential="credential-a",
        docs=(DOC,),
        scopes=("documents:read",),
    )

    response = client.get("/v1/documents", headers={"Authorization": f"Bearer {KEY_A}"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-a"
    assert [row["document_id"] for row in response.json()["documents"]] == [DOC]


def test_two_consumers_use_same_contract_with_different_effective_access(tmp_path):
    store = MutableAccessStore()
    store.principals[KEY_A] = _principal(
        tenant="tenant-a",
        app="app-a",
        credential="credential-a",
        docs=(DOC,),
        scopes=("retrieve", "documents:read"),
    )
    store.principals[KEY_B] = _principal(
        tenant="tenant-b",
        app="app-b",
        credential="credential-b",
        docs=("not-this-document",),
        scopes=("retrieve",),
    )
    client = _client(tmp_path, store)

    allowed = client.post(
        "/v1/retrieve",
        headers={"Authorization": f"Bearer {KEY_A}"},
        json={"query": "fractuurrisico"},
    )
    denied_corpus = client.post(
        "/v1/retrieve",
        headers={"Authorization": f"Bearer {KEY_B}"},
        json={"query": "fractuurrisico"},
    )
    denied_scope = client.get(
        "/v1/documents",
        headers={"Authorization": f"Bearer {KEY_B}"},
    )

    assert allowed.status_code == 200
    assert allowed.json()["result_count"] > 0
    assert denied_corpus.status_code == 200
    assert denied_corpus.json()["status"] == "abstain"
    assert denied_corpus.json()["reason"] == "empty_published_corpus"
    assert denied_scope.status_code == 403
    assert denied_scope.json()["detail"]["code"] == "scope_denied"


def test_postgres_access_mode_fails_closed_when_store_is_unavailable(tmp_path):
    client = _client(tmp_path, BrokenAccessStore())
    response = client.get(
        "/v1/documents",
        headers={"Authorization": f"Bearer {KEY_A}"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "access_store_unavailable"


def test_entitlement_covers_context_embedded_in_derived_retrieval_text():
    principal = _principal(
        tenant="tenant-a",
        app="app-a",
        credential="credential-a",
        docs=(DOC,),
        scopes=("retrieve",),
    )
    record = {
        "metadata": {
            "document_id": DOC,
            "topic": [],
            "context_object_ids": ["context-from-other-document"],
        }
    }
    from src.product_api_v1 import ProductState

    state = object.__new__(ProductState)
    state._object_document_ids = {
        "context-from-other-document": "not-entitled-document",
    }
    assert state._record_is_entitled(principal, record) is False


def test_postgres_mode_does_not_read_or_fallback_to_legacy_registry(tmp_path):
    store = MutableAccessStore()
    store.principals[KEY_A] = _principal(
        tenant="tenant-a",
        app="app-a",
        credential="credential-a",
        docs=(DOC,),
        scopes=("documents:read",),
    )
    p = _paths(tmp_path)
    p.tenant_config.write_text("{ definitely-not-valid-json", encoding="utf-8")
    app = create_product_app(
        "fixture",
        paths=p,
        api_access_store=store,
        api_access_mode="postgres",
        usage_ledger=UsageLedger(p.usage_db),
        allow_fixture=True,
    )
    client = TestClient(app)
    response = client.get(
        "/v1/documents",
        headers={"Authorization": f"Bearer {KEY_A}"},
    )
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-a"
