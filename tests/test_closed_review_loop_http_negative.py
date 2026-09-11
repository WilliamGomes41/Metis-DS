"""HTTP boundary regression for closed-loop Review repair.

# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.closed_review_loop_v1 import ClosedLoopReviewConsole, install_closed_review_routes
from src.operations_console_app import create_console_app
from src.proportionate_review_v1 import normal_risk_batch_queue
from src.review_cockpit_v1 import broncontext_parts, confirmable_proposed_type
from src.review_ledger import read_events


def test_wrong_role_repair_post_fails_closed_without_writes(tmp_path):
    console = ClosedLoopReviewConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    researcher = console.create_account(
        username="anne", password="anne-secret", roles=("researcher",)
    )
    reviewer = console.create_account(
        username="bert", password="bert-secret", roles=("reviewer",)
    )
    publisher = console.create_account(
        username="piet", password="piet-secret", roles=("publisher",)
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="begrippen.html",
        content_type="text/html",
        data=(
            b"<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>"
            b"<p>De Dutch Job Group is een meetinstrument voor werkbelasting.</p>"
            b"</body></html>"
        ),
        ingest_kind="new",
        title="Begrippen",
        version="1.0",
        date="2026-09-10",
        live_url="",
        class_="richtlijn",
        family="begrippen",
        named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    oid = normal_risk_batch_queue(
        console.snapshot_objects(sid), review_path="richtlijn"
    )[0]["object_id"]
    obj = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    console.review_object(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=oid,
        decision="revise",
        comment="Brongebonden herstel.",
        proposed_correction="",
        confirmed_object_type=(confirmable_proposed_type(obj) or None),
        suitability="mist_context",
        eindoordeel="goedkeuren_na_correctie",
        type_action="dit_klopt",
    )
    before = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    ledger_before = list(read_events(console._ledger_path))
    exact = broncontext_parts(before)["source_text_exact"]

    app = create_console_app(console)
    install_closed_review_routes(app, console)
    client = TestClient(app, base_url="https://testserver")
    login = client.post(
        "/login", data={"username": "piet", "password": "piet-secret"}
    )
    assert login.status_code in {200, 303}

    response = client.post(
        "/review/repair/source",
        data={
            "snapshot_id": sid,
            "object_id": oid,
            "corrected_text": exact,
            "reason": "Wrong-role repair must not write.",
            "snapshot_revision": console.objects_revision(sid),
        },
        follow_redirects=False,
    )

    assert response.status_code == 403
    after = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    assert after == before
    assert read_events(console._ledger_path) == ledger_before
