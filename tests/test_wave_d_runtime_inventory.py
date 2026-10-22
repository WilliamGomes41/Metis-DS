"""Protocol v2.22 wave D: inventory, backup/restore, integrity, --clean true."""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import json
from pathlib import Path

import pytest

from src.g2_source_store import g2_gate_status
from src.operations_console_v1 import OperationsConsole
from src.runtime_data_inventory_v1 import (
    INVENTORY_CATEGORIES,
    CleanDeployError,
    RuntimeDataError,
    apply_clean_wwwroot,
    export_runtime_data,
    integrity_check,
    inventory_runtime_data,
    restore_runtime_data,
    safe_backup_member,
)


ROOT = Path(__file__).resolve().parents[1]


def _console(tmp_path: Path, *, production_console) -> OperationsConsole:
    return production_console(processing_binder=bind_fixture_selections,
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _seed_console(tmp_path: Path, *, production_console) -> tuple[OperationsConsole, dict[str, str]]:
    console = _console(tmp_path, production_console=production_console)
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
    html = (
        b"<!doctype html><html lang='nl'><head><title>Continentie</title></head>"
        b"<body><h1>Continentie</h1>"
        b"<p>Dit is een aanbeveling voor continentiezorg in de praktijk.</p>"
        b"</body></html>"
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="richtlijn.html",
        data=html,
        content_type="text/html",
        ingest_kind="new",
        title="Continentie fixture",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/richtlijn",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[researcher["account_id"], reviewer["account_id"]],
    )
    return console, receipt


def test_clean_true_wipes_wwwroot_and_must_not_delete_runtime_data(tmp_path: Path) -> None:
    wwwroot = tmp_path / "site" / "wwwroot"
    data_root = tmp_path / "home" / "data" / "metis-console"
    (wwwroot / "old.py").parent.mkdir(parents=True)
    (wwwroot / "old.py").write_text("stale\n", encoding="utf-8")
    (wwwroot / "nested" / "stale.txt").parent.mkdir(parents=True)
    (wwwroot / "nested" / "stale.txt").write_text("gone\n", encoding="utf-8")
    data_root.mkdir(parents=True)
    keep = data_root / "accounts.json"
    keep.write_text('{"keep":true}\n', encoding="utf-8")
    freeze = data_root / "sources" / "private" / "freeze.html"
    freeze.parent.mkdir(parents=True)
    freeze.write_bytes(b"<html></html>")

    result = apply_clean_wwwroot(wwwroot=wwwroot, runtime_data_root=data_root, clean=True)
    assert result["wwwroot_wiped"] is True
    assert result["runtime_data_deleted"] is False
    assert not (wwwroot / "old.py").exists()
    assert not (wwwroot / "nested" / "stale.txt").exists()
    assert keep.read_text(encoding="utf-8") == '{"keep":true}\n'
    assert freeze.is_file()

    result_false = apply_clean_wwwroot(wwwroot=wwwroot, runtime_data_root=data_root, clean=False)
    assert result_false["wwwroot_wiped"] is False

    overlapping = tmp_path / "overlap"
    overlapping.mkdir()
    with pytest.raises(CleanDeployError, match="runtime_data_must_not_live_in_wwwroot"):
        apply_clean_wwwroot(wwwroot=overlapping, runtime_data_root=overlapping / "data", clean=True)


def test_migration_boundary_is_documented() -> None:
    recovery = (ROOT / "docs" / "RUNTIME_DATA_RECOVERY.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "TEST_AND_RELEASE_RUNBOOK.md").read_text(encoding="utf-8")
    assert "managed database" in recovery.lower() or "managed database" in runbook.lower()
    assert "meerdere App Service-instances" in recovery or "multiple App Service instances" in recovery
    assert "multi-reviewer" in recovery or "gelijktijdige multi-reviewer" in recovery
    assert "geen grote databasemigratie" in recovery.lower() or "no large database migration" in recovery.lower()
    assert "/home/data/metis-console" in recovery
    assert "--clean true" in recovery
    assert "wwwroot" in recovery


def test_wave_d_does_not_open_publish(tmp_path: Path, *, production_console) -> None:
    console, receipt = _seed_console(tmp_path, production_console=production_console)
    publisher = console.create_account(
        username="publisher.carla",
        password="carla-secret",
        roles=("publisher",),
        display_name="Carla",
    )
    published = console.publish(
        actor_id=publisher["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert published["status"] == "BLOCKED"
    assert published["g2"] == "BLOCKED"
    assert published["cutover"] is False
    assert g2_gate_status() == "BLOCKED"


def _file_console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )



def _seed_file_console(tmp_path: Path) -> tuple[OperationsConsole, dict[str, str]]:
    console = _file_console(tmp_path)
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
    html = (
        b"<!doctype html><html lang='nl'><head><title>Continentie</title></head>"
        b"<body><h1>Continentie</h1>"
        b"<p>Dit is een aanbeveling voor continentiezorg in de praktijk.</p>"
        b"</body></html>"
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="richtlijn.html",
        data=html,
        content_type="text/html",
        ingest_kind="new",
        title="Continentie fixture",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/richtlijn",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[researcher["account_id"], reviewer["account_id"]],
    )
    projection = console.runtime / "published_projection.jsonl"
    projection.write_text(
        json.dumps({"snapshot_id": "snap-ffffffffffffffff-00000000", "derived": True}) + "\n",
        encoding="utf-8",
    )
    ledger = console.runtime / "review_ledger.jsonl"
    if not ledger.is_file():
        ledger.write_text(
            json.dumps(
                {
                    "event_type": "inventory_seed",
                    "snapshot_id": receipt["snapshot_id"],
                    "actor": researcher["account_id"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
    return console, {
        "snapshot_id": receipt["snapshot_id"],
        "sha256": receipt["sha256"],
        "title": receipt["title"],
    }



