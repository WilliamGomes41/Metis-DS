from pathlib import Path

from fastapi.testclient import TestClient

from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import SlidingWindowRateLimiter, TenantPolicy, TenantRegistry, hash_api_key
from src.usage_ledger_v1 import UsageLedger

ROOT = Path(__file__).resolve().parents[1]
KEY = "fixture-client-secret-key"
DOC = "vvn-osteoporose-fractuurpreventie-2024"


def registry(*, docs=(DOC,), scopes=("retrieve","knowledge:read","documents:read","updates:read","usage:read"), rpm=100, max_top_k=5):
    return TenantRegistry([TenantPolicy.from_dict({
        "tenant_id": "test-tenant",
        "name": "Test Tenant",
        "enabled": True,
        "api_key_sha256": hash_api_key(KEY),
        "scopes": list(scopes),
        "allowed_document_ids": list(docs),
        "allowed_topics": ["*"],
        "requests_per_minute": rpm,
        "max_top_k": max_top_k,
    })])


def paths(tmp_path):
    p = ProductPaths.defaults(ROOT)
    return ProductPaths(
        real_records=p.real_records,
        fixture_records=p.fixture_records,
        real_published=p.real_published,
        lexical_config=p.lexical_config,
        vector_config=p.vector_config,
        hybrid_config=p.hybrid_config,
        tenant_config=tmp_path/"unused.json",
        usage_db=tmp_path/"usage.sqlite",
    )


def client(tmp_path, *, mode="fixture", reg=None, limiter=None):
    ps = paths(tmp_path)
    ledger = UsageLedger(ps.usage_db)
    app = create_product_app(mode, paths=ps, tenant_registry=reg or registry(), usage_ledger=ledger,
                             rate_limiter=limiter, allow_fixture=(mode == "fixture"))
    return TestClient(app), ledger


def headers():
    return {"Authorization": f"Bearer {KEY}"}


def test_product_api_requires_auth(tmp_path):
    c,_=client(tmp_path)
    r=c.post("/v1/retrieve",json={"query":"Wanneer gebruik je de risicofactorenscore?"})
    assert r.status_code==401
    assert r.json()["detail"]["code"]=="missing_api_key"


def test_invalid_key_rejected(tmp_path):
    c,_=client(tmp_path)
    r=c.get("/v1/documents",headers={"Authorization":"Bearer wrong"})
    assert r.status_code==401


def test_fixture_retrieve_contract_and_source(tmp_path):
    c,_=client(tmp_path)
    r=c.post("/v1/retrieve",headers=headers(),json={"query":"Welke score geldt vanaf 60 jaar bij fractuurrisico?","top_k":5})
    assert r.status_code==200
    data=r.json()
    assert data["status"]=="retrieve"
    assert data["answerability"]=="supported"
    assert data["synthetic_fixture"] is True
    assert data["request_id"]
    assert data["tenant_id"]=="test-tenant"
    assert data["results"]
    first=data["results"][0]
    assert first["knowledge_object_id"]
    assert first["source"]["title"]
    assert "version" in first["source"]
    assert "hybrid_rrf" in first["scores"]


def test_no_answer_abstains(tmp_path):
    c,_=client(tmp_path)
    data=c.post("/v1/retrieve",headers=headers(),json={"query":"Wat is de aanbevolen dosering morfine bij nierfalen?"}).json()
    assert data["status"]=="abstain"
    assert data["answerability"]=="insufficient_evidence"
    assert data["results"]==[]


def test_entitlement_filters_before_retrieval(tmp_path):
    c,_=client(tmp_path,reg=registry(docs=("another-document",)))
    data=c.post("/v1/retrieve",headers=headers(),json={"query":"Welke score geldt vanaf 60 jaar?"}).json()
    assert data["status"]=="abstain"
    assert data["reason"]=="empty_published_corpus"


def test_explicit_unauthorized_document_filter_is_403(tmp_path):
    c,_=client(tmp_path)
    r=c.post("/v1/retrieve",headers=headers(),json={"query":"score", "filters":{"document_ids":["secret-doc"]}})
    assert r.status_code==403
    assert r.json()["detail"]["code"]=="document_not_entitled"


def test_knowledge_outside_entitlement_is_not_disclosed(tmp_path):
    c,_=client(tmp_path,reg=registry(docs=("another-document",)))
    r=c.get("/v1/knowledge/vvn-osteoporose-fractuurpreventie-2024-p015-score-01",headers=headers())
    assert r.status_code==404


def test_top_k_tenant_limit(tmp_path):
    c,_=client(tmp_path,reg=registry(max_top_k=2))
    r=c.post("/v1/retrieve",headers=headers(),json={"query":"fractuurrisico", "top_k":3})
    assert r.status_code==400
    assert r.json()["detail"]["code"]=="top_k_exceeds_tenant_limit"


def test_scope_is_enforced(tmp_path):
    c,_=client(tmp_path,reg=registry(scopes=("retrieve",)))
    r=c.get("/v1/documents",headers=headers())
    assert r.status_code==403
    assert r.json()["detail"]["code"]=="scope_denied"


def test_usage_ledger_hashes_query_not_plaintext(tmp_path):
    c,ledger=client(tmp_path)
    query="Welke score geldt vanaf 60 jaar bij fractuurrisico?"
    c.post("/v1/retrieve",headers=headers(),json={"query":query})
    import sqlite3
    with sqlite3.connect(ledger.db_path) as con:
        row=con.execute("SELECT query_sha256 FROM api_usage WHERE endpoint='/v1/retrieve'").fetchone()
        schema=' '.join(x[0] or '' for x in con.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall())
    assert row and len(row[0])==64
    assert query not in schema
    assert query not in ledger.db_path.read_bytes().decode('latin1',errors='ignore')


def test_usage_summary(tmp_path):
    c,_=client(tmp_path)
    c.post("/v1/retrieve",headers=headers(),json={"query":"fractuurrisico"})
    r=c.get("/v1/usage",headers=headers())
    assert r.status_code==200
    assert r.json()["requests"]==1


def test_documents_and_updates_are_tenant_scoped(tmp_path):
    c,_=client(tmp_path)
    docs=c.get("/v1/documents",headers=headers()).json()["documents"]
    assert len(docs)==1 and docs[0]["document_id"]==DOC
    updates=c.get("/v1/updates",headers=headers()).json()["updates"]
    assert len(updates)==1
    assert DOC in updates[0]["documents"]


def test_fixture_requires_explicit_allow_flag(tmp_path):
    ps=paths(tmp_path)
    try:
        create_product_app("fixture",paths=ps,tenant_registry=registry())
    except ValueError as exc:
        assert "fixture mode is disabled" in str(exc)
    else:
        raise AssertionError("fixture mode should require explicit enable")


def test_real_mode_is_fail_closed_even_with_valid_tenant(tmp_path):
    c,_=client(tmp_path,mode="real")
    health=c.get("/v1/health").json()
    assert health["synthetic_fixture"] is False
    data=c.post("/v1/retrieve",headers=headers(),json={"query":"fractuurrisico"}).json()
    assert data["status"]=="abstain"
    assert data["reason"]=="empty_published_corpus"


def test_request_id_is_returned(tmp_path):
    c,_=client(tmp_path)
    r=c.get("/v1/documents",headers={**headers(),"X-Request-ID":"client-req-123"})
    assert r.headers["X-Request-ID"]=="client-req-123"
    assert r.json()["request_id"]=="client-req-123"


def test_rate_limit(tmp_path):
    ticks=[0.0]
    limiter=SlidingWindowRateLimiter(now=lambda: ticks[0])
    c,_=client(tmp_path,reg=registry(rpm=1),limiter=limiter)
    assert c.get("/v1/documents",headers=headers()).status_code==200
    r=c.get("/v1/documents",headers=headers())
    assert r.status_code==429
    assert r.json()["detail"]["code"]=="rate_limit_exceeded"

def test_specific_topic_entitlement_does_not_include_untagged_records(tmp_path):
    reg=TenantRegistry([TenantPolicy.from_dict({
        "tenant_id":"topic-only","name":"Topic only","enabled":True,
        "api_key_sha256":hash_api_key(KEY),"scopes":["retrieve"],
        "allowed_document_ids":["*"],"allowed_topics":["nonexistent-topic"],
        "requests_per_minute":100,"max_top_k":5,
    })])
    c,_=client(tmp_path,reg=reg)
    data=c.post("/v1/retrieve",headers=headers(),json={"query":"fractuurrisico"}).json()
    assert data["status"]=="abstain"
    assert data["reason"]=="empty_published_corpus"

def test_product_state_reloads_changed_retrieval_file(tmp_path):
    import json, shutil
    base=paths(tmp_path)
    fixture_copy=tmp_path/"records.jsonl"
    shutil.copy(base.fixture_records, fixture_copy)
    p=ProductPaths(
        real_records=base.real_records, fixture_records=fixture_copy, real_published=base.real_published,
        lexical_config=base.lexical_config, vector_config=base.vector_config, hybrid_config=base.hybrid_config,
        tenant_config=base.tenant_config, usage_db=base.usage_db,
    )
    app=create_product_app("fixture",paths=p,tenant_registry=registry(),usage_ledger=UsageLedger(p.usage_db),allow_fixture=True)
    c=TestClient(app)
    assert c.get("/v1/health").json()["published_retrieval_records"]==19
    lines=fixture_copy.read_text(encoding="utf-8").splitlines()
    fixture_copy.write_text(lines[0]+"\n",encoding="utf-8")
    # Tenant-scoped endpoint triggers reload.
    docs=c.get("/v1/documents",headers=headers()).json()["documents"]
    assert docs[0]["knowledge_object_count"]==1
