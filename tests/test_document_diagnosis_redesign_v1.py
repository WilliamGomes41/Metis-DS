"""#854: Documentdiagnose leads with one verdict and plain-language findings.

Same data, same authorization and the same reads as before; only presentation.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
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
    assert actions.count(f'href="/source-selection?document={sid}&amp;task=repair"') == len(points)
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


@pytest.mark.parametrize("username", ["reviewer.854", "researcher.854", "uploader.854", "publisher.854"])
def test_read_budget_one_objects_read_one_ledger_read_and_no_writes(system, monkeypatch, username, *, production_app):
    console, sid = system
    import src.review_ledger as ledger
    client = _client(console, production_app, username)
    before = (deepcopy(console.snapshot_objects(sid)), console.objects_revision(sid),
              deepcopy(console._envelope(sid)), read_events(console._ledger_path))
    calls = {"objects": 0, "ledger": 0, "loads": 0}
    original_objects, original_events = console.snapshot_objects, ledger.read_events
    original_load = console._load_objects

    def objects(*args, **kwargs):
        calls["objects"] += 1
        return original_objects(*args, **kwargs)

    def events(*args, **kwargs):
        calls["ledger"] += 1
        return original_events(*args, **kwargs)
    def load(*args, **kwargs):
        calls["loads"] += 1
        return original_load(*args, **kwargs)
    monkeypatch.setattr(console, "snapshot_objects", objects)
    monkeypatch.setattr(ledger, "read_events", events)
    monkeypatch.setattr(console, "_load_objects", load)
    html = _page(client, sid)
    assert 'class="diagnosis-verdict"' in html
    assert calls["objects"] <= 1 and calls["ledger"] <= 1, calls
    assert calls["loads"] <= (0 if username == "publisher.854" else 1), calls
    assert calls["ledger"] == (1 if username == "reviewer.854" else 0), calls
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


def _with_last_attempt(console, monkeypatch, diagnostic):
    original = console._envelope

    def envelope(document):
        result = dict(original(document))
        result["processing_attempts"] = [*(result.get("processing_attempts") or []), {"diagnostic": diagnostic}]
        return result
    monkeypatch.setattr(console, "_envelope", envelope)


def _blocked_step(html):
    blocked = re.findall(r'<li class="blocked"><h3>(\d)\.', html)
    assert len(blocked) == 1, blocked
    return int(blocked[0])


def _clear_admission_blocks(console, sid):
    rows = console.snapshot_objects(sid)
    for row in rows:
        admission = (row.get("metadata") or {}).get("admission")
        if admission:
            admission.update(gate_result="allowed", reason_codes=[])
            stamp_canonical_hashes(row)
    install_fixture_history(console, sid, rows)


@pytest.mark.parametrize("username", ["reviewer.854", "researcher.854", "uploader.854"])
@pytest.mark.parametrize("has_blockers", [True, False])
def test_completed_processing_verdict_agrees_with_admission_blockers(
        system, monkeypatch, has_blockers, username, *, production_app):
    from src.knowledge_path_v1 import knowledge_publication_blockers
    console, sid = system
    if not has_blockers:
        _clear_admission_blocks(console, sid)
    assert any("admission_blocked" in knowledge_publication_blockers(row)
               for row in console.snapshot_objects(sid)) is has_blockers
    _fixed_status(console, monkeypatch, {"state": "succeeded"})
    html = _page(_client(console, production_app, username), sid)
    label = re.search(r'<p class="diagnosis-label">(.*?)</p>', html, flags=re.S).group(1)
    assert ("Niet publiceerbaar" in label) is has_blockers
    assert ("Geen blokkade vastgelegd" in label) is (not has_blockers)
    if has_blockers:
        assert _blocked_step(html) == 4
    if username != "reviewer.854":
        for protected in (UNKNOWN, "Passages met controlepunten", "Controlepunten", "De passage is niet los te lezen"):
            assert protected not in html
        assert "/inzicht/document/passages?" not in html


@pytest.mark.parametrize("username", ["reviewer.854", "researcher.854", "uploader.854"])
@pytest.mark.parametrize("has_blockers", [False, True])
@pytest.mark.parametrize("last_state", ["succeeded", "failed"])
@pytest.mark.parametrize("restriction", ["limit", "cooldown"])
def test_retry_restriction_is_not_a_publication_failure_after_success(
        system, username, has_blockers, last_state, restriction, *, production_app):
    from datetime import datetime, timedelta, timezone
    console, sid = system
    if not has_blockers:
        _clear_admission_blocks(console, sid)
    envelope = deepcopy(console._envelope(sid))
    now = datetime.now(timezone.utc)
    limit = console._processing_limits().max_attempts
    total = limit if restriction == "limit" else 1
    envelope["processing_attempts"] = [
        {"attempt_id": f"pa_{index + 1:032x}", "command_id": f"retry-verdict-{index}",
         "version": "source-reprocessing-v3", "limits": console._processing_limits().record(),
         "expected_revision": console.objects_revision(sid),
         "actor_id": envelope["uploader_account_id"], "source_hash": envelope["sha256"],
         "source_version": envelope["version"], "kind": "retry",
         "state": last_state if index == total - 1 else "failed",
         "error_code": (None if index == total - 1 and last_state == "succeeded"
                        else "pre_review_llm_proposal_rejected"),
         "started_at": now.isoformat(), "finished_at": now.isoformat(),
         "expires_at": (now + timedelta(hours=1)).isoformat(),
         "retry_not_before": (now + timedelta(hours=1)).isoformat() if restriction == "cooldown" else None,
         "diagnostic": {"phase": "formation_accounted" if last_state == "succeeded" else "validation_rejected"}}
        for index in range(total)]
    with console._reprocessing_transaction(sid):
        console._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    actor = next(a for a in console.list_accounts() if a["username"] == username)
    status = console.processing_status(sid, actor_id=actor["account_id"])
    expected_reason = "processing_attempt_limit_reached" if restriction == "limit" else "processing_retry_cooldown"
    assert status["state"] == last_state and status["reason_code"] == expected_reason
    assert not status["retry_allowed"]
    html = _page(_client(console, production_app, username), sid)
    label = re.search(r'<p class="diagnosis-label">(.*?)</p>', html, flags=re.S).group(1)
    blocked = has_blockers or last_state == "failed"
    assert ("Niet publiceerbaar" in label) is blocked
    assert ("Geen blokkade vastgelegd" in label) is (not blocked)
    if blocked:
        assert _blocked_step(html) == 4
    else:
        assert '<li class="blocked">' not in html
    if last_state == "succeeded":
        lead = re.search(r'<div class="diagnosis-verdict".*?<p class="lead">(.*?)</p>', html, flags=re.S).group(1)
        assert ERROR_COPY[expected_reason] not in lead
        assert 'action="/tree/processing-recovery"' not in html


@pytest.mark.parametrize("state", ["failed", "expired", "interrupted", "incomplete_budget"])
@pytest.mark.parametrize("diagnostic,step", [({}, 1), ({"phase": "validation_rejected"}, 4)])
def test_unsuccessful_stored_state_without_error_code_is_still_shown_as_stopped(
        system, monkeypatch, state, diagnostic, step, *, production_app):
    console, sid = system
    _clear_admission_blocks(console, sid)
    _fixed_status(console, monkeypatch, {"state": state})
    _with_last_attempt(console, monkeypatch, diagnostic)
    html = _page(_client(console, production_app, "uploader.854"), sid)
    label = re.search(r'<p class="diagnosis-label">(.*?)</p>', html, flags=re.S).group(1)
    assert "Niet publiceerbaar" in label
    assert _blocked_step(html) == step


@pytest.mark.parametrize("pending,step", [(1, 2), (0, 4)])
def test_successful_attempt_at_retry_limit_keeps_open_formation_and_recovery_visible(
        system, monkeypatch, pending, step, *, production_app):
    console, sid = system
    _clear_admission_blocks(console, sid)
    _fixed_status(console, monkeypatch, {
        "state": "succeeded", "reason_code": "processing_attempt_limit_reached",
        "formation_incomplete": True,
        "formation_progress": {"planned_task_count": 2, "terminal_task_count": 2 - pending,
                               "pending_task_count": pending}})
    html = _page(_client(console, production_app, "uploader.854"), sid)
    label = re.search(r'<p class="diagnosis-label">(.*?)</p>', html, flags=re.S).group(1)
    assert "Niet publiceerbaar" in label
    assert _blocked_step(html) == step
    assert ERROR_COPY["source_formation_incomplete"] in html
    assert 'action="/tree/processing-recovery"' in html


@pytest.mark.parametrize(("diagnostic", "active_step", "earlier_steps"), [
    ({"phase": "task_plan_pinned"}, 2, set()),
    ({"phase": "model_request"}, 2, set()),
    ({"phase": "worker_handover"}, 2, set()),
    ({"phase": "validation_started", "checkpoints": [{"phase": "proposal_received"}]}, 4, {2}),
    ({"phase": "reserved", "checkpoints": [{"phase": "task_plan_pinned"}]}, 1, set()),
    ({"phase": "unknown", "checkpoints": [{"phase": "reserved"}, {"phase": "model_request"}]}, 2, {1}),
    ({"checkpoints": [{"phase": "model_request"}, {"phase": "reserved"}]}, 1, set()),
    ({"phase": "unknown", "checkpoints": [{"phase": "unknown"}]}, 1, set()),
])
def test_running_timeline_follows_current_phase_or_latest_known_checkpoint(
        system, monkeypatch, diagnostic, active_step, earlier_steps, *, production_app):
    console, sid = system
    _fixed_status(console, monkeypatch, {"state": "running", "reason_code": "processing_attempt_in_progress"})
    _with_last_attempt(console, monkeypatch, diagnostic)
    html = _page(_client(console, production_app, "reviewer.854"), sid)
    steps = re.search(r'<ol class="diagnosis-steps">(.*?)</ol>', html, flags=re.S).group(1)
    rows = re.findall(r'<li[^>]*>(.*?)</li>', steps, flags=re.S)
    assert len(rows) == 5
    for number, row in enumerate(rows, start=1):
        status = re.search(r'<p class="diagnosis-status">(.*?)</p>', row).group(1)
        expected = (("Eerder bereikt" if number in earlier_steps else "Geen fase vastgelegd")
                    if number < active_step else "Bezig" if number == active_step else f"Wacht op stap {active_step}")
        assert status == expected
    assert 'class="blocked"' not in steps
    assert "Verwerking loopt" in html


@pytest.mark.parametrize(("diagnostic", "step"), [
    ({"phase": "task_plan_pinned", "checkpoints": [{"phase": "reserved"}, {"phase": "task_plan_pinned"}]}, 2),
    ({"phase": "joint_validation_rejected", "checkpoints": [{"phase": "reserved"}, {"phase": "joint_validation_rejected"}]}, 4),
    ({"phase": "validation_rejected", "checkpoints": [{"phase": "proposal_received"}]}, 4),
    ({"phase": "unmapped_854", "checkpoints": [{"phase": "reserved"}, {"phase": "source_views_pinned"}, {"phase": "unmapped_854"}]}, 2),
    ({"phase": "unmapped_854", "checkpoints": [{"phase": "unmapped_854"}]}, 1),
])
def test_other_failed_codes_stop_at_recorded_step_or_first_after_last_success(system, monkeypatch, diagnostic, step, *, production_app):
    console, sid = system
    _fixed_status(console, monkeypatch, {"state": "failed", "error_code": "source_processing_strategy_unconfigured",
                                         "reason_code": "source_processing_strategy_unconfigured", "retry_allowed": False})
    _with_last_attempt(console, monkeypatch, diagnostic)
    assert _blocked_step(_page(_client(console, production_app, "uploader.854"), sid)) == step


@pytest.mark.parametrize(("status", "icon"), [
    ({"state": "failed", "reason_code": "source_processing_strategy_unconfigured",
      "error_code": "source_processing_strategy_unconfigured"}, "blocked"),
    ({"state": "running", "reason_code": "processing_attempt_in_progress"}, "running"),
    ({"state": "succeeded"}, "info"),
])
def test_purple_exclamation_only_for_blocked_neutral_water_icons_otherwise(system, monkeypatch, status, icon, *, production_app):
    console, sid = system
    if icon == "info":
        _clear_admission_blocks(console, sid)
    _fixed_status(console, monkeypatch, status)
    html = _page(_client(console, production_app, "uploader.854"), sid)
    label = re.search(r'<p class="diagnosis-label">(.*?)</p>', html, flags=re.S).group(1)
    assert f'class="diagnosis-icon is-{icon}"' in label
    assert ("!" in label) is (icon == "blocked")
    assert ("<svg" in label) is (icon == "running")
    assert not any(mark in label for mark in ("✓", "✔", "check"))
    if icon == "info":
        assert ">i</span>" in label
    style = html[html.index(".diagnosis-icon"):html.index("</style>", html.index(".diagnosis-icon"))]
    assert re.search(r"\.diagnosis-icon\.is-running \{[^}]*#45AAC7", style)
    assert re.search(r"\.diagnosis-icon\.is-info \{[^}]*#45AAC7", style)
    assert re.search(r"\.diagnosis-icon\.is-blocked \{[^}]*#5D3297", style)
    assert "animation" not in style
