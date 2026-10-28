"""Full HTML/error snapshots of the current review-room orchestration.

CI supplies a native PostgreSQL 16 service for these production-composition
proofs. Exact snapshots and the recorded review mutation remain the oracle.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.integrity_kernel import compute_canonical_object_hash, stamp_canonical_hashes
from src.operations_console_v1 import ConsoleError
from src.review.proportionate_review_v1 import ProportionateReviewConsole
from src.publication.publish_authorization_v1 import tuple_record
from tests.semantic_fixture_support import install_fixture_history

from .support import ACTOR, OTHER, REVIEWER, command, console_at, select_literal

CASES = ["empty", "documents", "unknown_document", "index", "proportionate_index", "history_index", "history_no_reader",
         "history_detail", "batch", "batch_selected", "provided_snapshot", "unknown_object", "heading",
         "content", "outsider", "non_reviewer", "published", "context_source", "context_saved",
         "source_conflict", "source_conflict_empty_draft", "partial_one", "partial_many",
         "second_actionable", "second_same_reviewer", "explicit_second_without_duty", "legacy_bindings"]


@pytest.mark.parametrize("case", CASES)
def test_review_room_golden(case, tmp_path, monkeypatch, golden, production_console):
    import src.operations_console_app as ui

    console = console_at(tmp_path, production_console=production_console)
    account = deepcopy(console._accounts[REVIEWER])
    args = {}
    if case != "empty":
        select_literal(console, "recommendation" if case.startswith("second_") else "definition")
        sid = console.ingest(**command())["snapshot_id"]
        rows = console.snapshot_objects(sid)
        heading = next(r for r in rows if r["object_type"] == "heading")
        content = next(r for r in rows if r["object_type"] not in {"document", "heading"})
        args["document"] = sid
        if case in {"documents", "partial_one", "partial_many"}:
            args.pop("document")
        if case == "unknown_document":
            args["document"] = "missing-document"
        if case.startswith("history"):
            args["task"] = "history"
            if case == "history_detail":
                args["object"] = content["object_id"]
            if case == "history_no_reader":
                monkeypatch.setattr(console, "audit_review_signals", None, raising=False)
            else:
                monkeypatch.setattr(console, "audit_review_signals", lambda: [], raising=False)
        if case.startswith("batch"):
            args["task"] = "batch"
            if case == "batch_selected":
                args["batch_selection"] = [content["object_id"]]
        if case == "provided_snapshot":
            args["snapshot"] = (rows, "provided-revision")
        if case == "unknown_object":
            args["object"] = "missing-object"
        if case == "heading":
            args["object"] = heading["object_id"]
        if case in {"content", "outsider", "non_reviewer", "published", "context_source", "context_saved",
                    "source_conflict", "source_conflict_empty_draft", "second_actionable", "second_same_reviewer",
                    "explicit_second_without_duty", "legacy_bindings"}:
            args["object"] = content["object_id"]
        if case == "outsider":
            account = deepcopy(console._accounts[OTHER])
        if case == "non_reviewer":
            account["roles"] = ["researcher"]
        if case == "published":
            monkeypatch.setattr(console, "snapshot_is_published", lambda _: True)
        if case in {"context_source", "source_conflict", "source_conflict_empty_draft"}:
            args["context_mode"] = "source"
        if case == "context_saved":
            args["context_saved"] = True
        if case.startswith("source_conflict"):
            args.update(conflict=True, draft={"comment": "Bewaar <toelichting>", "proposed_correction": "Bewaar & correctie"}
                        if case == "source_conflict" else {})
        if case.startswith("partial"):
            args.update(conflict=True, batch_completed=1 if case == "partial_one" else 2)
        if case in {"second_actionable", "second_same_reviewer"}:
            target = next(r for r in rows if r["object_id"] == content["object_id"])
            target.update(object_type="recommendation", confirmed_object_type="recommendation")
            target["governance"].update(validation_status="approved", second_review={
                "required": True, "status": "pending", "reviewer": None, "review_date": None, "snapshot_hash": None})
            target["metadata"].setdefault("admission", {})["gate_result"] = "allowed"
            target["risk"] = {"level": "high", "risk_level": "high", "requires_second_review": True,
                              "risk_fields": ["contraindication"]}
            stamp_canonical_hashes(target)
            install_fixture_history(console, sid, rows)
            console._bindings[sid] = [tuple_record(object_id=target["object_id"], object_version=target["object_version"],
                canonical_object_hash=compute_canonical_object_hash(target), confirmed_object_type="recommendation",
                reviewer=REVIEWER, reviewer_id=REVIEWER, decision="approve")]
            console._save_bindings()
            if case == "second_actionable":
                account = deepcopy(console._accounts[OTHER])
        if case == "explicit_second_without_duty":
            args["task"] = "second_review"
        if case == "legacy_bindings":
            def missing(*args, **kwargs):
                raise AttributeError("legacy projection has no bindings")
            monkeypatch.setattr(console, "object_review_bindings", missing)
    before = deepcopy(console._envelopes)
    try:
        result = {"html": ui._render_review_room(console, account, **args)}
    except ConsoleError as error:
        result = {"error": error.code}
    except AttributeError as error:
        # Current compatibility failure is part of the characterization too.
        result = {"exception": type(error).__name__, "message": str(error)}
    assert console._envelopes == before, "Rendering must not mutate envelope state"
    golden("review_room", case, result)
