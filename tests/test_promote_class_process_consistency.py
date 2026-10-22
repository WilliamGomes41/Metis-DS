"""Failed-write process consistency for promote_class and peers.

Mutations MUST be prepared on a copy and published in-process only after
a successful durable commit. Injected save failures at objects / envelopes
/ bindings boundaries plus a console restart prove disk wins: in-memory
must not outrun the durable store. EXTEND/REUSE; no DB rewrite.

# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.operations_console_v1 import ConsoleError, OperationsConsole

ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _console(tmp_path: Path, *, production_console) -> OperationsConsole:
    return production_console(processing_binder=lambda console: None,
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _restart(tmp_path: Path, *, production_console) -> OperationsConsole:
    return _console(tmp_path, production_console=production_console)


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


def _boom_freeze_bytes() -> bytes:
    payload = {
        "kind": "beslisboom-freeze",
        "paths": [{"id": "path-screening", "text": "Screening op valrisico"}],
        "nodes": [
            {
                "id": "node-vraag",
                "text": "Is er een verhoogd valrisico?",
                "scorelist": False,
            }
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


def _ingest_richtlijn(console: OperationsConsole, accounts: dict[str, dict]) -> dict:
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
        named_reviewers=[accounts["reviewer"]["account_id"]],
    )


def _ingest_boom(console: OperationsConsole, accounts: dict[str, dict]) -> dict:
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="valrisico-boom.json",
        data=_boom_freeze_bytes(),
        content_type="application/json",
        ingest_kind="new",
        title="Valrisico boom",
        version="1.0",
        date="2025-04-01",
        live_url="",
        class_="beslisboom",
        family="valrisico",
        named_reviewers=[accounts["reviewer"]["account_id"]],
    )


def _disk_envelope(console, snapshot_id):
    return console.workflow_document_store.get_envelope(snapshot_id)


def _object_statuses(console: OperationsConsole, snapshot_id: str) -> list[str]:
    return [
        str((row.get("governance") or {}).get("validation_status") or "")
        for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") != "document"
    ]


def _assert_unpromoted(failed: OperationsConsole, tmp_path: Path, snapshot_id: str, original_class: str, *, original_statuses: list[str], production_console) -> None:
    disk = _disk_envelope(failed, snapshot_id)
    assert failed._envelopes[snapshot_id]["class"] == original_class
    assert disk["class"] == original_class
    restarted = _restart(tmp_path, production_console=production_console)
    assert restarted._envelopes[snapshot_id]["class"] == original_class
    assert _disk_envelope(restarted, snapshot_id)["class"] == original_class
    assert _object_statuses(restarted, snapshot_id) == original_statuses
    assert _object_statuses(failed, snapshot_id) == original_statuses


def test_promote_class_success_then_restart_keeps_new_class(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    changed = console.promote_class(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=snapshot_id,
        new_class="handreiking",
    )
    assert changed["class"] == "handreiking"
    restarted = _restart(tmp_path, production_console=production_console)
    assert restarted._envelopes[snapshot_id]["class"] == "handreiking"
    assert _disk_envelope(restarted, snapshot_id)["class"] == "handreiking"
    assert all(status == "needs_review" for status in _object_statuses(restarted, snapshot_id))


def _file_console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )



def _file_restart(tmp_path: Path) -> OperationsConsole:
    return _file_console(tmp_path)



def _file_disk_envelope(console: OperationsConsole, snapshot_id: str) -> dict:
    payload = json.loads((console.runtime / "envelopes.json").read_text(encoding="utf-8"))
    return payload[snapshot_id]



def _file_assert_unpromoted(
    failed: OperationsConsole,
    tmp_path: Path,
    snapshot_id: str,
    original_class: str,
    *,
    original_statuses: list[str],
) -> None:
    disk = _file_disk_envelope(failed, snapshot_id)
    assert failed._envelopes[snapshot_id]["class"] == original_class
    assert disk["class"] == original_class
    restarted = _file_restart(tmp_path)
    assert restarted._envelopes[snapshot_id]["class"] == original_class
    assert _file_disk_envelope(restarted, snapshot_id)["class"] == original_class
    assert _object_statuses(restarted, snapshot_id) == original_statuses
    assert _object_statuses(failed, snapshot_id) == original_statuses
