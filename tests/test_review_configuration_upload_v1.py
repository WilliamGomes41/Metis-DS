"""H2 slice 2b-2: B10-reviewkeuze bij uploaden (geen poortwijziging).

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

from secrets import token_urlsafe

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.review_configuration_v1 import CONTRACT, effective_configuration

HTML = b"<html><body><h1>Bron</h1><p>Bespreek als verpleegkundige de sociale contacten.</p></body></html>"


@pytest.fixture
def system(tmp_path, *, production_console):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path, source_store=tmp_path / "sources" / "private", runtime=tmp_path / "runtime")
    password = token_urlsafe(24)
    uploader = console.create_account("uploader", password, roles=("researcher", "reviewer"), display_name="Onderzoeker")
    first = console.create_account("eerste", token_urlsafe(24), roles=("reviewer",), display_name="Eerste")
    second = console.create_account("tweede", token_urlsafe(24), roles=("reviewer",), display_name="Tweede")
    reader = console.create_account("lezer", token_urlsafe(24), roles=("reviewer",), display_name="Lezer")
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


def _client(console, password, *, production_app):
    client = TestClient(production_app(console), base_url="https://testserver")
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


def test_http_form_requires_choice_next_to_old_fields(system, *, production_app):
    console, password, _ = system
    page = _client(console, password, production_app=production_app).get("/ingest").text
    assert 'name="review_mode"' in page and 'name="primary_reviewer"' in page
    for option in ("uploader_sole", "two_others", "one_other"):
        assert f'name="review_option" value="{option}" required' in page
    assert 'name="four_eyes"' in page and 'name="review_reviewers"' in page and 'name="review_readers"' in page


def test_http_upload_without_choice_is_refused(system, *, production_app):
    console, password, ids = system
    response = _client(console, password, production_app=production_app).post("/ingest", data=_form(ids),
                                               files={"file": ("bron.html", HTML, "text/html")})
    assert response.status_code == 400
    assert "review_configuration_required" in response.text
    assert console.list_envelopes() == []


def test_http_upload_with_choice_stores_chosen(system, *, production_app):
    console, password, ids = system
    response = _client(console, password, production_app=production_app).post("/ingest", data=_form(
        ids, review_option="one_other", four_eyes="yes", review_reviewers=[ids["first"]],
        review_readers=[ids["reader"]]), files={"file": ("bron.html", HTML, "text/html")}, follow_redirects=False)
    assert response.status_code == 303, response.text
    sid = response.headers["location"].split("document=")[1].split("&")[0]
    stored = console._envelope(sid)["review_configuration"]
    assert (stored["option"], stored["four_eyes_required"], stored["reviewers"], stored["readers"], stored["source"]) \
        == ("one_other", True, [ids["first"]], [ids["reader"]], "chosen")
    assert console._envelope(sid)["named_reviewers"] == [ids["first"]]


def test_http_non_legacy_mode_disagreeing_with_choice_is_refused(system, *, production_app):
    console, password, ids = system
    response = _client(console, password, production_app=production_app).post("/ingest", data=_form(
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


def test_reader_who_is_optional_policy_participant_is_refused(system):
    console, _, ids = system
    from src.review_policy_v1 import CONTRACT as POLICY
    policy = {"contract": POLICY, "revision": 1, "primary": ids["first"],
              "assignments": [{"reviewer_id": ids["reader"], "participation": "optional"}]}
    with pytest.raises(ConsoleError) as error:
        _kernel(console, ids, "Lezer met toegang", named_reviewers=[], review_policy=policy,
                review_choice={"option": "one_other", "four_eyes_required": False,
                               "reviewers": [ids["first"]], "readers": [ids["reader"]]})
    assert error.value.code == "review_configuration_reader_is_reviewer"
    assert console.list_envelopes() == []


def test_same_command_with_changed_choice_is_an_idempotency_conflict(system):
    console, _, ids = system
    choice = {"option": "one_other", "four_eyes_required": False, "reviewers": [ids["first"]], "readers": []}
    first = _kernel(console, ids, "Idempotent", review_choice=choice, command_id="cmd-keuze")
    assert _kernel(console, ids, "Idempotent", review_choice=dict(choice), command_id="cmd-keuze") == first
    for changed in ({**choice, "four_eyes_required": True}, {**choice, "readers": [ids["reader"]]}):
        with pytest.raises(ConsoleError) as error:
            _kernel(console, ids, "Idempotent", review_choice=changed, command_id="cmd-keuze")
        assert error.value.code == "ingest_command_conflict"
    assert console._envelope(first)["review_configuration"]["four_eyes_required"] is False
    assert len(console.list_envelopes()) == 1


def test_legacy_mode_uploader_sole_without_reviewers_is_stored(system, *, production_app):
    console, password, ids = system
    response = _client(console, password, production_app=production_app).post("/ingest", data=_form(ids, named_reviewers=[], review_option="uploader_sole"),
                                               files={"file": ("bron.html", HTML, "text/html")}, follow_redirects=False)
    assert response.status_code == 303, response.text
    sid = response.headers["location"].split("document=")[1].split("&")[0]
    stored = console._envelope(sid)
    assert (stored["review_configuration"]["option"], stored["review_configuration"]["source"]) == ("uploader_sole", "chosen")
    assert stored["named_reviewers"] == [ids["uploader"]]


def test_uploader_sole_with_other_named_reviewer_is_a_conflict(system):
    console, _, ids = system
    with pytest.raises(ConsoleError) as error:
        _kernel(console, ids, "Alleen ik", named_reviewers=[ids["first"]],
                review_choice={"option": "uploader_sole", "four_eyes_required": False, "reviewers": [], "readers": []})
    assert error.value.code == "review_configuration_policy_conflict"
    assert console.list_envelopes() == []


@pytest.mark.parametrize(("option", "count"), [("one_other", 2), ("two_others", 3)])
def test_chosen_option_requires_exact_reviewer_count(system, option, count):
    console, _, ids = system
    extra = console.create_account("derde", token_urlsafe(24), roles=("reviewer",), display_name="Derde")["account_id"]
    reviewers = [ids["first"], ids["second"], extra][:count]
    with pytest.raises(ConsoleError) as error:
        _kernel(console, ids, "Aantal", named_reviewers=[],
                review_choice={"option": option, "four_eyes_required": False, "reviewers": reviewers, "readers": []})
    assert error.value.code == "review_configuration_reviewer_count_mismatch"
    assert console.list_envelopes() == []


def test_legacy_document_with_two_reviewers_stays_valid(system):
    console, _, ids = system
    sid = _kernel(console, ids, "Legacy twee", named_reviewers=[ids["first"], ids["second"]])
    envelope = console._envelope(sid)
    assert envelope["review_configuration"]["source"] == "legacy_default"
    assert envelope["review_configuration"]["reviewers"] == [ids["first"], ids["second"]]
    assert effective_configuration(envelope)["needs_choice"] is False


@pytest.mark.parametrize(("uploader_required", "four_eyes"), [(True, False), (False, True)])
def test_policy_four_eyes_must_match_choice(system, uploader_required, four_eyes):
    console, _, ids = system
    from src.review_policy_v1 import CONTRACT as POLICY
    if uploader_required:
        policy = {"contract": POLICY, "revision": 1, "primary": ids["uploader"],
                  "assignments": [{"reviewer_id": ids["first"], "participation": "required"}]}
    else:
        policy = {"contract": POLICY, "revision": 1, "primary": ids["first"], "assignments": []}
    with pytest.raises(ConsoleError) as error:
        _kernel(console, ids, "Vier ogen", named_reviewers=[], review_policy=policy,
                review_choice={"option": "one_other", "four_eyes_required": four_eyes,
                               "reviewers": [ids["first"]], "readers": []})
    assert error.value.code == "review_configuration_policy_conflict"
    assert console.list_envelopes() == []


def test_policy_uploader_required_plus_one_other_accepts_four_eyes(system):
    console, _, ids = system
    from src.review_policy_v1 import CONTRACT as POLICY
    policy = {"contract": POLICY, "revision": 1, "primary": ids["uploader"],
              "assignments": [{"reviewer_id": ids["first"], "participation": "required"}]}
    sid = _kernel(console, ids, "Vier ogen eens", named_reviewers=[], review_policy=policy,
                  review_choice={"option": "one_other", "four_eyes_required": True,
                                 "reviewers": [ids["first"]], "readers": []})
    assert console._envelope(sid)["review_configuration"]["four_eyes_required"] is True


def test_legacy_default_runs_validation_before_any_write(system, monkeypatch):
    console, _, ids = system
    # Diepteverdediging: ook als de oude resolutie een verboden identiteit doorlaat,
    # MAG NIET een legacy_default met die identiteit worden opgeslagen.
    monkeypatch.setattr(console, "_resolve_named_reviewers", lambda named, uploader: ["ai"])
    with pytest.raises(ConsoleError) as error:
        _kernel(console, ids, "Verboden")
    assert error.value.code == "forbidden_reviewer_identity"
    assert console.list_envelopes() == []


def _uploader_plus_two(ids):
    from src.review_policy_v1 import CONTRACT as POLICY
    return {"contract": POLICY, "revision": 1, "primary": ids["uploader"],
            "assignments": [{"reviewer_id": ids["first"], "participation": "required"},
                            {"reviewer_id": ids["second"], "participation": "required"}]}


def test_h2_1_uploader_plus_two_without_choice_needs_choice(system):
    console, _, ids = system
    sid = _kernel(console, ids, "H2-1 zonder keuze", named_reviewers=[], review_policy=_uploader_plus_two(ids))
    envelope = console._envelope(sid)
    assert envelope["configuration_source"] == "legacy_policy_mapping"
    assert effective_configuration(envelope)["needs_choice"] is True


@pytest.mark.parametrize("four_eyes", [False, True])
def test_h2_1_uploader_plus_two_does_not_force_four_eyes_on_choice(system, four_eyes):
    console, _, ids = system
    sid = _kernel(console, ids, "H2-1 keuze", named_reviewers=[], review_policy=_uploader_plus_two(ids),
                  review_choice={"option": "two_others", "four_eyes_required": four_eyes,
                                 "reviewers": [ids["first"], ids["second"]], "readers": []})
    assert console._envelope(sid)["review_configuration"]["four_eyes_required"] is four_eyes


def _uploader_sole(console, ids):
    return _kernel(console, ids, "Alleen uploader", named_reviewers=[],
                   review_choice={"option": "uploader_sole", "four_eyes_required": False, "reviewers": [], "readers": []})


def test_uploader_sole_overview_shows_uploader_as_reviewer(system):
    # 2b3-2: met uploader_sole en lege named_reviewers MOET het overzicht de uploader tonen.
    console, _, ids = system
    from src.review_participation_ui_v1 import participation_choices, roster
    envelope = console._envelope(_uploader_sole(console, ids))
    html = roster(console, envelope)
    assert "Toegewezen: Onderzoeker" in html
    assert "wacht op" not in html.lower()
    participation_choices(console, envelope)


def test_uploader_sole_workboard_lists_document_for_uploader(system, *, production_app):
    console, password, ids = system
    _uploader_sole(console, ids)
    response = _client(console, password, production_app=production_app).get("/review?work=all")
    assert response.status_code == 200
    assert "Alleen uploader" in response.text
    assert "wacht op reviewer" not in response.text.lower()
    assert "wacht op andere reviewer" not in response.text.lower()


def test_stale_local_account_cannot_legitimize_an_unknown_reader(system):
    console, _, ids = system
    console._accounts['stale-reader'] = {'account_id': 'stale-reader', 'roles': ['reviewer']}
    with pytest.raises(ConsoleError, match='^unknown_reader$'):
        _kernel(console, ids, 'Stale reader', review_choice={
            'option': 'one_other', 'four_eyes_required': False,
            'reviewers': [ids['first']], 'readers': ['stale-reader'],
        })
    assert console.list_envelopes() == []
