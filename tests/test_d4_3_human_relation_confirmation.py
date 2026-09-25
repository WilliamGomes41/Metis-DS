"""D4.3 human KnowledgeRelation confirmation regressions.

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
from src.knowledge_relation_review_v1 import relation_choice_value
from src.knowledge_relations_v1 import (
    CONFIRMED_FIELD,
    PROPOSED_FIELD,
    build_knowledge_relation,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole


REC = "De werkgroep adviseert de verpleegkundige interventie A te gebruiken."
COND = "De patiënt heeft een verhoogd risico wanneer score X aanwezig is."
EXPL = "Deze toelichting beschrijft waarom intensieve monitoring nodig is."


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime" / "console",
    )


def _accounts(console: OperationsConsole) -> dict[str, dict]:
    researcher = console.create_account(
        username="researcher.d43",
        password="researcher-secret",
        roles=("researcher", "reviewer"),
        display_name="D4.3 Researcher",
    )
    reviewer = console.create_account(
        username="reviewer.d43",
        password="reviewer-secret",
        roles=("reviewer",),
        display_name="D4.3 Reviewer",
    )
    return {"researcher": researcher, "reviewer": reviewer}


def _html() -> bytes:
    return (
        "<!doctype html><html lang='nl'><body>"
        "<h1>D4.3 richtlijn</h1>"
        f"<p>{COND}</p>"
        f"<p>{REC}</p>"
        f"<p>{EXPL}</p>"
        "</body></html>"
    ).encode("utf-8")


def _ingest(console: OperationsConsole, accounts: dict) -> dict:
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="d43.html",
        data=_html(),
        content_type="text/html",
        ingest_kind="new",
        title="D4.3 richtlijn",
        version="1.0",
        date="2026-09-25",
        live_url="https://example.test/d43",
        class_="richtlijn",
        family="test",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )


def _text(row: dict) -> str:
    return str((row.get("content") or {}).get("clean_text") or "")


def _rows(console: OperationsConsole, snapshot_id: str) -> dict[str, dict]:
    return {
        _text(row): row
        for row in console.snapshot_objects(snapshot_id)
        if _text(row)
    }


def _plant_proposals(
    console: OperationsConsole,
    snapshot_id: str,
    *,
    include_explanation: bool = True,
) -> tuple[dict, list[dict]]:
    current = _rows(console, snapshot_id)
    rec = current[REC]
    cond = current[COND]
    expl = current[EXPL]

    rows = console._load_objects(snapshot_id)
    proposal_rows: list[dict] = []
    for row in rows:
        if row["object_id"] == cond["object_id"]:
            row["proposed_object_type"] = "condition"
            stamp_canonical_hashes(row)
        elif row["object_id"] == expl["object_id"]:
            row["proposed_object_type"] = "explanation"
            stamp_canonical_hashes(row)
        elif row["object_id"] == rec["object_id"]:
            row["proposed_object_type"] = "recommendation"
            proposal_rows = [
                build_knowledge_relation(
                    source_object_id=row["object_id"],
                    source_object_version=row["object_version"],
                    relation_type="applies_if",
                    target_object_id=cond["object_id"],
                    target_object_version=cond["object_version"],
                )
            ]
            if include_explanation:
                proposal_rows.append(
                    build_knowledge_relation(
                        source_object_id=row["object_id"],
                        source_object_version=row["object_version"],
                        relation_type="supported_by",
                        target_object_id=expl["object_id"],
                        target_object_version=expl["object_version"],
                    )
                )
            proposal_rows.sort(
                key=lambda item: (
                    item["relation_type"],
                    item["target_object_id"],
                    item["target_object_version"],
                    item["relation_id"],
                )
            )
            row[PROPOSED_FIELD] = deepcopy(proposal_rows)
            row["relations"] = [
                {
                    "relation_type": item["relation_type"],
                    "target_object_id": item["target_object_id"],
                    "target_object_version": item["target_object_version"],
                    "confirmed": False,
                }
                for item in proposal_rows
            ]
            stamp_canonical_hashes(row)
    console._save_objects(snapshot_id, rows)
    live = _rows(console, snapshot_id)[REC]
    return live, proposal_rows


def _approve(
    console: OperationsConsole,
    accounts: dict,
    snapshot_id: str,
    object_id: str,
    choices: list[str],
) -> list[dict]:
    return console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=snapshot_id,
        object_id=object_id,
        decision="approve",
        confirmed_object_type="recommendation",
        relation_choices=choices,
        relation_review_ack=True,
        expected_revision=console.objects_revision(snapshot_id),
    )


def test_confirmation_rebinds_relation_ids_to_new_source_version_atomically(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    snapshot_id = _ingest(console, accounts)["snapshot_id"]
    rec, proposals = _plant_proposals(console, snapshot_id, include_explanation=False)

    before_version = rec["object_version"]
    before_hash = compute_canonical_object_hash(rec)
    proposal_id = proposals[0]["relation_id"]

    _approve(
        console,
        accounts,
        snapshot_id,
        rec["object_id"],
        [relation_choice_value(proposals[0])],
    )

    live = _rows(console, snapshot_id)[REC]
    assert live["object_version"] != before_version
    assert compute_canonical_object_hash(live) != before_hash
    assert PROPOSED_FIELD not in live
    [confirmed] = live[CONFIRMED_FIELD]
    assert confirmed["target_object_version"] == proposals[0]["target_object_version"]
    assert confirmed["relation_id"] != proposal_id
    assert live["confirmed_relations"] == [
        {
            "relation_type": confirmed["relation_type"],
            "target_object_id": confirmed["target_object_id"],
            "target_object_version": confirmed["target_object_version"],
            "confirmed": True,
        }
    ]

    evidence = live["metadata"]["knowledge_relation_review"]
    assert evidence["source_object_version_before"] == before_version
    assert evidence["source_object_version_after"] == live["object_version"]
    assert evidence["selected_proposal_relation_ids"] == [proposal_id]
    assert evidence["confirmed_relation_ids"] == [confirmed["relation_id"]]

    bindings = [
        row
        for row in console.object_review_bindings(snapshot_id)
        if row["object_id"] == rec["object_id"]
        and row["reviewer_id"] == accounts["reviewer"]["account_id"]
    ]
    assert len(bindings) == 1
    assert bindings[0]["valid"] is True
    assert bindings[0]["object_version"] == live["object_version"]
    assert bindings[0]["canonical_object_hash"] == compute_canonical_object_hash(live)

    history = [
        row
        for row in console._load_objects(snapshot_id)
        if row["object_id"] == rec["object_id"]
    ]
    assert any(
        row["object_version"] == before_version and PROPOSED_FIELD in row
        for row in history
    )


def test_reviewer_can_reject_one_machine_relation_from_atomic_set(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    snapshot_id = _ingest(console, accounts)["snapshot_id"]
    rec, proposals = _plant_proposals(console, snapshot_id, include_explanation=True)

    applies = next(row for row in proposals if row["relation_type"] == "applies_if")
    rejected = next(row for row in proposals if row["relation_type"] == "supported_by")
    _approve(
        console,
        accounts,
        snapshot_id,
        rec["object_id"],
        [relation_choice_value(applies)],
    )

    live = _rows(console, snapshot_id)[REC]
    assert [row["relation_type"] for row in live[CONFIRMED_FIELD]] == ["applies_if"]
    evidence = live["metadata"]["knowledge_relation_review"]
    assert rejected["relation_id"] in evidence["rejected_proposal_relation_ids"]


def test_empty_selection_is_valid_only_with_explicit_relation_acknowledgement(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    snapshot_id = _ingest(console, accounts)["snapshot_id"]
    rec, _proposals = _plant_proposals(console, snapshot_id, include_explanation=False)

    with pytest.raises(ConsoleError, match="knowledge_relation_review_required"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=snapshot_id,
            object_id=rec["object_id"],
            decision="approve",
            confirmed_object_type="recommendation",
            relation_choices=[],
            relation_review_ack=False,
            expected_revision=console.objects_revision(snapshot_id),
        )

    _approve(console, accounts, snapshot_id, rec["object_id"], [])
    live = _rows(console, snapshot_id)[REC]
    assert live[CONFIRMED_FIELD] == []
    assert live["confirmed_relations"] == []


def test_target_version_change_rejects_entire_confirmation_without_partial_write(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    snapshot_id = _ingest(console, accounts)["snapshot_id"]
    rec, proposals = _plant_proposals(console, snapshot_id, include_explanation=False)
    before = deepcopy(_rows(console, snapshot_id)[REC])

    rows = console._load_objects(snapshot_id)
    condition_id = proposals[0]["target_object_id"]
    for row in rows:
        if row["object_id"] == condition_id:
            row["object_version"] = "1.1"
            stamp_canonical_hashes(row)
    console._save_objects(snapshot_id, rows)

    with pytest.raises(ConsoleError, match="knowledge_relation_target_stale"):
        _approve(
            console,
            accounts,
            snapshot_id,
            rec["object_id"],
            [relation_choice_value(proposals[0])],
        )

    after = _rows(console, snapshot_id)[REC]
    assert after["object_version"] == before["object_version"]
    assert after.get(CONFIRMED_FIELD) == before.get(CONFIRMED_FIELD)
    assert after.get(PROPOSED_FIELD) == before.get(PROPOSED_FIELD)
    assert not any(
        row["object_id"] == rec["object_id"] and row.get("valid")
        for row in console.object_review_bindings(snapshot_id)
    )


def test_identical_human_confirmation_is_semantically_idempotent(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    snapshot_id = _ingest(console, accounts)["snapshot_id"]
    rec, proposals = _plant_proposals(console, snapshot_id, include_explanation=False)
    _approve(
        console,
        accounts,
        snapshot_id,
        rec["object_id"],
        [relation_choice_value(proposals[0])],
    )

    first = _rows(console, snapshot_id)[REC]
    first_version = first["object_version"]
    first_hash = compute_canonical_object_hash(first)
    [confirmed] = first[CONFIRMED_FIELD]

    _approve(
        console,
        accounts,
        snapshot_id,
        rec["object_id"],
        [relation_choice_value(confirmed)],
    )
    second = _rows(console, snapshot_id)[REC]
    assert second["object_version"] == first_version
    assert compute_canonical_object_hash(second) == first_hash


def test_review_ui_shows_version_bound_relations_and_requires_ack(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    snapshot_id = _ingest(console, accounts)["snapshot_id"]
    rec, proposals = _plant_proposals(console, snapshot_id, include_explanation=False)

    client = TestClient(create_console_app(console))
    client.post(
        "/login",
        data={"username": "reviewer.d43", "password": "reviewer-secret"},
    )
    html = client.get(
        f"/review?document={snapshot_id}&object={rec['object_id']}"
    ).text
    assert "Welke relaties kloppen?" in html
    assert 'name="relation_choice"' in html
    assert relation_choice_value(proposals[0]) in html
    assert 'name="relation_review_ack"' in html
    assert "versie 1.0" in html


def test_d43_does_not_make_new_format_relations_serving_authority(tmp_path: Path) -> None:
    from src.serving_relations_v1 import binding_relations

    console = _console(tmp_path)
    accounts = _accounts(console)
    snapshot_id = _ingest(console, accounts)["snapshot_id"]
    rec, proposals = _plant_proposals(console, snapshot_id, include_explanation=False)
    _approve(
        console,
        accounts,
        snapshot_id,
        rec["object_id"],
        [relation_choice_value(proposals[0])],
    )
    live = _rows(console, snapshot_id)[REC]

    # Serving still reads the exact legacy compatibility mirror until D4.4.
    assert binding_relations(live) == live["confirmed_relations"]
