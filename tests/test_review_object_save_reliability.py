"""Review object JSONL save reliability (audit wave 1).

Snapshot object writes MUST be atomic (no torn/empty JSONL on interrupt)
and MUST NOT silently last-write-wins when two reviewers overlap on the
same snapshot. Concurrent conflict fails closed with ConsoleError.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here. publish() stays
G2-BLOCKED. Phase 3/4 + Dit klopt paths stay.
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import json
import os
import threading
from pathlib import Path

import pytest

from src.operations_console_v1 import ConsoleError, OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
SNAPSHOT_WRITE_CONFLICT = "snapshot_object_write_conflict"


def _console(tmp_path: Path, *, production_console) -> OperationsConsole:
    return production_console(processing_binder=bind_fixture_selections,
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
    return {"researcher": researcher, "reviewer": reviewer}


def _ingest(console: OperationsConsole, accounts: dict) -> dict:
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Continentie fixture",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/continentie",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )


def _content_rows(console: OperationsConsole, snapshot_id: str) -> list[dict]:
    rows = [
        row
        for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") != "document"
    ]
    assert len(rows) >= 2
    return rows


def _parse_objects_jsonl(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    assert text.strip(), "snapshot object JSONL MUST NOT be empty"
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _passage_suitability(row: dict) -> str:
    return str(((row.get("metadata") or {}).get("review_passage") or {}).get("suitability") or "")


def test_sequential_save_objects_keeps_both_updates(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    first, second = _content_rows(console, snapshot_id)[:2]

    rows = console._load_objects(snapshot_id)
    for row in rows:
        if row["object_id"] == first["object_id"]:
            row["reliability_marker"] = "alpha"
    console._save_objects(snapshot_id, rows)

    rows = console._load_objects(snapshot_id)
    for row in rows:
        if row["object_id"] == second["object_id"]:
            row["reliability_marker"] = "beta"
    console._save_objects(snapshot_id, rows)

    stored = {row["object_id"]: row for row in console._load_objects(snapshot_id)}
    assert stored[first["object_id"]]["reliability_marker"] == "alpha"
    assert stored[second["object_id"]]["reliability_marker"] == "beta"
    assert console._load_objects(snapshot_id)


def test_overlapping_save_objects_does_not_silently_drop_a_marker(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    first, second = _content_rows(console, snapshot_id)[:2]
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def writer(object_id: str, marker: str) -> None:
        try:
            rows = console._load_objects(snapshot_id)
            barrier.wait(timeout=5)
            for row in rows:
                if row["object_id"] == object_id:
                    row["reliability_marker"] = marker
            console._save_objects(snapshot_id, rows)
        except ConsoleError as exc:
            errors.append(exc)
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=(first["object_id"], "alpha")),
        threading.Thread(target=writer, args=(first["object_id"], "beta")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    stored = console._load_objects(snapshot_id)
    markers = {
        row.get("reliability_marker")
        for row in stored
        if row.get("reliability_marker") in {"alpha", "beta"}
    }
    conflict_errors = [
        exc
        for exc in errors
        if isinstance(exc, ConsoleError) and exc.code == SNAPSHOT_WRITE_CONFLICT
    ]
    unexpected = [exc for exc in errors if exc not in conflict_errors]
    assert unexpected == []
    assert conflict_errors, "overlapping save MUST fail closed with snapshot_object_write_conflict"
    assert len(markers) == 1
    assert markers <= {"alpha", "beta"}


def test_stale_revision_save_fails_closed_with_console_error(tmp_path: Path, *, production_console) -> None:
    """Two reviewers / two console instances: loser MUST raise, winner MUST remain."""
    first = _console(tmp_path, production_console=production_console)
    accounts = _accounts(first)
    receipt = _ingest(first, accounts)
    snapshot_id = receipt["snapshot_id"]
    second = production_console(processing_binder=bind_fixture_selections,
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    content = _content_rows(first, snapshot_id)
    rows_a = first._load_objects(snapshot_id)
    rows_b = second._load_objects(snapshot_id)
    for row in rows_a:
        if row["object_id"] == content[0]["object_id"]:
            row["reliability_marker"] = "anne"
    for row in rows_b:
        if row["object_id"] == content[0]["object_id"]:
            row["reliability_marker"] = "bert"
    first._save_objects(snapshot_id, rows_a)
    with pytest.raises(ConsoleError) as caught:
        second._save_objects(snapshot_id, rows_b)
    assert caught.value.code == SNAPSHOT_WRITE_CONFLICT
    stored = first._load_objects(snapshot_id)
    markers = {row.get("reliability_marker") for row in stored if row.get("reliability_marker")}
    assert markers == {"anne"}
    assert "bert" not in json.dumps(stored, ensure_ascii=False)


def _file_console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
