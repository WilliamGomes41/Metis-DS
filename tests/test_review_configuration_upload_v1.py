"""H2 slice 2b-2: B10-reviewkeuze bij uploaden (geen poortwijziging).

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from secrets import token_urlsafe

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.review_configuration_v1 import CONTRACT, effective_configuration

HTML = b"<html><body><h1>Bron</h1><p>Bespreek als verpleegkundige de sociale contacten.</p></body></html>"


@pytest.fixture
def system(tmp_path):
    console = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources" / "private", runtime=tmp_path / "runtime")
    password = token_urlsafe(24)
    uploader = console.create_account("uploader", password, roles=("researcher", "reviewer"), display_name="Onderzoeker")
    first = console.create_account("eerste", token_urlsafe(24), roles=("reviewer",), display_name="Eerste")
    second = console.create_account("tweede", token_urlsafe(24), roles=("reviewer",), display_name="Tweede")
    reader = console.create_account("lezer", token_urlsafe(24), roles=("reviewer",), display_name="Lezer")
    from tests.semantic_fixture_support import bind_fixture_selections
    bind_fixture_selections(console)
    ids = {"uploader": uploader["account_id"], "first": first["account_id"],
           "second": second["account_id"], "reader": reader["account_id"]}
    return console, password, ids


def _kernel(console, ids, title, **extra):
    command = dict(actor_id=ids["uploader"], ingest_kind="new", title=title, version="1.0", date="2026-10-15",
                   live_url="", class_="richtlijn", family="Configuratie", filename="bron.html", data=HTML,
                   content_type="text/html")
    command.setdefault("named_reviewers", [ids["first"]])
    command.update(extra)
    return console.receive_source(**command)["snapshot_id"]


def _client(console, password):
    client = TestClient(create_console_app(console), base_url="https://testserver")
    assert client.post("/login", data={"username": "uploader", "password": password}).status_code == 200
    return client


def _form(ids, **extra):
    form = dict(ingest_kind="new", title="Upload", version="1.0", date="2026-10-15", class_="richtlijn",
                family="Configuratie", named_reviewers=[ids["first"]])
    form.update(extra)
    return form


def test_kernel_ingest_without_choice_stores_legacy_default(system):
    console, _, ids = system
    sid = _kernel(console, ids, "Kernel")
    stored = console._envelope(sid)["review_configuration"]
    assert stored == {"contract": CONTRACT, "option": "one_other", "four_eyes_required": False,
                      "reviewers": [ids["first"]], "readers": [], "revision": 0, "locked_at": None,
                      "source": "legacy_default"}
    assert effective_configuration(console._envelope(sid))["needs_choice"] is False


def test_kernel_ingest_with_choice_stores_chosen_and_readers_never_count(system):
    console, _, ids = system
    sid = _kernel(console, ids, "Keuze", named_reviewers=[ids["first"], ids["second"]],
                  review_choice={"option": "two_others", "four_eyes_required": True,
                                 "reviewers": [ids["first"], ids["second"]], "readers": [ids["reader"]]})
    envelope = console._envelope(sid)
    assert envelope["review_configuration"]["source"] == "chosen"
    assert envelope["review_configuration"]["option"] == "two_others"
    assert envelope["review_configuration"]["four_eyes_required"] is True
    assert envelope["review_configuration"]["readers"] == [ids["reader"]]
    assert ids["reader"] not in envelope["named_reviewers"]


def test_kernel_choice_named_reviewers_from_choice_when_old_field_empty(system):
    console, _, ids = system
    sid = _kernel(console, ids, "Alleen keuze", named_reviewers=[],
                  review_choice={"option": "one_other", "four_eyes_required": False,
                                 "reviewers": [ids["second"]], "readers": []})
    assert console._envelope(sid)["named_reviewers"] == [ids["second"]]


@pytest.mark.parametrize("named", [["first"], ["first", "second"]])
def test_kernel_legacy_named_reviewers_disagreeing_with_choice_is_refused(system, named):
    console, _, ids = system
    with pytest.raises(ConsoleError) as error:
        _kernel(console, ids, "Conflict", named_reviewers=[ids[n] for n in named],
                review_choice={"option": "one_other", "four_eyes_required": False,
                               "reviewers": [ids["second"]], "readers": []})
    assert error.value.code == "review_configuration_policy_conflict"
    assert console.list_envelopes() == []


def test_kernel_review_policy_disagreeing_with_choice_is_refused(system):
    console, _, ids = system
    from src.review_policy_v1 import CONTRACT as POLICY
    policy = {"contract": POLICY, "revision": 1, "primary": ids["first"], "assignments": []}
    with pytest.raises(ConsoleError) as error:
        _kernel(console, ids, "Policy", named_reviewers=[], review_policy=policy,
                review_choice={"option": "one_other", "four_eyes_required": False,
                               "reviewers": [ids["second"]], "readers": []})
    assert error.value.code == "review_configuration_policy_conflict"
    assert console.list_envelopes() == []


def test_kernel_review_policy_agreeing_with_choice_stores_chosen(system):
    console, _, ids = system
    from src.review_policy_v1 import CONTRACT as POLICY
    policy = {"contract": POLICY, "revision": 1, "primary": ids["first"], "assignments": []}
    sid = _kernel(console, ids, "Policy eens", named_reviewers=[], review_policy=policy,
                  review_choice={"option": "one_other", "four_eyes_required": False,
                                 "reviewers": [ids["first"]], "readers": []})
    assert console._envelope(sid)["review_configuration"]["source"] == "chosen"


def test_kernel_review_policy_without_choice_stores_no_configuration(system):
    console, _, ids = system
    from src.review_policy_v1 import CONTRACT as POLICY
    policy = {"contract": POLICY, "revision": 1, "primary": ids["first"], "assignments": []}
    sid = _kernel(console, ids, "Policy zonder keuze", named_reviewers=[], review_policy=policy)
    assert "review_configuration" not in console._envelope(sid)


@pytest.mark.parametrize(("choice", "code"), [
    ({"option": "uploader_sole", "four_eyes_required": True, "reviewers": [], "readers": []},
     "review_configuration_four_eyes_uploader_sole_refused"),
    ({"option": "one_other", "four_eyes_required": False, "reviewers": ["ai"], "readers": []},
     "forbidden_reviewer_identity"),
    ({"option": "one_other", "four_eyes_required": False, "reviewers": [], "readers": []},
     "review_configuration_reviewers_missing"),
    ({"option": "elk", "four_eyes_required": False, "reviewers": [], "readers": []},
     "invalid_review_configuration"),
    ({"option": "one_other", "four_eyes_required": False, "reviewers": ["FIRST"], "readers": ["onbekend"]},
     "unknown_reader"),
])
def test_kernel_invalid_choice_is_refused_before_any_write(system, choice, code):
    console, _, ids = system
    choice = {**choice, "reviewers": [ids["first"] if r == "FIRST" else r for r in choice["reviewers"]]}
    with pytest.raises(ConsoleError) as error:
        _kernel(console, ids, "Ongeldig", named_reviewers=[], review_choice=choice)
    assert error.value.code == code
    assert console.list_envelopes() == []


def test_http_form_requires_choice_next_to_old_fields(system):
    console, password, _ = system
    page = _client(console, password).get("/ingest").text
    assert 'name="review_mode"' in page and 'name="primary_reviewer"' in page
    for option in ("uploader_sole", "two_others", "one_other"):
        assert f'name="review_option" value="{option}" required' in page
    assert 'name="four_eyes"' in page and 'name="review_reviewers"' in page and 'name="review_readers"' in page


def test_http_upload_without_choice_is_refused(system):
    console, password, ids = system
    response = _client(console, password).post("/ingest", data=_form(ids),
                                               files={"file": ("bron.html", HTML, "text/html")})
    assert response.status_code == 400
    assert "review_configuration_required" in response.text
    assert console.list_envelopes() == []


def test_http_upload_with_choice_stores_chosen(system):
    console, password, ids = system
    response = _client(console, password).post("/ingest", data=_form(
        ids, review_option="one_other", four_eyes="yes", review_reviewers=[ids["first"]],
        review_readers=[ids["reader"]]), files={"file": ("bron.html", HTML, "text/html")}, follow_redirects=False)
    assert response.status_code == 303, response.text
    sid = response.headers["location"].split("document=")[1].split("&")[0]
    stored = console._envelope(sid)["review_configuration"]
    assert (stored["option"], stored["four_eyes_required"], stored["reviewers"], stored["readers"], stored["source"]) \
        == ("one_other", True, [ids["first"]], [ids["reader"]], "chosen")
    assert console._envelope(sid)["named_reviewers"] == [ids["first"]]


def test_http_non_legacy_mode_disagreeing_with_choice_is_refused(system):
    console, password, ids = system
    response = _client(console, password).post("/ingest", data=_form(
        ids, named_reviewers=[], review_mode="single", primary_reviewer=ids["first"],
        review_option="one_other", review_reviewers=[ids["second"]]),
        files={"file": ("bron.html", HTML, "text/html")})
    assert response.status_code == 400
    assert "review_configuration_policy_conflict" in response.text
    assert console.list_envelopes() == []


def test_review_overview_shows_configuration_and_source(system):
    console, _, ids = system
    _kernel(console, ids, "Zichtbaar")
    from src.review_participation_ui_v1 import roster
    html = roster(console, console.list_envelopes()[0])
    assert "Reviewkeuze: één andere reviewer" in html
    assert "bron: standaard voor bestaande regels (legacy_default)" in html


def test_kernel_review_policy_without_choice_marks_policy_mapping_visibly(system):
    console, _, ids = system
    from src.review_policy_v1 import CONTRACT as POLICY
    from src.review_participation_ui_v1 import roster
    policy = {"contract": POLICY, "revision": 1, "primary": ids["first"], "assignments": []}
    receipt = console.receive_source(actor_id=ids["uploader"], ingest_kind="new", title="Markering", version="1.0",
                                     date="2026-10-15", live_url="", class_="richtlijn", family="Configuratie",
                                     filename="bron.html", data=HTML, content_type="text/html",
                                     named_reviewers=[], review_policy=policy)
    assert receipt["configuration_source"] == "legacy_policy_mapping"
    envelope = console._envelope(receipt["snapshot_id"])
    assert envelope["configuration_source"] == "legacy_policy_mapping"
    assert "review_configuration" not in envelope
    assert effective_configuration(envelope)["source"] == "migrated_policy"
    assert "configuratiebron: legacy_policy_mapping" in roster(console, envelope)


def test_chosen_and_legacy_default_carry_no_policy_mapping_marker(system):
    console, _, ids = system
    sid = _kernel(console, ids, "Geen markering")
    assert "configuration_source" not in console._envelope(sid)
