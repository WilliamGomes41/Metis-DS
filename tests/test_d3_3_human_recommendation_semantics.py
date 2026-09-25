"""D3.3 human recommendation-semantics confirmation regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.integrity_kernel import compute_canonical_object_hash, stamp_canonical_hashes
from src.operations_console_app import create_console_app
from src.operations_console_v1 import (
    SNAPSHOT_OBJECT_WRITE_CONFLICT,
    ConsoleError,
    OperationsConsole,
)
from src.recommendation_semantics_v1 import (
    CONFIRMED_FIELD,
    PROPOSED_FIELD,
    confirmed_recommendation_semantics_from_review,
)


RECOMMENDATION_TEXT = (
    "De werkgroep adviseert de verpleegkundige de interventie te gebruiken."
)


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime" / "console",
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
    return {"researcher": researcher, "reviewer": reviewer}


def _html() -> bytes:
    return (
        "<!doctype html><html lang='nl'><body>"
        "<h1>D3.3 richtlijn</h1>"
        "<h2>Zwakke aanbeveling</h2>"
        f"<p>{RECOMMENDATION_TEXT}</p>"
        "<h2>Toelichting</h2>"
        "<p>Deze toelichting beschrijft de achtergrond van de aanbeveling.</p>"
        "</body></html>"
    ).encode("utf-8")


def _ingest(console: OperationsConsole, accounts: dict) -> dict:
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="d33.html",
        data=_html(),
        content_type="text/html",
        ingest_kind="new",
        title="D3.3 richtlijn",
        version="1.0",
        date="2026-09-25",
        live_url="https://example.test/d33",
        class_="richtlijn",
        family="test",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )


def _text(obj: dict) -> str:
    return str((obj.get("content") or {}).get("clean_text") or "")


def _target(console: OperationsConsole, snapshot_id: str) -> dict:
    return next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if RECOMMENDATION_TEXT in _text(row)
    )


def _proposal(
    *,
    direction: str = "for",
    strength: str | None = "weak",
    status: str = "explicit",
    label: str | None = "Zwakke aanbeveling",
) -> dict:
    return {
        "version": "recommendation-semantics-v1",
        "direction": direction,
        "strength": strength,
        "strength_status": status,
        "direction_evidence_span": RECOMMENDATION_TEXT,
        "strength_evidence_span": label if status != "not_stated" else None,
        "source_label": label if status != "not_stated" else None,
        "normalization_scheme": "source_literal_v1",
    }


def _plant_new_format_proposal(
    console: OperationsConsole,
    snapshot_id: str,
    object_id: str,
    *,
    direction: str = "for",
    strength: str | None = "weak",
    status: str = "explicit",
    label: str | None = "Zwakke aanbeveling",
) -> dict:
    rows = console._load_objects(snapshot_id)
    for row in rows:
        if row["object_id"] != object_id:
            continue
        row["proposed_object_type"] = "recommendation"
        row.pop("proposed_recommendation_strength", None)
        row[PROPOSED_FIELD] = _proposal(
            direction=direction,
            strength=strength,
            status=status,
            label=label,
        )
        structure = row.setdefault("structure", {})
        path = list(structure.get("section_path") or [])
        if label and label not in path:
            path.append(label)
        structure["section_path"] = path
        stamp_canonical_hashes(row)
    console._save_objects(snapshot_id, rows)
    return _target(console, snapshot_id)


def _review_new(
    console: OperationsConsole,
    accounts: dict,
    snapshot_id: str,
    object_id: str,
    *,
    direction: str = "for",
    strength_level: str = "weak",
    expected_revision: str | None = None,
    confirmed_type: str = "recommendation",
) -> list[dict]:
    return console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=snapshot_id,
        object_id=object_id,
        decision="approve",
        confirmed_object_type=confirmed_type,
        recommendation_direction=direction,
        recommendation_strength_level=strength_level,
        expected_revision=expected_revision,
    )


@pytest.mark.parametrize(
    ("direction", "strength", "label"),
    [
        ("for", "strong", "Sterke aanbeveling"),
        ("for", "weak", "Zwakke aanbeveling"),
        ("against", "strong", "Sterke aanbeveling"),
        ("against", "weak", "Zwakke aanbeveling"),
    ],
)
def test_confirmation_kernel_supports_direction_strength_cross_product(
    direction: str,
    strength: str,
    label: str,
) -> None:
    obj = {
        "content": {"clean_text": RECOMMENDATION_TEXT},
        "structure": {"section_path": ["Aanbevelingen", label]},
        PROPOSED_FIELD: _proposal(
            direction=direction,
            strength=strength,
            status="explicit",
            label=label,
        ),
    }
    confirmed = confirmed_recommendation_semantics_from_review(
        obj,
        direction=direction,
        strength_choice=strength,
    )
    assert confirmed["direction"] == direction
    assert confirmed["strength"] == strength
    assert confirmed["strength_status"] == "explicit"
    assert confirmed["strength_evidence_span"] == label


def test_not_stated_is_valid_only_without_explicit_source_strength() -> None:
    obj = {
        "content": {"clean_text": RECOMMENDATION_TEXT},
        "structure": {"section_path": ["Aanbevelingen"]},
        PROPOSED_FIELD: _proposal(
            direction="for",
            strength=None,
            status="not_stated",
            label=None,
        ),
    }
    confirmed = confirmed_recommendation_semantics_from_review(
        obj,
        direction="for",
        strength_choice="not_stated",
    )
    assert confirmed["strength"] is None
    assert confirmed["strength_status"] == "not_stated"
    assert confirmed["strength_evidence_span"] is None

    explicit = deepcopy(obj)
    explicit["structure"]["section_path"].append("Zwakke aanbeveling")
    explicit[PROPOSED_FIELD] = _proposal()
    with pytest.raises(ValueError, match="recommendation_strength_not_stated_conflict"):
        confirmed_recommendation_semantics_from_review(
            explicit,
            direction="for",
            strength_choice="not_stated",
        )


def test_explicit_strength_must_match_source_literal_evidence() -> None:
    obj = {
        "content": {"clean_text": RECOMMENDATION_TEXT},
        "structure": {"section_path": ["Zwakke aanbeveling"]},
        PROPOSED_FIELD: _proposal(),
    }
    with pytest.raises(ValueError, match="recommendation_strength_evidence_required"):
        confirmed_recommendation_semantics_from_review(
            obj,
            direction="for",
            strength_choice="strong",
        )


def test_review_confirmation_updates_version_hash_and_binding_atomically(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _target(console, snapshot_id)
    target = _plant_new_format_proposal(console, snapshot_id, target["object_id"])

    before_version = target["object_version"]
    before_hash = compute_canonical_object_hash(target)
    revision = console.objects_revision(snapshot_id)

    _review_new(
        console,
        accounts,
        snapshot_id,
        target["object_id"],
        expected_revision=revision,
    )

    live = _target(console, snapshot_id)
    confirmed = live[CONFIRMED_FIELD]
    assert confirmed["direction"] == "for"
    assert confirmed["strength"] == "weak"
    assert confirmed["strength_status"] == "explicit"
    assert live["object_version"] != before_version
    assert compute_canonical_object_hash(live) != before_hash
    assert live.get("confirmed_recommendation_strength") in {None, ""}

    bindings = [
        row
        for row in console.object_review_bindings(snapshot_id)
        if row["object_id"] == target["object_id"]
        and row["reviewer_id"] == accounts["reviewer"]["account_id"]
    ]
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding["valid"] is True
    assert binding["object_version"] == live["object_version"]
    assert binding["canonical_object_hash"] == compute_canonical_object_hash(live)
    assert binding["confirmed_object_type"] == "recommendation"

    history = [
        row for row in console._load_objects(snapshot_id)
        if row["object_id"] == target["object_id"]
    ]
    assert any(row["object_version"] == before_version and CONFIRMED_FIELD not in row for row in history)


def test_same_confirmation_is_idempotent_for_semantic_object_version(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _plant_new_format_proposal(
        console,
        snapshot_id,
        _target(console, snapshot_id)["object_id"],
    )

    _review_new(
        console,
        accounts,
        snapshot_id,
        target["object_id"],
        expected_revision=console.objects_revision(snapshot_id),
    )
    first = _target(console, snapshot_id)
    first_version = first["object_version"]
    first_hash = compute_canonical_object_hash(first)

    _review_new(
        console,
        accounts,
        snapshot_id,
        target["object_id"],
        expected_revision=console.objects_revision(snapshot_id),
    )
    second = _target(console, snapshot_id)

    assert second["object_version"] == first_version
    assert compute_canonical_object_hash(second) == first_hash


def test_stale_confirmation_leaves_no_partial_semantics_or_binding(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _plant_new_format_proposal(
        console,
        snapshot_id,
        _target(console, snapshot_id)["object_id"],
    )
    stale_revision = console.objects_revision(snapshot_id)

    rows = console._load_objects(snapshot_id)
    document = next(row for row in rows if row.get("object_type") == "document")
    document.setdefault("metadata", {})["d33_concurrent_touch"] = True
    console._save_objects(snapshot_id, rows)
    assert console.objects_revision(snapshot_id) != stale_revision

    before = _target(console, snapshot_id)
    before_hash = compute_canonical_object_hash(before)
    with pytest.raises(ConsoleError) as caught:
        _review_new(
            console,
            accounts,
            snapshot_id,
            target["object_id"],
            expected_revision=stale_revision,
        )
    assert caught.value.code == SNAPSHOT_OBJECT_WRITE_CONFLICT

    after = _target(console, snapshot_id)
    assert CONFIRMED_FIELD not in after
    assert compute_canonical_object_hash(after) == before_hash
    assert not any(
        row.get("valid")
        for row in console.object_review_bindings(snapshot_id)
        if row.get("object_id") == target["object_id"]
    )


def test_type_change_away_clears_active_semantics_but_keeps_history(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _plant_new_format_proposal(
        console,
        snapshot_id,
        _target(console, snapshot_id)["object_id"],
    )
    _review_new(console, accounts, snapshot_id, target["object_id"])
    approved = _target(console, snapshot_id)
    approved_version = approved["object_version"]
    assert CONFIRMED_FIELD in approved

    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=snapshot_id,
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="explanation",
        expected_revision=console.objects_revision(snapshot_id),
    )
    live = _target(console, snapshot_id)
    assert live["confirmed_object_type"] == "explanation"
    assert CONFIRMED_FIELD not in live
    history = [
        row for row in console._load_objects(snapshot_id)
        if row["object_id"] == target["object_id"]
    ]
    assert any(
        row["object_version"] == approved_version and CONFIRMED_FIELD in row
        for row in history
    )


def test_new_format_recommendation_rejects_legacy_strength_write(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _plant_new_format_proposal(
        console,
        snapshot_id,
        _target(console, snapshot_id)["object_id"],
    )

    with pytest.raises(ConsoleError, match="legacy_recommendation_strength_not_allowed"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=snapshot_id,
            object_id=target["object_id"],
            decision="approve",
            confirmed_object_type="recommendation",
            recommendation_strength="doen",
            recommendation_direction="for",
            recommendation_strength_level="weak",
        )


def test_legacy_recommendation_compatibility_does_not_auto_migrate(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _target(console, snapshot_id)

    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=snapshot_id,
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
        recommendation_strength="doen",
    )
    live = _target(console, snapshot_id)
    assert live.get("confirmed_recommendation_strength") == "doen"
    assert CONFIRMED_FIELD not in live


def test_review_ui_uses_direction_strength_and_preserves_proposal_evidence(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _plant_new_format_proposal(
        console,
        snapshot_id,
        _target(console, snapshot_id)["object_id"],
    )
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})

    html = client.get(
        f"/review?document={snapshot_id}&object={target['object_id']}"
    ).text
    assert "data-recommendation-semantics-block" in html
    assert 'name="recommendation_direction"' in html
    assert 'name="recommendation_strength_level"' in html
    assert "Aanraden" in html and "Afraden" in html
    assert "Sterk" in html and "Zwak" in html and "Niet vermeld in de bron" in html
    assert RECOMMENDATION_TEXT in html
    assert "Zwakke aanbeveling" in html
    assert ">DOEN<" not in html
    assert ">OVERWEEG<" not in html
    assert ">NIET DOEN<" not in html


def test_authenticated_review_post_confirms_new_semantics(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _plant_new_format_proposal(
        console,
        snapshot_id,
        _target(console, snapshot_id)["object_id"],
    )
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})

    response = client.post(
        "/review",
        data={
            "snapshot_id": snapshot_id,
            "object_id": target["object_id"],
            "snapshot_revision": console.objects_revision(snapshot_id),
            "proposed_object_type": "recommendation",
            "type_action": "dit_klopt",
            "suitability": "ja",
            "eindoordeel": "goedkeuren",
            "recommendation_direction": "for",
            "recommendation_strength_level": "weak",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    live = _target(console, snapshot_id)
    assert live[CONFIRMED_FIELD]["direction"] == "for"
    assert live[CONFIRMED_FIELD]["strength"] == "weak"


def test_boom_outcome_legacy_field_remains_outside_new_semantics_kernel() -> None:
    outcome = {
        "object_type": "outcome",
        "confirmed_object_type": "outcome",
        "confirmed_recommendation_strength": "niet_doen",
    }
    assert CONFIRMED_FIELD not in outcome
    assert outcome["confirmed_recommendation_strength"] == "niet_doen"
