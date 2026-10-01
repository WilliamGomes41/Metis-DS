"""Decision review copy explains extraction without changing review authority.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import fitz
import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from tests.test_decision_graph_chain import _accounts, _console, _ingest_boom, policy


@pytest.mark.parametrize("source", ["pdf", "bundle", "export"])
def test_decision_review_explains_types_without_mutating_evidence(tmp_path, source):
    console = _console(tmp_path)
    accounts = _accounts(console)
    kwargs = {}
    if source != "export":
        with fitz.open() as doc:
            page = doc.new_page()
            page.insert_text((70, 80), "Plan:\n- Neem contact op.\n- Maak een afspraak."
                             if source == "bundle" else "Is er valrisico?")
            kwargs = dict(data=doc.tobytes(), filename="boom.pdf", content_type="application/pdf")
    sid = _ingest_boom(console, accounts, named_reviewers=[], review_policy=policy(accounts), **kwargs)["snapshot_id"]
    before = deepcopy(console.snapshot_objects(sid))
    envelope = deepcopy(console._envelope(sid))
    client = TestClient(create_console_app(console))
    assert client.get(f"/review?document={sid}", follow_redirects=False).status_code == 401
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    for obj in before:
        if obj["object_type"] == "document":
            continue
        html = client.get(f"/review?document={sid}&object={obj['object_id']}").text
        assert 'value="path"' in html and "Pad — route of resultaatbundel" in html
        assert 'value="node"' in html and "Knoop — vraag of beslispunt" in html
        assert 'value="outcome"' in html and "Uitkomst — afsluitend advies" in html
        assert "scorelijstitem" in html and "Een pad is zelf geen advies" in html
        assert "Metis stelt voor" not in html
        assert "Huidige indeling:" in html
        if source == "pdf":
            assert "standaard het type Knoop" in html
            assert "geen inhoudelijke classificatie" in html
        elif source == "bundle":
            role = obj["metadata"]["result_bundle"]["role"]
            assert ("automatisch gegroepeerd" if role == "container" else "automatisch afgesplitst") in html
        else:
            assert "standaard het type Knoop" not in html
    graph = client.get(f"/review/decision-graph?document={sid}")
    assert graph.status_code == 200
    assert "Verbinding 1" in graph.text and "Soort verbinding" in graph.text
    assert "Een route bestaat uit opeenvolgende stappen" in graph.text
    assert "Verbindingen opslaan" in graph.text
    assert console.snapshot_objects(sid) == before
    assert console._envelope(sid) == envelope
