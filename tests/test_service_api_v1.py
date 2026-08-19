from fastapi.testclient import TestClient

from src.service_app import create_app


def test_real_mode_is_default_fail_closed():
    client = TestClient(create_app("real"))
    st = client.get("/system/status").json()
    assert st["mode"] == "real"
    assert st["synthetic_fixture_mode"] is False
    assert st["retrieval_record_count"] == 0
    r = client.post("/search", json={"query": "Wanneer verwijs je bij een hoge risicofactorenscore?", "top_k": 5}).json()
    assert r["behavior"] == "abstain"
    assert r["reason"] == "empty_published_corpus"
    assert r["results"] == []


def test_real_mode_does_not_expose_unpublished_knowledge():
    client = TestClient(create_app("real"))
    oid = "vvn-osteoporose-fractuurpreventie-2024-p015-score-01"
    res = client.get(f"/knowledge/{oid}")
    assert res.status_code == 404
    assert res.json()["detail"] == "object_not_published"


def test_fixture_mode_is_visibly_synthetic_and_retrieves():
    client = TestClient(create_app("fixture"))
    st = client.get("/system/status").json()
    assert st["synthetic_fixture_mode"] is True
    assert "SYNTHETIC" in st["warning"]
    assert st["retrieval_record_count"] > 0
    r = client.post("/search", json={"query": "Welke score geldt vanaf 60 jaar bij fractuurrisico?", "top_k": 5}).json()
    assert r["synthetic_fixture_mode"] is True
    assert r["behavior"] == "retrieve"
    assert r["results"]
    assert all(x.get("object_id") for x in r["results"])
    assert all("source_title" in x for x in r["results"])


def test_fixture_no_answer_abstains():
    client = TestClient(create_app("fixture"))
    r = client.post("/search", json={"query": "Wat is de aanbevolen dosering morfine bij nierfalen?", "top_k": 5}).json()
    assert r["behavior"] == "abstain"
    assert r["results"] == []


def test_explain_exposes_child_gates_and_thresholds():
    client = TestClient(create_app("fixture"))
    r = client.post("/retrieval/explain", json={"query": "Wanneer gebruik je de risicofactorenscore?", "top_k": 5}).json()
    assert r["policy"]["search_scope"] == "synthetic_fixture_only"
    assert "lexical_thresholds" in r["policy"]
    assert "vector_threshold" in r["policy"]
    assert "lexical" in r and "vector" in r and "hybrid" in r


def test_fixture_knowledge_is_labelled_and_has_preview():
    client = TestClient(create_app("fixture"))
    oid = "vvn-osteoporose-fractuurpreventie-2024-p015-score-01"
    res = client.get(f"/knowledge/{oid}")
    assert res.status_code == 200
    data = res.json()
    assert data["synthetic"] is True
    assert "not published" in data["warning"]
    assert data["retrieval_record"]["metadata"]["object_id"] == oid


def test_sources_documents_releases_and_ui():
    real = TestClient(create_app("real"))
    assert real.get("/sources").status_code == 200
    docs = real.get("/documents").json()
    assert len(docs) == 1
    assert docs[0]["published_count"] == 0
    assert real.get("/releases").json() == []
    html = real.get("/")
    assert html.status_code == 200
    assert "V&amp;VN Data Services Inspector" not in html.text  # source HTML contains literal text
    assert "V&VN Data Services Inspector" in html.text

    fixture = TestClient(create_app("fixture"))
    releases = fixture.get("/releases").json()
    assert len(releases) == 1
    assert releases[0]["synthetic"] is True
