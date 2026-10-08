"""T12 tests-first authority regressions against the merged T11 baseline.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from pathlib import Path

from src.integrity_kernel import stamp_canonical_hashes
from src.knowledge_path_v1 import content_reviewable
from src import publication_readiness_v1 as readiness_module
from src.publication_readiness_v1 import REVIEW_WORK_INCOMPLETE
from src.review_closure_v1 import ReviewClosureConsole
from tests.semantic_fixture_support import bind_fixture_selections, install_fixture_history

ROOT = Path(__file__).resolve().parents[1]


def _console(tmp_path):
    console = ReviewClosureConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    author = console.create_account(
        username="anne", password="anne-secret", roles=("researcher",)
    )
    reviewer = console.create_account(
        username="bert", password="bert-secret", roles=("reviewer",)
    )
    bind_fixture_selections(
        console, [("Oedeem is een ophoping van vocht.", "definition")]
    )
    receipt = console.ingest(
        actor_id=author["account_id"],
        filename="source.html",
        content_type="text/html",
        data=(
            b"<html><body><h1>Begrippen</h1>"
            b"<p>Oedeem is een ophoping van vocht.</p></body></html>"
        ),
        ingest_kind="new",
        title="Begrippen",
        version="1.0",
        date="2026-10-08",
        live_url="",
        class_="richtlijn",
        family="test",
        named_reviewers=[reviewer["account_id"]],
    )
    return console, receipt["snapshot_id"]


# RED: merged T11 still exposes the action-oriented readiness bypass.\ndef test_readiness_has_no_internal_publisher_capability() -> None:
    source = (ROOT / "src" / "publication_readiness_v1.py").read_text(encoding="utf-8")

    assert "_READINESS_EVALUATION_CAPABILITY" not in source
    assert "code.startswith(" not in source


def test_governance_approved_without_exact_t9_binding_stays_in_review(tmp_path) -> None:
    console, snapshot_id = _console(tmp_path)
    rows = console.snapshot_objects(snapshot_id)
    candidate = next(row for row in rows if content_reviewable(row))
    candidate["object_type"] = candidate["confirmed_object_type"] = "definition"
    candidate["governance"]["validation_status"] = "approved"
    stamp_canonical_hashes(candidate)
    install_fixture_history(console, snapshot_id, rows)
    before_objects = deepcopy(console.snapshot_objects(snapshot_id, include_blocked=True))
    before_bindings = deepcopy(console.object_review_bindings(snapshot_id))
    before_envelope = deepcopy(console._envelope(snapshot_id))

    readiness = console.publication_readiness(snapshot_id)

    assert readiness["review_complete"] is False
    assert readiness["curation_ready"] is False
    assert REVIEW_WORK_INCOMPLETE in readiness["curation_blockers"]
    assert candidate["object_id"] in readiness["unresolved_review_object_ids"]
    assert console.snapshot_objects(snapshot_id, include_blocked=True) == before_objects
    assert console.object_review_bindings(snapshot_id) == before_bindings
    assert console._envelope(snapshot_id) == before_envelope


def test_one_readiness_request_reads_each_current_input_once(monkeypatch, tmp_path) -> None:
    console, snapshot_id = _console(tmp_path)
    counts = {"objects": 0, "bindings": 0, "fragments": 0, "source": 0}
    original_objects = console.snapshot_objects
    original_bindings = console.object_review_bindings
    original_fragments = console.review_source_fragments
    original_source = readiness_module.source_accountability

    def objects(*args, **kwargs):
        counts["objects"] += 1
        return original_objects(*args, **kwargs)

    def bindings(*args, **kwargs):
        counts["bindings"] += 1
        return original_bindings(*args, **kwargs)

    def fragments(*args, **kwargs):
        counts["fragments"] += 1
        return original_fragments(*args, **kwargs)

    def source(*args, **kwargs):
        counts["source"] += 1
        return original_source(*args, **kwargs)

    monkeypatch.setattr(console, "snapshot_objects", objects)
    monkeypatch.setattr(console, "object_review_bindings", bindings)
    monkeypatch.setattr(console, "review_source_fragments", fragments)
    monkeypatch.setattr(readiness_module, "source_accountability", source)

    console.publication_readiness(snapshot_id)

    assert counts == {"objects": 1, "bindings": 1, "fragments": 1, "source": 1}
