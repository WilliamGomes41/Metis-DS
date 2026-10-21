"""Decision review keeps evidence separate from help without changing authority.

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
def test_decision_review_moves_type_explanations_to_help_without_mutating_evidence(tmp_path, source):
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
        assert "scorelijstitem" not in html and "Een pad is zelf geen advies" not in html
        assert "Metis stelt voor" not in html
        assert "Huidige indeling:" in html
        assert "standaard het type Knoop" not in html
        assert "automatisch gegroepeerd" not in html
        assert "automatisch afgesplitst" not in html
    help_page = client.get("/help/review")
    assert help_page.status_code == 200
    assert "scorelijstitem" in help_page.text and "Een pad is zelf geen advies" in help_page.text
    assert "geen inhoudelijke classificatie" in help_page.text
    graph = client.get(f"/review/decision-graph?document={sid}")
    assert graph.status_code == 200
    assert "Verbinding 1" in graph.text and "Soort verbinding" in graph.text
    assert "Een route bestaat uit opeenvolgende stappen" not in graph.text
    assert 'href="/help/review"' in graph.text
    assert "Verbindingen opslaan" in graph.text
    assert console.snapshot_objects(sid) == before
    assert console._envelope(sid) == envelope
