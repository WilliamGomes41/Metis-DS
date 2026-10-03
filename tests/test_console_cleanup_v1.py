"""Issue #454: compact document workspaces and authorized maintenance/exports.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs

from src.operations_console_app import _document_list_page
from src.review_ledger import append_event, read_events
from src.review_workboard_v1 import _review_activity_status
from test_vsa_review_workboard_v1 import _client, _login, _system


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def documents(self):
        return [attrs for tag, attrs in self.tags if tag == "details"
                and "document-disclosure" in attrs.get("class", "")]


def test_ingest_is_focused_and_documents_are_searchable_disclosures(tmp_path):
    console, _, _, _ = _system(tmp_path)
    client = _client(console)
    _login(client, "researcher.anne")
    ingest = client.get("/ingest")
    assert ingest.status_code == 200
    assert "Ingeleverde documenten" not in ingest.text
    assert '<form method="post" action="/ingest"' in ingest.text
    documents = client.get("/tree")
    assert documents.status_code == 200
    assert len(Tags(documents.text).documents()) == 2
    assert all("open" not in attrs for attrs in Tags(documents.text).documents())
    assert "freeze-bytes" not in documents.text
    assert "Same-model" not in documents.text
    assert "Deze wijziging vereist een nieuwe beoordeling" in documents.text
    found = client.get("/tree", params={"q": "document b"})
    assert len(Tags(found.text).documents()) == 1
    assert "Document B" in found.text and "Document A" not in found.text
    assert "Geen documenten gevonden" in client.get("/tree?q=onvindbaar").text


def test_search_reaches_later_pages_is_bounded_and_escapes_input():
    rows = [{"title": f"Document {i}", "family": "zorg"} for i in range(103)]
    visible, html = _document_list_page(rows, q="", page=2, path="/tree")
    assert len(visible) == 25 and visible[0]["title"] == "Document 25"
    assert "pagina 2 van 5" in html
    visible, _ = _document_list_page(rows, q="zorg 102", page=99, path="/tree")
    assert visible == [rows[102]]
    assert _document_list_page(rows, q="", page=-10, path="/tree")[0] == rows[:25]
    _, html = _document_list_page(rows, q='"><script>alert(1)</script>', page=1, path="/tree")
    assert "<script>" not in html


def test_review_read_is_collapsed_and_only_human_decisions_start_review(tmp_path):
    console, _, first, _ = _system(tmp_path)
    snapshot = first["snapshot_id"]
    client = _client(console)
    _login(client, "reviewer.a")
    before = read_events(console._ledger_path)
    revision = console.objects_revision(snapshot)
    landing = client.get("/review")
    assert landing.status_code == 200
    assert "Nog niet gestart" in landing.text
    assert all("open" not in attrs for attrs in Tags(landing.text).documents())
    assert "Reviewinteracties" not in landing.text
    assert "Passages herstellen" not in landing.text
    opened = client.get("/review", params={"document": snapshot, "q": "Document A"})
    assert "open" in Tags(opened.text).documents()[0]
    assert "Jouw open werk" in opened.text and "Reviewvoortgang" in opened.text
    assert read_events(console._ledger_path) == before
    assert console.objects_revision(snapshot) == revision
    append_event(console._ledger_path, event_type="clinical_review_approve", object_id="automatic",
                 object_version="1", actor="Metis", details={"snapshot_id": snapshot})
    assert "Review: Nog niet gestart" in client.get("/review").text
    heading = next(obj for obj in console.snapshot_objects(snapshot)
                   if obj.get("object_type") == "heading" or obj.get("proposed_object_type") == "heading")
    response = client.post("/review/headings/batch-confirm", data={
        "snapshot_id": snapshot, "snapshot_revision": revision,
        "object_ids": [heading["object_id"]],
    }, follow_redirects=False)
    assert response.status_code == 303
    assert "Review: Gestart" in client.get("/review").text


def test_automatic_progress_is_not_human_start_and_waiting_is_not_complete():
    item = {"snapshot_id": "s", "lifecycle_status": {"workflow_status": "reviewing"},
            "source_passage_review_complete": False, "review_duties": 1,
            "closure_gap_count": 0, "blocked_count": 0, "progress": {"done": 2}}
    assert _review_activity_status(item, set()) == "Nog niet gestart"
    assert _review_activity_status(item, {"s"}) == "Gestart"
    item.update(source_passage_review_complete=True, review_duties=0)
    assert _review_activity_status(item, {"s"}) == "Afgerond"
    item.update(blocked_count=1)
    assert _review_activity_status(item, {"s"}) == "Gestart"


def test_exports_and_technical_repair_preserve_document_authorization(tmp_path):
    console, _, first, second = _system(tmp_path)
    client = _client(console)
    assert client.get("/settings/technical/exports").status_code == 401
    _login(client, "reviewer.a")
    snapshot = first["snapshot_id"]
    landing = client.get("/settings/technical/exports")
    assert landing.status_code == 200
    assert "Document A" in landing.text and "Document B" not in landing.text
    opened = client.get("/settings/technical/exports", params={"document": snapshot})
    downloads = [attrs["href"] for tag, attrs in Tags(opened.text).tags
                 if tag == "a" and attrs.get("href", "").startswith((
                     "/review/passages-export?", "/review/processing-diagnostics"))]
    assert len(downloads) == 4
    for link in downloads:
        response = client.get(link)
        assert response.status_code == 200
        denied = client.get(link.replace(snapshot, second["snapshot_id"]))
        assert denied.status_code == 400
        assert "reviewer_not_named_on_snapshot" in denied.text
    assert client.get("/settings/technical/exports", params={"document": second["snapshot_id"]}).status_code == 400
    technical = client.get("/settings/technical", params={"document": snapshot})
    assert technical.status_code == 200
    assert "Verwerkingsproblemen herstellen" in technical.text
    assert "Reviewinteracties" in technical.text
    redirect = client.get("/review", params={"document": snapshot, "task": "repair"}, follow_redirects=False)
    assert redirect.status_code == 200
    assert "Passages corrigeren" in redirect.text
    assert "Diagnostiek en brondekking" not in redirect.text
    _login(client, "publisher.carla")
    assert client.get("/settings/technical/exports").status_code == 403


def test_task_back_link_keeps_selected_document_and_search(tmp_path):
    console, _, first, _ = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.a")
    response = client.get("/review", params={"document": first["snapshot_id"],
                          "task": "structure", "q": "Document A", "page": 2})
    assert response.status_code == 200
    back = [attrs["href"] for tag, attrs in Tags(response.text).tags
            if tag == "a" and "q=Document+A" in attrs.get("href", "")]
    assert back
    query = parse_qs(urlsplit(back[0]).query)
    assert query["document"] == [first["snapshot_id"]]
    assert query["q"] == ["Document A"] and query["page"] == ["2"]
