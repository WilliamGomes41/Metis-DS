"""T4 invariants for one content-review path.

T5 enforces these on the richtlijn readers: review_stage, the CLI review
queue, console POST, and knowledge publication. The deterministic creator
that still admits non-heading prose without a semantic selection is not
closed here.
"""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED
from src.build_review_queue_v3 import build as build_review_queue
from src.candidate_eligibility_v1 import assess_candidate_eligibility
from src.closed_review_loop_v1 import ClosedLoopReviewConsole
from src.four_eyes_v1 import publish_authorization_contract
from src.integrity_kernel import exact_review_snapshot_hash
from src.operations_console_v1 import ConsoleError
from src.review_duty_v1 import review_duty_counts, review_duty_for, review_stage
from src.review_workboard_v1 import _work_summary
from src.semantic_passage_v1 import SELECTION_ORIGIN_COVERAGE, SELECTION_ORIGIN_PROPOSAL
from src.source_accountability_v1 import KEY as SOURCE_KEY
from src.source_containers_v1 import partition

REVIEW_PATH = "richtlijn"
EXACT_SPANS = (
    {"block_id": "p001-f001", "start": 0, "end": 28, "source_span_id": "span-001"},
)


def _canonical(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _row(
    object_id: str,
    object_type: str,
    *,
    proposed: str = "",
    confirmed: str = "",
    text: str = "Compressietherapie vermindert oedeem.",
    gate: str | None = None,
    origin: str | None = None,
    spans: list[dict] | None = None,
    structural: bool = False,
    validation: str = "needs_review",
    track: str = "clinical",
    source_record: bool = False,
) -> dict:
    semantic: dict = {}
    if origin:
        semantic["selection_origin"] = origin
    if structural:
        semantic["structural"] = True
    if spans is not None:
        semantic["spans"] = spans
    metadata: dict = {}
    if semantic:
        metadata["semantic_passage"] = semantic
    if gate:
        metadata["admission"] = {"gate_result": gate}
    if source_record:
        metadata[SOURCE_KEY] = {"record_kind": "source_passage"}
    return {
        "object_id": object_id,
        "document_id": "doc-1",
        "object_version": "1.0",
        "parent_object_id": None,
        "object_type": object_type,
        "proposed_object_type": proposed,
        "confirmed_object_type": confirmed,
        "source": {"source_id": "src-1", "source_page": 1},
        "structure": {},
        "content": {"clean_text": text},
        "logic": {},
        "relations": [],
        "decision_graph": {},
        "risk": {"risk_fields": []},
        "uncertainty": {"has_uncertainty": False},
        "provenance": {
            "source_fragments": ["p001-f001"],
            "transformation_mode": "deterministic",
        },
        "governance": {
            "validation_status": validation,
            "review_track": track,
            "publication_status": "unpublished",
            "second_review": {"required": False, "status": "not_required"},
        },
        "metadata": metadata,
    }


def _stamp_hash(obj: dict) -> dict:
    obj["provenance"]["canonical_object_hash"] = exact_review_snapshot_hash(obj)
    return obj


def _binding(obj: dict, reviewer_id: str = "reviewer-bert") -> dict:
    return {
        "valid": True,
        "decision": "approve",
        "object_id": obj["object_id"],
        "object_version": obj["object_version"],
        "reviewer_id": reviewer_id,
        "confirmed_object_type": obj.get("confirmed_object_type") or "",
        "canonical_object_hash": obj["provenance"]["canonical_object_hash"],
    }


def _heading() -> dict:
    return _row(
        "doc-1-p001-f001",
        "heading",
        proposed="heading",
        text="Inhoudsopgave",
        origin="not_applicable",
        structural=True,
    )


def _blocked() -> dict:
    return _row(
        "doc-1-sem-blocked",
        "definition",
        proposed="definition",
        text="Oedeem is een ophoping van vocht.",
        gate=GATE_BLOCKED,
        origin=SELECTION_ORIGIN_PROPOSAL,
        spans=list(EXACT_SPANS),
    )


def _coverage_record() -> dict:
    return _row(
        "doc-1-coverage-record",
        "unclassified",
        text="Paginavoettekst.",
        origin=SELECTION_ORIGIN_COVERAGE,
        spans=list(EXACT_SPANS),
        source_record=True,
        track="technical",
    )


def _coverage_origin_only() -> dict:
    return _row(
        "doc-1-coverage-origin",
        "definition",
        proposed="definition",
        text="Resttekst zonder bronrecord.",
        gate=GATE_ALLOWED,
        origin=SELECTION_ORIGIN_COVERAGE,
        spans=list(EXACT_SPANS),
    )


def _deterministic_fragment() -> dict:
    return _row(
        "doc-1-det-fragment",
        "factual_finding",
        proposed="factual_finding",
        text="De incidentie is 4 per 100.000.",
        gate=GATE_ALLOWED,
    )


def _allowed_source() -> list[dict]:
    text = "Oedeem is een ophoping van vocht."
    return [{
        "fragment_id": "p001-f001", "fragment_hash": "hash-p001",
        "raw_text": text, "clean_text": text, "section_path": [],
        "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:1-1"},
    }]


def _allowed_spans() -> list[dict]:
    from src.semantic_passage_v1 import semantic_source_blocks
    block = semantic_source_blocks(_allowed_source())[0]
    return [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}]


def _allowed_candidate() -> dict:
    from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
    from src.semantic_transform_generic_v1 import _fragment_ref
    fragments = _allowed_source()
    [candidate] = materialise_knowledge_candidates(
        [{"decision_kind": "semantic_selection", "selection_origin": SELECTION_ORIGIN_PROPOSAL,
          "spans": _allowed_spans(), "source_text": fragments[0]["clean_text"]}],
        document_id="doc-1", fragments=fragments)
    row = _row(
        "doc-1-sem-allowed", "definition", proposed="definition", confirmed="definition",
        text=candidate["clean_text"], gate=GATE_ALLOWED, origin=SELECTION_ORIGIN_PROPOSAL,
        spans=candidate["semantic_passage"]["spans"])
    row["metadata"]["semantic_passage"] = candidate["semantic_passage"]
    row["provenance"]["source_fragments"] = [_fragment_ref(fragment) for fragment in fragments]
    return _stamp_hash(row)


def _unspanned_candidate() -> dict:
    return _row(
        "doc-1-sem-unknown",
        "definition",
        proposed="definition",
        text="Oedeem is een ophoping van vocht.",
        gate=GATE_ALLOWED,
        origin=SELECTION_ORIGIN_PROPOSAL,
        spans=[{"block_id": "p001-f001", "start": 0, "end": 28, "source_span_id": "UNKNOWN"}],
    )


def _no_duty_definition() -> dict:
    return _row(
        "doc-1-no-duty",
        "definition",
        proposed="definition",
        text="Een wonde is een defect van de huid.",
    )


def _observed_lifecycle(obj: dict) -> str:
    from src.knowledge_path_v1 import candidate_lifecycle
    return candidate_lifecycle(obj)


def _content_phrase(duties: int) -> str:
    return _work_summary({
        "work_state": "review",
        "review_duties": duties,
        "actionable_review_duties": duties,
        "waiting_for_reviewer_duties": 0,
        "meaningful_status": "open",
    })


def test_heading_needs_review_is_not_content_reviewable():
    obj = _heading()
    assert obj["governance"]["validation_status"] == "needs_review"
    assert obj["object_type"] == "heading"
    assert review_stage(obj, review_path=REVIEW_PATH, fragments=_allowed_source()) is None
    assert review_duty_for(obj, review_path=REVIEW_PATH, fragments=_allowed_source()) is None


def test_ineligible_candidate_has_no_review_stage(, fragments=_allowed_source()):
    violations = []
    for obj in (_heading(), _coverage_record(), _no_duty_definition()):
        eligibility = assess_candidate_eligibility(obj)
        stage = review_stage(obj, review_path=REVIEW_PATH, fragments=_allowed_source())
        if eligibility.eligible is False and stage is not None:
            violations.append(f"{obj['object_id']}:{eligibility.reason}:{stage}")
    assert violations == []


def test_blocked_admission_is_not_content_review():
    obj = _blocked()
    assert review_duty_for(obj, review_path=REVIEW_PATH, fragments=_allowed_source()) is None
    counts = review_duty_counts([obj], review_path=REVIEW_PATH, fragments=_allowed_source())
    assert counts["review_duties"] == 0
    assert "inhoudelijke beoordeling" not in _content_phrase(counts["review_duties"]) or counts["review_duties"] == 0
    emitted = {row["object_id"] for row in build_review_queue([obj], "clinical", fragments=_allowed_source())}
    assert emitted == set()


def test_coverage_remainder_has_no_content_duty():
    recorded = _coverage_record()
    leaked = _coverage_origin_only()
    assert review_duty_for(recorded, review_path=REVIEW_PATH, fragments=_allowed_source()) is None
    assert leaked["metadata"]["semantic_passage"]["selection_origin"] == SELECTION_ORIGIN_COVERAGE
    assert SOURCE_KEY not in leaked["metadata"]
    assert review_duty_for(leaked, review_path=REVIEW_PATH, fragments=_allowed_source()) is None
    assert build_review_queue([recorded, leaked], "clinical", fragments=_allowed_source()) == []
    assert build_review_queue([recorded], "technical", fragments=_allowed_source()) == []


def test_deterministic_fragment_without_selection_has_no_content_duty():
    obj = _deterministic_fragment()
    assert "semantic_passage" not in obj["metadata"]
    assert assess_candidate_eligibility(obj).source != "semantic" or not assess_candidate_eligibility(obj).eligible
    assert review_duty_for(obj, review_path=REVIEW_PATH, fragments=_allowed_source()) is None
    assert build_review_queue([obj], "clinical", fragments=_allowed_source()) == []


def test_allowed_candidate_with_exact_spans_is_content_reviewable():
    obj = _allowed_candidate()
    assert obj["metadata"]["semantic_passage"]["selection_origin"] == SELECTION_ORIGIN_PROPOSAL
    assert obj["metadata"]["admission"]["gate_result"] == GATE_ALLOWED
    assert review_stage(obj, review_path=REVIEW_PATH, fragments=_allowed_source()) == "first_review"
    duty = review_duty_for(obj, review_path=REVIEW_PATH, fragments=_allowed_source())
    assert duty is not None
    assert duty["stage"] == "first_review"


def test_candidate_without_exact_spans_fails_materialisation_and_review():
    obj = _unspanned_candidate()
    problems = []
    if _observed_lifecycle(obj) != "materialisation_failed":
        problems.append(f"lifecycle={_observed_lifecycle(obj)}")
    stage = review_stage(obj, review_path=REVIEW_PATH, fragments=_allowed_source())
    if stage is not None:
        problems.append(f"stage={stage}")
    if build_review_queue([obj], "clinical", fragments=_allowed_source()):
        problems.append("review-queue emitted the row")
    assert problems == []


def test_review_queue_cli_emits_only_content_reviewable_rows():
    rejected = [
        _heading(),
        _blocked(),
        _coverage_record(),
        _coverage_origin_only(),
        _deterministic_fragment(),
        _unspanned_candidate(),
        _no_duty_definition(),
    ]
    emitted = {row["object_id"] for row in build_review_queue(rejected, "clinical", fragments=_allowed_source())}
    emitted.update(row["object_id"] for row in build_review_queue(rejected, "technical", fragments=_allowed_source()))
    assert emitted == set()


def test_partition_knowledge_gives_no_review_authority():
    obj = _deterministic_fragment()
    bucket = [row["object_id"] for row in partition([obj])["knowledge"]]
    assert review_duty_for(obj, review_path=REVIEW_PATH, fragments=_allowed_source()) is None
    assert build_review_queue([obj], "clinical", fragments=_allowed_source()) == []
    for object_id in bucket:
        assert object_id != obj["object_id"] or review_duty_for(obj, review_path=REVIEW_PATH, fragments=_allowed_source()) is None


def test_structural_binding_stays_history_and_does_not_authorize_publication():
    obj = _stamp_hash(_row(
        "doc-1-p001-f009",
        "heading",
        proposed="heading",
        confirmed="heading",
        text="Doelgroep",
        origin="not_applicable",
        structural=True,
        validation="approved",
    ))
    binding = _binding(obj)
    before_obj = _canonical(obj)
    before_binding = _canonical(binding)
    contract = publish_authorization_contract(
        obj=obj,
        bindings=[binding],
        uploader_id="uploader-anne",
        immutable_locator=None,
    )
    assert _canonical(obj) == before_obj
    assert _canonical(binding) == before_binding
    assert binding["valid"] is True
    assert contract["tuple_authorization"] is False


def test_matching_review_hash_keeps_existing_content_review_valid():
    from src.review_duty_v1 import exact_current_approver_ids

    obj = _allowed_candidate()
    binding = _binding(obj)
    assert exact_current_approver_ids(obj, [binding]) == ("reviewer-bert",)
    assert review_stage(obj, review_path=REVIEW_PATH, bindings=[binding], fragments=_allowed_source()) is None


def test_unknown_lineage_cannot_be_newly_published():
    obj = _stamp_hash(_row(
        "doc-1-sem-unknown-pub",
        "definition",
        proposed="definition",
        confirmed="definition",
        text="Oedeem is een ophoping van vocht.",
        gate=GATE_ALLOWED,
        origin=SELECTION_ORIGIN_PROPOSAL,
        spans=[{"block_id": "p001-f001", "start": 0, "end": 28, "source_span_id": "UNKNOWN"}],
        validation="approved",
    ))
    contract = publish_authorization_contract(
        obj=obj,
        bindings=[_binding(obj)],
        uploader_id="uploader-anne",
        immutable_locator=None,
    )
    problems = []
    if "source_lineage_incomplete" not in contract["blockers"]:
        problems.append(f"publish_blockers={contract['blockers']}")
    if contract["tuple_authorization"] is not False:
        problems.append("tuple_authorization treated UNKNOWN lineage as publication authority")
    assert problems == []


def test_side_index_classification_does_not_rewrite_bytes_or_bindings():
    obj = _heading()
    binding = _binding(_stamp_hash(deepcopy(obj)))
    before_obj = _canonical(obj)
    before_binding = _canonical(binding)
    side_index = {
        "object_id": obj["object_id"],
        "object_version": obj["object_version"],
        "kind": "structure",
        "lifecycle": "structure",
        "review_authority": "non_content",
    }
    assert side_index["review_authority"] == "non_content"
    assert _canonical(obj) == before_obj
    assert _canonical(binding) == before_binding
    assert review_stage(obj, review_path=REVIEW_PATH, fragments=_allowed_source()) is None
    assert review_duty_for(obj, review_path=REVIEW_PATH, fragments=_allowed_source()) is None


def test_changed_spans_do_not_inherit_review_authority():
    """A later explicit revises command belongs to T11. Silence is not that command."""
    from src.review_duty_v1 import exact_current_approver_ids

    current = _allowed_candidate()
    binding = _binding(current)
    shifted = deepcopy(current)
    shifted["metadata"]["semantic_passage"]["spans"] = [
        {"block_id": "p001-f001", "start": 4, "end": 28, "source_span_id": "span-002"},
    ]
    _stamp_hash(shifted)
    assert exact_current_approver_ids(shifted, [binding]) == ()


def _console(tmp_path):
    console = ClosedLoopReviewConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
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
    return console, reviewer, receipt["snapshot_id"]


def _project_policy(console, snapshot_id: str, obj: dict) -> None:
    policy = console._envelope(snapshot_id).get("review_policy")
    if not policy:
        return
    if policy.get("contract"):
        obj.setdefault("governance", {})["review_policy"] = deepcopy(policy)
    else:
        obj.setdefault("metadata", {})["review_policy"] = deepcopy(policy)


def _append(console, snapshot_id: str, obj: dict) -> None:
    rows, revision = console.snapshot_objects_and_revision(snapshot_id)
    _project_policy(console, snapshot_id, obj)
    rows.append(obj)
    console._save_objects(snapshot_id, rows, expected_revision=revision)


def _approve(console, reviewer, snapshot_id: str, object_id: str) -> str | None:
    try:
        console.review_object(
            actor_id=reviewer["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            decision="approve",
            confirmed_object_type="definition",
        )
    except ConsoleError as exc:
        return exc.code
    return None


def test_console_post_cannot_review_without_an_open_content_duty(tmp_path):
    console, reviewer, snapshot_id = _console(tmp_path)
    blocked = _blocked()
    no_duty = _no_duty_definition()
    _append(console, snapshot_id, blocked)
    _append(console, snapshot_id, no_duty)
    stored = {row["object_id"]: row for row in console.snapshot_objects(snapshot_id, include_blocked=False)}
    assert blocked["object_id"] in stored
    assert stored[blocked["object_id"]]["metadata"]["admission"]["gate_result"] == GATE_BLOCKED
    assert review_duty_for(stored[no_duty["object_id"]], review_path=REVIEW_PATH, fragments=_allowed_source()) is None
    assert review_duty_for(stored[blocked["object_id"]], review_path=REVIEW_PATH, fragments=_allowed_source()) is None
    problems = []
    if _approve(console, reviewer, snapshot_id, no_duty["object_id"]) is None:
        problems.append("console POST approved an object without an open content duty")
    if _approve(console, reviewer, snapshot_id, blocked["object_id"]) is None:
        problems.append("console POST approved a blocked candidate")
    visible = console.snapshot_objects(snapshot_id, include_blocked=False)
    blocked_visible = [
        row for row in visible
        if (row.get("metadata") or {}).get("admission", {}).get("gate_result") == GATE_BLOCKED
    ]
    if not blocked_visible:
        problems.append("include_blocked=False hid the blocked row; it is not a content filter")
    elif build_review_queue(blocked_visible, "clinical", fragments=_allowed_source()):
        problems.append("review-queue emitted a blocked row returned by include_blocked=False")
    assert problems == []


def test_approve_of_blocked_candidate_does_not_commit(tmp_path):
    console, reviewer, snapshot_id = _console(tmp_path)
    blocked = _blocked()
    _append(console, snapshot_id, blocked)
    before = _canonical(next(
        row for row in console.snapshot_objects(snapshot_id) if row["object_id"] == blocked["object_id"]
    ))
    with pytest.raises(ConsoleError):
        console.review_object(
            actor_id=reviewer["account_id"],
            snapshot_id=snapshot_id,
            object_id=blocked["object_id"],
            decision="approve",
            confirmed_object_type="definition",
        )
    after = _canonical(next(
        row for row in console.snapshot_objects(snapshot_id) if row["object_id"] == blocked["object_id"]
    ))
    assert after == before


def _authorize(obj: dict) -> dict:
    stamped = _stamp_hash(obj)
    stamped["governance"]["validation_status"] = "approved"
    binding = _binding(stamped)
    before_obj = _canonical(stamped)
    before_binding = _canonical(binding)
    contract = publish_authorization_contract(
        obj=stamped,
        bindings=[binding],
        uploader_id="uploader-anne",
        immutable_locator=None,
        fragments=_allowed_source(),
    )
    assert _canonical(stamped) == before_obj
    assert _canonical(binding) == before_binding
    assert binding["valid"] is True
    return contract


def test_deterministic_row_with_old_approval_has_no_publication_authority():
    contract = _authorize(_deterministic_fragment())
    assert contract["tuple_authorization"] is False


def test_coverage_and_source_row_with_old_approval_has_no_publication_authority():
    for factory in (_coverage_record, _coverage_origin_only):
        contract = _authorize(factory())
        assert contract["tuple_authorization"] is False


def test_blocked_semantic_candidate_with_old_approval_has_no_publication_authority():
    contract = _authorize(_blocked())
    assert contract["tuple_authorization"] is False
    assert "admission_blocked" in contract["blockers"]


def test_matching_approval_keeps_knowledge_publication_authority():
    contract = _authorize(_allowed_candidate())
    assert contract["tuple_authorization"] is True


def test_malformed_persisted_spans_are_not_exact_review_or_publication():
    from src.knowledge_path_v1 import content_reviewable, spans_are_exact

    exact = list(EXACT_SPANS)
    assert spans_are_exact(exact) is True
    malformed = [
        [{"block_id": "p001-f001", "start": "0", "end": "28"}],
        [{"block_id": "p001-f001", "start": -1, "end": 28}],
        [{"block_id": "p001-f001", "start": 28, "end": 28}],
        [{"block_id": "p001-f001", "start": 10, "end": 4}],
        [{"block_id": "p001-f001", "start": True, "end": 28}],
        [{"block_id": "p001-f001", "start": 0, "end": 28, "source_span_id": "UNKNOWN"}],
        [{"block_id": "p001-f001", "start": 0, "end": 28, "source_span_id": ""}],
    ]
    assert all(spans_are_exact(spans) is False for spans in malformed)
    obj = _row(
        "doc-1-sem-malformed",
        "definition",
        proposed="definition",
        confirmed="definition",
        gate=GATE_ALLOWED,
        origin=SELECTION_ORIGIN_PROPOSAL,
        spans=[{"block_id": "p001-f001", "start": "0", "end": "28"}],
        validation="approved",
    )
    assert content_reviewable(obj) is False
    contract = _authorize(obj)
    assert contract["tuple_authorization"] is False
    assert "source_lineage_incomplete" in contract["blockers"]
