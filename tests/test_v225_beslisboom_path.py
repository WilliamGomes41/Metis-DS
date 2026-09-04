"""Protocol v2.25 code wave: beslisboom path / node / outcome on real functions.

Klasse includes beslisboom and selects the review path. Boom types are
path | node | outcome only. Other Klassen keep the richtlijn stacks.
publish() stays G2-BLOCKED. Product API boom serving is not activated.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.answerability_gate_v1 import evaluate_answerability
from src.beslisboom_path_v1 import (
    CLOSED_BOOM_TYPES,
    CLOSED_KLASSEN,
    RICHTLIJN_PATH_TYPES,
    boom_freeze_errors,
    boom_serving_activated,
    class_outranks,
    extract_boom_fragments,
    is_closed_boom_type,
    is_empty_or_placeholder_outcome,
    is_live_rest_sole_source,
    is_story_html_alone,
    map_geen_actie,
    outcome_review_errors,
    review_path_for_klasse,
    scorelist_item_model,
    split_or_reject_multi_bullet_outcome,
)
from src.integrity_kernel import canonical_object_payload, compute_canonical_object_hash
from src.four_eyes_v1 import requires_four_eyes
from src.object_taxonomy_v1 import (
    CLASS_ORDER,
    CLOSED_OBJECT_TYPES,
    is_advice_weight,
    is_closed_confirmed_type,
    locator_of,
    published_object_type,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import (
    ALLOWED_CLASSES,
    ConsoleError,
    OperationsConsole,
    review_lane,
    review_stacks,
    slow_review_duty,
)


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
STORY_FIXTURE = ROOT / "data/fixtures/story_html_boom_player_fixture.html"


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _accounts(console: OperationsConsole) -> dict[str, dict]:
    researcher = console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher", "reviewer"),
        display_name="Anne Onderzoeker",
    )
    reviewer = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    publisher = console.create_account(
        username="publisher.carla",
        password="carla-secret",
        roles=("publisher",),
        display_name="Carla Publisher",
    )
    return {"researcher": researcher, "reviewer": reviewer, "publisher": publisher}


def _boom_freeze_bytes() -> bytes:
    payload = {
        "kind": "beslisboom-freeze",
        "paths": [{"id": "path-screening", "text": "Screening op valrisico"}],
        "nodes": [
            {
                "id": "node-vraag",
                "text": "Is er een verhoogd valrisico?",
                "scorelist": False,
            },
            {
                "id": "node-score",
                "text": "Score 2: evenwicht",
                "scorelist": True,
            },
        ],
        "outcomes": [
            {
                "id": "out-verwijs",
                "text": "Verwijs naar de valpoli.",
                "applies_if": ["node-vraag"],
            }
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _ingest_boom(console: OperationsConsole, accounts: dict[str, dict], **overrides) -> dict:
    kwargs = {
        "actor_id": accounts["researcher"]["account_id"],
        "filename": "valrisico-boom.json",
        "data": _boom_freeze_bytes(),
        "content_type": "application/json",
        "ingest_kind": "new",
        "title": "Valrisico boom",
        "version": "1.0",
        "date": "2025-04-01",
        "live_url": "",
        "class_": "beslisboom",
        "family": "valrisico",
        "named_reviewers": [accounts["reviewer"]["account_id"]],
    }
    kwargs.update(overrides)
    return console.ingest(**kwargs)


def _ingest_richtlijn(console: OperationsConsole, accounts: dict[str, dict], **overrides) -> dict:
    kwargs = {
        "actor_id": accounts["researcher"]["account_id"],
        "filename": "continentie.html",
        "data": HTML_FIXTURE.read_bytes(),
        "content_type": "text/html",
        "ingest_kind": "new",
        "title": "Continentie fixture",
        "version": "1.0",
        "date": "2025-04-01",
        "live_url": "https://example.test/continentie",
        "class_": "richtlijn",
        "family": "valrisico",
        "named_reviewers": [accounts["reviewer"]["account_id"]],
    }
    kwargs.update(overrides)
    return console.ingest(**kwargs)


def _confirm_applies_if(
    console: OperationsConsole,
    accounts: dict[str, dict],
    snapshot_id: str,
    obj: dict,
) -> None:
    proposed = [
        row
        for row in (obj.get("relations") or [])
        if row.get("relation_type") == "applies_if" and row.get("target_object_id")
    ]
    assert proposed, "boom outcome must carry a proposed applies_if for the reviewer"
    console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=snapshot_id,
        object_id=obj["object_id"],
        relations=proposed,
    )


def test_klasse_closed_set_includes_beslisboom_and_selects_review_path() -> None:
    assert ALLOWED_CLASSES == CLOSED_KLASSEN
    assert ALLOWED_CLASSES == (
        "richtlijn",
        "handreiking",
        "artikel",
        "transcript",
        "podcast",
        "beslisboom",
    )
    assert review_path_for_klasse("beslisboom") == "boom"
    for klasse in ("richtlijn", "handreiking", "artikel", "transcript", "podcast"):
        assert review_path_for_klasse(klasse) == "richtlijn"
    with pytest.raises(ValueError, match="invalid_class"):
        review_path_for_klasse("scorelist")
    with pytest.raises(ValueError, match="invalid_class"):
        review_path_for_klasse("path")


def test_ingest_accepts_beslisboom_and_rejects_invented_klasse(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(console, accounts)
    assert receipt["class"] == "beslisboom"
    assert receipt["sha256"] == hashlib.sha256(_boom_freeze_bytes()).hexdigest()
    with pytest.raises(ConsoleError, match="invalid_class"):
        _ingest_boom(console, accounts, class_="scorelist", title="Bad")


def test_inleveren_has_no_second_path_chooser(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    client = TestClient(create_console_app(console))
    login = client.post(
        "/login",
        data={"username": "researcher.anne", "password": "anne-secret"},
        follow_redirects=True,
    )
    assert login.status_code == 200
    page = client.get("/ingest")
    html = page.text
    assert 'name="class_"' in html
    assert "beslisboom" in html
    assert 'name="path"' not in html
    assert 'name="review_path"' not in html
    assert 'id="path"' not in html
    assert html.count("<select") >= 1
    assert html.lower().count("tweede kiezer") == 0


def test_beslisboom_uses_path_node_outcome_only_scorelist_is_node_flag() -> None:
    assert CLOSED_BOOM_TYPES == ("path", "node", "outcome")
    assert "scorelist" not in CLOSED_BOOM_TYPES
    assert is_closed_boom_type("path")
    assert is_closed_boom_type("node")
    assert is_closed_boom_type("outcome")
    assert not is_closed_boom_type("scorelist")
    assert not is_closed_boom_type("recommendation")
    model = scorelist_item_model()
    assert model["object_type"] == "node"
    assert model["scorelist"] is True
    assert "scorelist" not in CLOSED_OBJECT_TYPES
    assert set(CLOSED_BOOM_TYPES).isdisjoint(set(RICHTLIJN_PATH_TYPES))


def test_other_klassen_do_not_get_boom_types(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    content = [row for row in objects if row.get("object_type") != "document"]
    assert content
    for row in content:
        assert row.get("object_type") not in CLOSED_BOOM_TYPES
        assert row.get("proposed_object_type") not in CLOSED_BOOM_TYPES
        assert row.get("confirmed_object_type") not in CLOSED_BOOM_TYPES
    target = next(
        row
        for row in content
        if (row.get("content") or {}).get("clean_text")
    )
    with pytest.raises(ConsoleError, match="unknown_object_type"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=target["object_id"],
            decision="approve",
            confirmed_object_type="outcome",
        )
    with pytest.raises(ConsoleError, match="unknown_object_type"):
        console.confirm_object_type(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=target["object_id"],
            confirmed_object_type="path",
        )
    koppen, inhoud = review_stacks(objects)
    assert all(
        (row.get("object_type") or row.get("proposed_object_type")) != "path"
        for row in koppen
    )


def test_beslisboom_review_uses_path_node_outcome_stacks(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    types = {
        row.get("proposed_object_type") or row.get("object_type")
        for row in objects
        if row.get("object_type") != "document"
    }
    assert types <= {"path", "node", "outcome", "unclassified"}
    assert "path" in types
    assert "node" in types
    assert "outcome" in types
    assert "scorelist" not in types
    score_node = next(
        row
        for row in objects
        if "evenwicht" in ((row.get("content") or {}).get("clean_text") or "")
    )
    assert (score_node.get("proposed_object_type") or score_node.get("object_type")) == "node"
    assert score_node.get("scorelist") is True or (score_node.get("metadata") or {}).get("scorelist")
    paths, duty = review_stacks(objects, review_path="boom")
    assert paths
    assert all(review_lane(row, review_path="boom") == "fast" for row in paths)
    assert slow_review_duty(objects, review_path="boom")
    outcome = next(
        row
        for row in objects
        if (row.get("proposed_object_type") or row.get("object_type")) == "outcome"
    )
    assert outcome in slow_review_duty(objects, review_path="boom")


def test_outcome_must_bind_applies_if_and_rejects_fused_empty_multibullet() -> None:
    node = {
        "object_id": "node-1",
        "object_type": "node",
        "confirmed_object_type": "node",
    }
    path = {
        "object_id": "path-1",
        "object_type": "path",
        "confirmed_object_type": "path",
    }
    good = {
        "object_id": "out-1",
        "object_type": "outcome",
        "content": {"clean_text": "Verwijs naar de valpoli."},
        "confirmed_relations": [
            {"relation_type": "applies_if", "target_object_id": "node-1", "confirmed": True}
        ],
    }
    assert outcome_review_errors(good, peers=[node, path]) == []

    fused_only = {
        "object_id": "out-2",
        "object_type": "outcome",
        "content": {
            "clean_text": "Indien er valrisico is, verwijs naar de valpoli."
        },
        "confirmed_relations": [],
        "relations": [],
    }
    errors = outcome_review_errors(fused_only, peers=[node])
    assert "condition_fused_into_outcome" in errors

    empty = {
        "object_id": "out-3",
        "object_type": "outcome",
        "content": {"clean_text": ""},
        "confirmed_relations": [
            {"relation_type": "applies_if", "target_object_id": "node-1", "confirmed": True}
        ],
    }
    assert "empty_or_placeholder_outcome" in outcome_review_errors(empty, peers=[node])
    assert is_empty_or_placeholder_outcome("Uitkomst1_2_titel")
    assert is_empty_or_placeholder_outcome("   ")
    placeholder = {
        **empty,
        "content": {"clean_text": "Uitkomst4_1_titel"},
    }
    assert "empty_or_placeholder_outcome" in outcome_review_errors(placeholder, peers=[node])

    multi = "• Verwijs naar de valpoli.\n• Bespreek mantelzorg.\n• Start vitamine D."
    decision = split_or_reject_multi_bullet_outcome(multi)
    assert decision["action"] in {"split", "reject"}
    if decision["action"] == "split":
        assert len(decision["parts"]) >= 2
        assert all("•" not in part or part.count("•") <= 1 for part in decision["parts"])
    multi_obj = {
        "object_id": "out-4",
        "object_type": "outcome",
        "content": {"clean_text": multi},
        "confirmed_relations": [
            {"relation_type": "applies_if", "target_object_id": "node-1", "confirmed": True}
        ],
    }
    multi_errors = outcome_review_errors(multi_obj, peers=[node])
    assert "multi_bullet_outcome" in multi_errors


def test_console_rejects_invalid_outcomes_on_review(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    outcome = next(
        row
        for row in objects
        if (row.get("proposed_object_type") or row.get("object_type")) == "outcome"
    )
    fused = dict(outcome)
    fused["content"] = {
        **(outcome.get("content") or {}),
        "clean_text": "Indien score hoog is, verwijs naar de valpoli.",
    }
    fused["confirmed_relations"] = []
    fused["relations"] = []
    console._save_objects(
        receipt["snapshot_id"],
        [fused if row["object_id"] == outcome["object_id"] else row for row in objects],
    )
    with pytest.raises(ConsoleError, match="condition_fused_into_outcome|outcome_review_failed"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=outcome["object_id"],
            decision="approve",
            confirmed_object_type="outcome",
        )


def test_doen_overweeg_niet_doen_geen_actie_and_four_eyes() -> None:
    actionable = {
        "object_id": "out-a",
        "confirmed_object_type": "outcome",
        "object_type": "outcome",
        "content": {"clean_text": "Verwijs naar de valpoli."},
    }
    from src.beslisboom_path_v1 import outcome_strength_applies, proposed_outcome_strength

    assert outcome_strength_applies(actionable)
    assert proposed_outcome_strength("Adviseer verwijzing naar de valpoli.") == "doen"
    assert proposed_outcome_strength("Overweeg verwijzing.") == "overweeg"
    assert proposed_outcome_strength("NIET DOEN: start geen medicatie.") == "niet_doen"
    mapped = map_geen_actie("geen actie nodig")
    assert mapped["strength"] == "niet_doen"
    assert mapped["no_action"] is True
    assert mapped["positive_advice"] is False
    high = {
        "object_id": "out-risk",
        "confirmed_object_type": "outcome",
        "object_type": "outcome",
        "risk": {"risk_level": "high", "risk_fields": ["dosage"]},
        "metadata": {"dosage": "vitamine D 800IE"},
        "content": {"clean_text": "Start vitamine D 800IE."},
    }
    assert requires_four_eyes(high, confirmed_type="outcome")
    ordinary = {
        "object_id": "out-ok",
        "confirmed_object_type": "outcome",
        "object_type": "outcome",
        "content": {"clean_text": "Bespreek eenzaamheid."},
    }
    assert not requires_four_eyes(ordinary, confirmed_type="outcome")


def test_console_stamps_actionable_outcome_and_maps_geen_actie(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    outcome = next(
        row
        for row in objects
        if (row.get("proposed_object_type") or row.get("object_type")) == "outcome"
    )
    _confirm_applies_if(console, accounts, receipt["snapshot_id"], outcome)
    updated = console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=outcome["object_id"],
        decision="approve",
        confirmed_object_type="outcome",
        recommendation_strength="doen",
    )
    row = next(item for item in updated if item["object_id"] == outcome["object_id"])
    assert row["confirmed_object_type"] == "outcome"
    assert row["confirmed_recommendation_strength"] == "doen"

    empty_freeze = {
        "kind": "beslisboom-freeze",
        "paths": [{"id": "p", "text": "Pad"}],
        "nodes": [{"id": "n", "text": "Is er eenzaamheid?", "scorelist": False}],
        "outcomes": [
            {
                "id": "o",
                "text": "geen actie nodig",
                "applies_if": ["n"],
            }
        ],
    }
    second = _ingest_boom(
        console,
        accounts,
        filename="eenzaamheid-boom.json",
        data=(json.dumps(empty_freeze, ensure_ascii=False) + "\n").encode("utf-8"),
        title="Eenzaamheid boom",
        family="eenzaamheid",
    )
    objects = console.snapshot_objects(second["snapshot_id"])
    geen = next(
        row
        for row in objects
        if "geen actie" in ((row.get("content") or {}).get("clean_text") or "").lower()
    )
    _confirm_applies_if(console, accounts, second["snapshot_id"], geen)
    updated = console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=second["snapshot_id"],
        object_id=geen["object_id"],
        decision="approve",
        confirmed_object_type="outcome",
    )
    row = next(item for item in updated if item["object_id"] == geen["object_id"])
    assert row.get("confirmed_recommendation_strength") == "niet_doen"
    assert row.get("no_action") is True or (row.get("metadata") or {}).get("no_action") is True


def test_boom_freeze_locator_sha256_rejects_live_rest_and_story_html(tmp_path: Path) -> None:
    freeze = _boom_freeze_bytes()
    digest = hashlib.sha256(freeze).hexdigest()
    assert boom_freeze_errors(
        data=freeze,
        filename="valrisico-boom.json",
        live_url="",
    ) == []
    assert not is_live_rest_sole_source(
        data=freeze,
        live_url="",
        filename="valrisico-boom.json",
    )
    assert is_live_rest_sole_source(
        data=b"",
        live_url="https://kennisplatform.venvn.nl/wp-json/beslisboom/v1/outcomes",
        filename="",
    )
    assert "live_rest_sole_source" in boom_freeze_errors(
        data=b'{"kind":"beslisboom-freeze","paths":[],"nodes":[],"outcomes":[]}',
        filename="remote.json",
        live_url="https://kennisplatform.venvn.nl/wp-json/beslisboom/v1/outcomes",
    )
    assert is_story_html_alone(filename="story.html", data=STORY_FIXTURE.read_bytes())
    assert "story_html_alone_insufficient" in boom_freeze_errors(
        data=STORY_FIXTURE.read_bytes(),
        filename="story.html",
        live_url="",
    )

    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(console, accounts)
    assert receipt["sha256"] == digest
    objects = console.snapshot_objects(receipt["snapshot_id"])
    node = next(
        row
        for row in objects
        if (row.get("proposed_object_type") or row.get("object_type")) == "node"
        and "scorelist" not in str(row.get("scorelist")).lower()
        and "evenwicht" not in ((row.get("content") or {}).get("clean_text") or "")
    )
    outcome = next(
        row
        for row in objects
        if (row.get("proposed_object_type") or row.get("object_type")) == "outcome"
    )
    for row in (node, outcome):
        opened = console.open_source_passage(
            snapshot_id=receipt["snapshot_id"],
            object_id=row["object_id"],
        )
        assert opened["passage"]
        assert (row.get("content") or {}).get("clean_text") in opened["passage"] or opened["passage"]
        loc = None
        for frag in (row.get("provenance") or {}).get("source_fragments") or []:
            loc = frag.get("source_locator")
            if loc:
                break
        assert loc and loc.get("locator_value")

    with pytest.raises(ConsoleError, match="story_html_alone_insufficient|story_html_boom_player"):
        _ingest_boom(
            console,
            accounts,
            filename="story.html",
            data=STORY_FIXTURE.read_bytes(),
            content_type="text/html",
            title="Story only",
        )
    with pytest.raises(ConsoleError, match="live_rest_not_sole_source|live_url_html_not_allowed"):
        console.ingest(
            actor_id=accounts["researcher"]["account_id"],
            filename=None,
            data=None,
            url="https://kennisplatform.venvn.nl/wp-json/beslisboom/v1/outcomes",
            ingest_kind="new",
            title="Live REST",
            version="1.0",
            date="2025-04-01",
            live_url="https://kennisplatform.venvn.nl/wp-json/beslisboom/v1/outcomes",
            class_="beslisboom",
            family="valrisico",
            named_reviewers=[accounts["reviewer"]["account_id"]],
        )


def test_class_axis_richtlijn_recommendation_outranks_boom_outcome() -> None:
    assert CLASS_ORDER["richtlijn"] > CLASS_ORDER["beslisboom"]
    assert class_outranks("richtlijn", "beslisboom")
    assert not class_outranks("beslisboom", "richtlijn")
    richtlijn = {
        "object_id": "rec-1",
        "confirmed_object_type": "recommendation",
        "metadata": {"source_class": "richtlijn", "family": "valrisico"},
        "content": {"topic": ["valrisico", "class:richtlijn"]},
    }
    boom = {
        "object_id": "out-1",
        "confirmed_object_type": "outcome",
        "metadata": {"source_class": "beslisboom", "family": "valrisico"},
        "content": {"topic": ["valrisico", "class:beslisboom"]},
    }
    from src.beslisboom_path_v1 import preferred_same_family_advice

    winner = preferred_same_family_advice([boom, richtlijn], family="valrisico")
    assert winner["object_id"] == "rec-1"
    missing_richtlijn = preferred_same_family_advice([boom], family="valrisico")
    assert missing_richtlijn is None or missing_richtlijn.get("fills_missing_richtlijn") is False


def test_select_for_question_does_not_fill_richtlijn_with_boom(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    _ingest_boom(console, accounts)
    selected = console.select_for_question(family="valrisico", asked_class="richtlijn")
    assert selected == []
    boom_selected = console.select_for_question(family="valrisico", asked_class="beslisboom")
    assert boom_selected
    assert all(item["class"] == "beslisboom" for item in boom_selected)
    _ingest_richtlijn(console, accounts)
    selected = console.select_for_question(family="valrisico", asked_class="richtlijn")
    assert selected
    assert all(item["class"] == "richtlijn" for item in selected)


def test_g2_still_blocks_publish_for_boom_and_richtlijn(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    boom = _ingest_boom(console, accounts)
    richtlijn = _ingest_richtlijn(console, accounts, family="continentie", title="Richtlijn")
    for receipt in (boom, richtlijn):
        considered = console.consider_publish(
            actor_id=accounts["publisher"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
        )
        assert considered["publish_allowed"] is False
        assert considered["g2"] == "BLOCKED"
        published = console.publish(
            actor_id=accounts["publisher"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
        )
        assert published["status"] == "BLOCKED"
        assert published["g2"] == "BLOCKED"
        assert published["cutover"] is False


def test_product_api_does_not_serve_boom_outcomes() -> None:
    assert boom_serving_activated() is False
    assert "outcome" not in CLOSED_OBJECT_TYPES
    assert not is_closed_confirmed_type("outcome")
    assert not is_closed_confirmed_type("path")
    assert not is_closed_confirmed_type("node")
    record = {
        "object_id": "out-1",
        "metadata": {
            "confirmed_object_type": "outcome",
            "object_type": "outcome",
            "source_class": "beslisboom",
            "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:2-2"},
        },
    }
    assert published_object_type(record) == "unclassified"
    assert not is_advice_weight("action_advice", "outcome")


def test_answerability_does_not_support_boom_when_richtlijn_exists() -> None:
    from src.beslisboom_path_v1 import preferred_same_family_advice

    boom = {
        "object_id": "out-1",
        "canonical_object_hash": "a" * 64,
        "metadata": {
            "confirmed_object_type": "outcome",
            "object_type": "outcome",
            "source_class": "beslisboom",
            "family": "valrisico",
            "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:3-3"},
        },
        "content": {"clean_text": "Verwijs naar de valpoli."},
    }
    richtlijn = {
        "object_id": "rec-1",
        "canonical_object_hash": "b" * 64,
        "metadata": {
            "confirmed_object_type": "recommendation",
            "object_type": "recommendation",
            "source_class": "richtlijn",
            "family": "valrisico",
            "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:4-4"},
        },
        "content": {"clean_text": "Verwijs naar de valpoli."},
    }
    winner = preferred_same_family_advice([boom, richtlijn], family="valrisico")
    assert winner is not None
    assert winner["object_id"] == "rec-1"
    result = evaluate_answerability(
        "Wanneer verwijzen bij valrisico?",
        {"behavior": "retrieve", "results": [{"object_id": "out-1"}, {"object_id": "rec-1"}]},
        {"out-1": boom, "rec-1": richtlijn},
    )
    if result.get("answerability") == "supported":
        ids = [item.get("object_id") for item in result.get("results") or []]
        assert "out-1" not in ids
    assert published_object_type(boom) == "unclassified"


def test_path_confinement_rejects_dotdot_and_slashes_on_boom_ingest(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    with pytest.raises(ConsoleError, match="invalid_store_path"):
        _ingest_boom(console, accounts, filename="../escape.json", title="Escape")
    with pytest.raises(ConsoleError, match="invalid_store_path"):
        _ingest_boom(console, accounts, filename="sub/dir/boom.json", title="Slash")
    with pytest.raises(ConsoleError, match="invalid_store_path"):
        _ingest_boom(console, accounts, filename="..\\escape.json", title="WinEscape")


def test_handoff_not_recreated_and_no_nurse_tree_player() -> None:
    assert not (ROOT / "HANDOFF.md").exists()
    app_src = (ROOT / "src" / "operations_console_app.py").read_text(encoding="utf-8")
    assert "nurse tree player" not in app_src.lower()
    assert "storyline-player" not in app_src.lower()
    assert "interactive tree player" not in app_src.lower()


def _locator_value(obj: dict) -> str:
    loc = locator_of(obj) or {}
    return str(loc.get("locator_value") or "")


def test_approve_does_not_auto_confirm_proposed_applies_if(tmp_path: Path) -> None:
    """Codex P1: machine-proposed applies_if must not bind on approve."""
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(console, accounts)
    outcome = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("proposed_object_type") == "outcome"
        and obj.get("content", {}).get("clean_text", "").startswith("Verwijs")
    )
    assert any(
        rel.get("relation_type") == "applies_if" and rel.get("target_object_id")
        for rel in outcome.get("relations") or []
    )
    assert not (outcome.get("confirmed_relations") or [])
    with pytest.raises(ConsoleError, match="outcome_relation_unconfirmed|outcome_review_failed"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=outcome["object_id"],
            decision="approve",
            confirmed_object_type="outcome",
        )
    stored = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == outcome["object_id"]
    )
    assert stored.get("confirmed_relations") in (None, [], {})


def test_vitamine_d_extract_preserves_high_risk_fields(tmp_path: Path) -> None:
    """Codex P1: four-eyes must fire after boom extract of high-risk advice."""
    freeze = _boom_freeze_bytes()
    payload = json.loads(freeze.decode("utf-8"))
    payload["outcomes"].append(
        {
            "id": "out-vitd",
            "text": "Start vitamine D 800IE",
            "strength": "doen",
            "applies_if": ["node-vraag"],
            "dosage": "800",
            "unit": "IE",
        }
    )
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    fragments = extract_boom_fragments(data, document_id="doc-vitd", source_id="src-vitd")
    vit_frag = next(row for row in fragments if "vitamine D" in row.get("clean_text", ""))
    assert "dosage" in (vit_frag.get("risk_fields") or [])
    assert (vit_frag.get("risk_metadata") or {}).get("dosage") == "800"

    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(
        console,
        accounts,
        filename="vitd-boom.json",
        title="Vitamine D boom",
        data=data,
    )
    outcomes = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("proposed_object_type") == "outcome"
        and "vitamine D" in obj.get("content", {}).get("clean_text", "")
    ]
    assert outcomes
    assert requires_four_eyes(outcomes[0]) is True


def test_compact_json_freeze_uses_byte_span_locators(tmp_path: Path) -> None:
    """Codex P1: locators must point into original freeze bytes, not whole-file 1-1."""
    payload = json.loads(_boom_freeze_bytes().decode("utf-8"))
    payload["outcomes"][0]["text"] = 'Zeg "valpoli".'
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert compact.count(b"\n") == 0
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(
        console,
        accounts,
        filename="compact-boom.json",
        title="Compact boom",
        data=compact,
    )
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if (obj.get("proposed_object_type") or obj.get("object_type")) in {"path", "node", "outcome"}
    ]
    locators = [_locator_value(obj) for obj in objects]
    assert locators
    assert all("bytes:" in value for value in locators)
    assert len(set(locators)) == len(locators)
    for value in locators:
        match = re.search(r"bytes:(\d+)-(\d+)", value)
        assert match is not None
        start, end = int(match.group(1)), int(match.group(2))
        assert 0 <= start < end <= len(compact)
        assert compact[start:end] != compact
    quoted = [
        obj
        for obj in objects
        if "valpoli" in obj.get("content", {}).get("clean_text", "")
    ]
    assert quoted
    passage = console.open_source_passage(
        snapshot_id=receipt["snapshot_id"],
        object_id=quoted[0]["object_id"],
    )
    assert passage["passage"] != compact.decode("utf-8")
    assert "valpoli" in passage["passage"]


def test_canonical_review_hash_includes_no_action_and_metadata() -> None:
    """Codex P1: geen-actie must not hash-collide with positive advice."""
    base = {
        "object_id": "out-1",
        "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:1-1;bytes:0-10"},
        "content": {"clean_text": "Geen extra screening."},
        "proposed_object_type": "outcome",
        "confirmed_object_type": "outcome",
        "confirmed_relations": [{"relation_type": "applies_if", "target_object_id": "n-1"}],
        "proposed_recommendation_strength": "niet_doen",
        "confirmed_recommendation_strength": "niet_doen",
    }
    with_flag = {**base, "no_action": True, "metadata": {"mapped_from": "geen_actie"}}
    without_flag = dict(base)
    payload_with = canonical_object_payload(with_flag)
    assert payload_with.get("no_action") is True
    assert payload_with.get("metadata") == {"mapped_from": "geen_actie"}
    assert compute_canonical_object_hash(with_flag) != compute_canonical_object_hash(without_flag)


def test_actionable_outcome_approve_requires_strength(tmp_path: Path) -> None:
    """Codex P2: actionable outcomes cannot approve with a blank strength."""
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    outcome = next(
        obj
        for obj in objects
        if obj.get("proposed_object_type") == "outcome"
        and obj.get("content", {}).get("clean_text", "").startswith("Verwijs")
    )
    _confirm_applies_if(console, accounts, receipt["snapshot_id"], outcome)
    current = console.snapshot_objects(receipt["snapshot_id"])
    cleared = []
    for row in current:
        if row["object_id"] == outcome["object_id"]:
            row = dict(row)
            row["proposed_recommendation_strength"] = None
            row["confirmed_recommendation_strength"] = None
        cleared.append(row)
    console._save_objects(receipt["snapshot_id"], cleared)
    with pytest.raises(ConsoleError, match="outcome_strength_required|outcome_review_failed"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=outcome["object_id"],
            decision="approve",
            confirmed_object_type="outcome",
        )


def test_empty_local_boom_freeze_is_rejected(tmp_path: Path) -> None:
    """Codex P2: a local freeze without nodes+outcomes is not a valid boom source."""
    empty = json.dumps({"kind": "beslisboom-freeze"}, ensure_ascii=False).encode("utf-8")
    errors = boom_freeze_errors(data=empty, filename="empty-boom.json", live_url="")
    assert errors
    assert any("empty_boom_freeze" in err for err in errors)
    console = _console(tmp_path)
    accounts = _accounts(console)
    with pytest.raises(ConsoleError, match="empty_boom_freeze|invalid_boom_freeze"):
        _ingest_boom(
            console,
            accounts,
            filename="empty-boom.json",
            title="Empty boom",
            data=empty,
        )
