"""#854: Documentdiagnose leads with one verdict and plain-language findings.

Same data, same authorization and the same reads as before; only presentation.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
"""
from __future__ import annotations

from copy import deepcopy
import re

import pytest
from fastapi.testclient import TestClient

from src.extract_coverage_v1 import DUTCH_STATUS_LABELS
from src.integrity_kernel import stamp_canonical_hashes
from src.operations_console_app import ERROR_COPY
from src.processing_diagnostics_v1 import processing_diagnostics
from src.review_ledger import read_events
from tests.semantic_fixture_support import bind_fixture_selections, install_fixture_history

PASSWORD = "docdiag-854-secret"
UNKNOWN = "docdiag_unknown_reason_854"
BLOCKED_CODES = (
    ["incomplete_sentence", "recommendation_evidence_missing", UNKNOWN],
    ["recommendation_evidence_missing", "type_contract_incomplete", UNKNOWN],
)


def _system(tmp_path, *, production_console):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "sources" / "private", runtime=tmp_path / "runtime")
    uploader = console.create_account(username="uploader.854", password=PASSWORD, roles=("researcher", "publisher"))
    console.create_account(username="researcher.854", password=PASSWORD, roles=("researcher",))
    reviewer = console.create_account(username="reviewer.854", password=PASSWORD, roles=("reviewer",))
    console.create_account(username="publisher.854", password=PASSWORD, roles=("publisher",))
    receipt = console.ingest(
        actor_id=uploader["account_id"], filename="diagnose.html",
        data=(b"<html><body><h1>Richtlijn</h1><h2>Aanbevelingen</h2>"
              b"<p>Bespreek passende ondersteuning met de client.</p>"
              b"<p>Leg de gemaakte afspraken vast.</p>"
              b"<p>Evalueer de afspraken elke maand.</p></body></html>"),
        content_type="text/html", ingest_kind="new", title="Diagnose 854", version="1.0",
        date="2026-10-26", live_url="", class_="richtlijn", family="diagnose854",
        named_reviewers=[reviewer["account_id"]])
    sid = str(receipt["snapshot_id"])
    rows = console._load_objects(sid)
    units = [row for row in rows if row.get("object_type") not in {"document", "heading"}
             and row.get("proposed_object_type") != "heading"]
    assert len(units) >= len(BLOCKED_CODES)
    for index, row in enumerate(units):
        codes = BLOCKED_CODES[index] if index < len(BLOCKED_CODES) else []
        row.setdefault("metadata", {})["admission"] = {
            "gate_result": "blocked" if codes else "allowed", "reason_codes": list(codes),
            "proposed_type": "recommendation", "section_role": "primary",
            "section_path": ["Richtlijn", "Aanbevelingen"]}
        stamp_canonical_hashes(row)
    install_fixture_history(console, sid, rows)
    return console, sid


def _client(console, production_app, username):
    client = TestClient(production_app(console), base_url="https://testserver")
    assert client.post("/login", data={"username": username, "password": PASSWORD},
                       follow_redirects=False).status_code == 303
    return client


def _formation_incomplete(console, monkeypatch, **extra):
    original = console.processing_status

    def status(document, *, actor_id):
        result = dict(original(document, actor_id=actor_id))
        result.update({"formation_incomplete": True,
                       "formation_progress": {"planned_task_count": 3, "terminal_task_count": 3,
                                              "pending_task_count": 0}}, **extra)
        return result
    monkeypatch.setattr(console, "processing_status", status)


def _fixed_status(console, monkeypatch, status):
    monkeypatch.setattr(console, "processing_status", lambda document, *, actor_id: dict(status))


def _without_details(html: str) -> str:
    return re.sub(r"<details\b.*?</details>", "", html, flags=re.S)


def _page(client, sid):
    response = client.get("/inzicht/document", params={"document": sid})
    assert response.status_code == 200, response.text
    return response.text


@pytest.fixture
def system(tmp_path, production_console):
    return _system(tmp_path, production_console=production_console)


def test_reviewer_sees_verdict_first_then_steps_actions_findings_and_evidence(system, monkeypatch, *, production_app):
    console, sid = system
    _formation_incomplete(console, monkeypatch)
    diagnostics = processing_diagnostics(console.snapshot_objects(sid))
    html = _page(_client(console, production_app, "reviewer.854"), sid)
    order = [html.index(text) for text in ("Niet publiceerbaar", "Wat Metis met dit document deed",
                                           "Wat er nu moet gebeuren", "Wat de controle vond",
                                           "Bewijs en downloads")]
    assert order == sorted(order)
    verdict = html[html.index('class="diagnosis-verdict"'):html.index("Wat Metis met dit document deed")]
    assert "<dd>3/3</dd>" in verdict
    assert f'<dd>{int(diagnostics["issue_occurrence_count"])}</dd>' in verdict
    assert f'<dd>{int(diagnostics["blocked_candidate_count"])}</dd>' in verdict
    blocked = re.findall(r'<li class="blocked">.*?</li>', html, flags=re.S)
    assert len(blocked) == 1 and "Passages gecontroleerd" in blocked[0]
    actions = html[html.index("Wat er nu moet gebeuren"):html.index("Wat de controle vond")]
    points = [int(value) for value in re.findall(r'data-label="Punten" class="num">(\d+)<', actions)]
    assert points == sorted(points, reverse=True)
    assert len(points) == len(diagnostics["by_family"])
    assert actions.count(f'href="/review?document={sid}&amp;task=repair"') == len(points)
    assert "Wie" not in actions and "Redacteur" not in actions
    assert "De passage is niet los te lezen" in html  # plain-language family text


def test_codes_only_inside_technical_details_and_unclassified_code_once(system, monkeypatch, *, production_app):
    console, sid = system
    _formation_incomplete(console, monkeypatch)
    diagnostics = processing_diagnostics(console.snapshot_objects(sid))
    html = _page(_client(console, production_app, "reviewer.854"), sid)
    visible = _without_details(html)
    for code in diagnostics["by_reason_code"]:
        assert code in html
        assert code not in visible, code
    assert "source_formation_incomplete" not in visible
    assert html.count(UNKNOWN) == 1
    assert "Technische details" in html


@pytest.mark.parametrize("username", ["reviewer.854", "researcher.854", "uploader.854"])
def test_page_has_no_internal_jargon_or_raw_json(system, monkeypatch, username, *, production_app):
    console, sid = system
    _formation_incomplete(console, monkeypatch)
    client = _client(console, production_app, username)
    html = _page(client, sid)
    for forbidden in ("admission-contract", "root cause", "<pre"):
        assert forbidden not in html
    assert "/inzicht/document/verwerkingsspoor?" in html
    assert client.get("/inzicht/document/verwerkingsspoor", params={"document": sid}).status_code == 200


def test_raw_diagnostics_remain_downloadable_with_real_route_labels(system, monkeypatch, *, production_app):
    console, sid = system
    client = _client(console, production_app, "reviewer.854")
    html = _page(client, sid)
    for label in ("Bronpassages", "Diagnostiek (JSON)", "Detaildiagnostiek (JSON)",
                  "Verwerkingsbewijs als CSV-pakket", "Verwerkingsspoor (JSON)"):
        assert label in html
    for path in ("diagnostiek", "detaildiagnostiek"):
        assert client.get("/inzicht/document/" + path, params={"document": sid}).status_code == 200


def test_coverage_is_a_five_column_table_without_filter_or_script(system, monkeypatch, *, production_app):
    console, sid = system
    html = _page(_client(console, production_app, "reviewer.854"), sid)
    table = re.search(r'<table class="diagnosis-coverage.*?</table>', html, flags=re.S)
    assert table, "coverage table missing"
    headers = re.findall(r'<th scope="col"[^>]*>(.*?)</th>', table.group(0))
    assert headers[1:] == list(DUTCH_STATUS_LABELS.values())
    diagnosis = html[html.index("<h1>"):html.rindex('class="export-options"')]
    assert "<script" not in diagnosis.lower()
    assert "alleen koppen met open punten" not in html.lower()


def test_read_budget_one_objects_read_one_ledger_read_and_no_writes(system, monkeypatch, *, production_app):
    console, sid = system
    import src.review_ledger as ledger
    client = _client(console, production_app, "reviewer.854")
    before = (deepcopy(console.snapshot_objects(sid)), console.objects_revision(sid),
              deepcopy(console._envelope(sid)), read_events(console._ledger_path))
    calls = {"objects": 0, "ledger": 0}
    original_objects, original_events = console.snapshot_objects, ledger.read_events

    def objects(*args, **kwargs):
        calls["objects"] += 1
        return original_objects(*args, **kwargs)

    def events(*args, **kwargs):
        calls["ledger"] += 1
        return original_events(*args, **kwargs)
    monkeypatch.setattr(console, "snapshot_objects", objects)
    monkeypatch.setattr(ledger, "read_events", events)
    html = _page(client, sid)
    assert 'class="diagnosis-verdict"' in html
    assert calls["objects"] <= 1 and calls["ledger"] <= 1, calls
    monkeypatch.undo()
    assert before == (console.snapshot_objects(sid), console.objects_revision(sid),
                      console._envelope(sid), read_events(console._ledger_path))


def test_publisher_without_processing_access_sees_no_families_codes_or_counts(system, monkeypatch, *, production_app):
    console, sid = system
    diagnostics = processing_diagnostics(console.snapshot_objects(sid))
    html = _page(_client(console, production_app, "publisher.854"), sid)
    assert "Verwerkingsdiagnostiek is beschikbaar voor onderzoekers en aangewezen reviewers." in html
    assert 'class="diagnosis-verdict"' in html
    for text in ("De passage is niet los te lezen", "Zelfstandigheid van passage", "Controlepunten",
                 "Passages gecontroleerd", UNKNOWN, *diagnostics["by_reason_code"]):
        assert text not in html, text
    assert "/inzicht/document/publicatiebewijs?" in html
    assert "/inzicht/document/blokkade?" not in html


def test_researcher_keeps_reviewer_only_passage_boundary(system, monkeypatch, *, production_app):
    console, sid = system
    _formation_incomplete(console, monkeypatch)
    html = _page(_client(console, production_app, "researcher.854"), sid)
    assert 'class="diagnosis-verdict"' in html
    assert "Passagediagnostiek en passage-exports zijn beschikbaar voor de aangewezen reviewer." in html
    assert "De passage is niet los te lezen" not in html and UNKNOWN not in html
    assert "/inzicht/document/passages?" not in html
    assert "/inzicht/document/blokkade?" in html


@pytest.mark.parametrize(("status", "label"), [
    ({"state": "failed", "error_code": "processing_attempt_limit_reached",
      "reason_code": "processing_attempt_limit_reached", "retry_allowed": False,
      "retry_not_before": None}, "Niet publiceerbaar"),
    ({"state": "running", "reason_code": "processing_attempt_in_progress", "retry_allowed": False,
      "retry_not_before": None}, "Verwerking loopt"),
    ({"state": "failed", "error_code": "source_processing_strategy_unconfigured",
      "reason_code": "source_processing_strategy_unconfigured", "retry_allowed": True,
      "retry_not_before": "2026-10-27T10:00:00+00:00"}, "Niet publiceerbaar"),
])
def test_failed_limit_and_running_keep_current_copy_and_controls(system, monkeypatch, status, label, *, production_app):
    console, sid = system
    _fixed_status(console, monkeypatch, status)
    html = _page(_client(console, production_app, "uploader.854"), sid)
    verdict = html[html.index('class="diagnosis-verdict"'):html.index("Wat Metis met dit document deed")]
    assert label in verdict
    code = status["error_code"] if status.get("error_code") else status["reason_code"]
    assert ERROR_COPY.get(code, "Controleer de actuele verwerking.") in html
    assert (status["retry_not_before"] or "niet van toepassing") in html
    assert ('href="/source-selection?' in html) is bool(status["retry_allowed"])
    limit = status["reason_code"] == "processing_attempt_limit_reached"
    assert ('action="/tree/processing-recovery"' in html) is limit


def test_recovery_form_only_for_publisher_uploader_or_named_reviewer(system, monkeypatch, *, production_app):
    console, sid = system
    _fixed_status(console, monkeypatch, {"state": "failed", "reason_code": "processing_attempt_limit_reached",
                                         "error_code": "processing_attempt_limit_reached", "retry_allowed": False})
    assert 'action="/tree/processing-recovery"' in _page(_client(console, production_app, "uploader.854"), sid)
    assert 'Een herstelpoging autoriseren' in _page(_client(console, production_app, "uploader.854"), sid)
    for username in ("reviewer.854", "researcher.854"):
        assert 'action="/tree/processing-recovery"' not in _page(_client(console, production_app, username), sid)


def test_preserved_panels_source_pages_view_check_blockage_and_publication_evidence(system, monkeypatch, *, production_app):
    console, sid = system
    import src.insight_v1 as insight
    import src.view_check as view_check
    monkeypatch.setattr(insight, "_source_pages_html", lambda envelope, diagnostic, document: '<p id="pages-854">P</p>')
    monkeypatch.setattr(view_check, "panel", lambda app, state, account, document, attempt: '<section id="vc-854"></section>')
    reviewer = _page(_client(console, production_app, "reviewer.854"), sid)
    assert 'id="pages-854"' in reviewer and 'id="vc-854"' in reviewer
    assert f'href="/inzicht/document/blokkade?document={sid}"' in reviewer
    assert "/inzicht/document/publicatiebewijs?" not in reviewer
    assert "Reviewinteracties" in reviewer and "Passages en brondekking" in reviewer
    uploader = _page(_client(console, production_app, "uploader.854"), sid)
    assert "/inzicht/document/publicatiebewijs?" in uploader and 'id="pages-854"' in uploader
    publisher = _page(_client(console, production_app, "publisher.854"), sid)
    assert 'id="pages-854"' not in publisher and 'id="vc-854"' in publisher


def test_shared_review_helpers_are_unchanged_for_other_callers(system):
    console, sid = system
    from src.operations_console_app import _coverage_panel, _processing_diagnostics_html
    objects = console.snapshot_objects(sid)
    assert 'class="processing-diagnostics"' in _processing_diagnostics_html(objects)
    assert 'class="review-coverage"' in _coverage_panel(objects)
