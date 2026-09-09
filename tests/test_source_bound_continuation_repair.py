"""Brongebonden herstel zonder automatische inhoudelijke goedkeuring.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.admission_gate_v1 import (
    GATE_ALLOWED,
    GATE_BLOCKED,
    admission_of,
    admit_candidate,
    apply_admission_gate,
    build_candidate_record,
)
from src.context_scan_v1 import propose_expand_merge
from src.integrity_kernel import stamp_canonical_hashes
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole
from src.object_taxonomy_v1 import has_terminal_sentence_boundary, is_truncated_sentence


pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_beschikbaarheid,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


FIRST = (
    "De werkgroep adviseert gepast gebruik te maken van een betrouwbare en goed "
    "gevalideerde eenzaamheidsschaal om een indicatie te krijgen van de ernst van "
    "de eenzaamheid. De werkgroep is van mening dat voor dit doel de de Jong "
    "Gierveld 6-item"
)
CONTINUATION = "versie voor wijkverpleegkundigen het meest geschikte instrument is."
MERGED = f"{FIRST} {CONTINUATION}"


def _console(tmp_path: Path) -> tuple[OperationsConsole, dict, dict]:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    researcher = console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher",),
        display_name="Anne Onderzoeker",
    )
    reviewer = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    return console, researcher, reviewer


def _split_existing_object(console: OperationsConsole, snapshot_id: str) -> str:
    rows = console.snapshot_objects(snapshot_id, for_update=True)
    index = next(
        i
        for i, row in enumerate(rows)
        if CONTINUATION in str((row.get("content") or {}).get("clean_text") or "")
        and len((row.get("provenance") or {}).get("source_fragments") or []) >= 2
    )
    original = rows[index]
    refs = list((original.get("provenance") or {}).get("source_fragments") or [])
    assert len(refs) >= 2

    first = deepcopy(original)
    first["content"]["clean_text"] = FIRST
    first["content"]["raw_text"] = FIRST
    first["provenance"]["source_fragments"] = [refs[0]]
    first["governance"]["validation_status"] = "needs_review"
    stamp_canonical_hashes(first)

    continuation = deepcopy(original)
    continuation["object_id"] = f"{original['object_id']}-continuation"
    continuation["content"]["clean_text"] = CONTINUATION
    continuation["content"]["raw_text"] = CONTINUATION
    continuation["provenance"]["source_fragments"] = [refs[1]]
    continuation["object_type"] = "unclassified"
    continuation.pop("confirmed_object_type", None)
    continuation["governance"]["validation_status"] = "needs_review"
    stamp_canonical_hashes(continuation)

    rows[index : index + 1] = [first, continuation]
    envelope = console._envelope(snapshot_id)
    rows = apply_admission_gate(
        rows,
        klasse=envelope["class"],
        document_version=envelope["version"],
        source_hash=envelope["sha256"],
    )
    for row in rows:
        stamp_canonical_hashes(row)
    console._save_objects(snapshot_id, rows)
    return str(first["object_id"])


def test_proposal_uses_only_literal_adjacent_sentence() -> None:
    proposal = propose_expand_merge(
        candidate_paragraph=FIRST,
        next_paragraph=f"{CONTINUATION} Een nieuwe zelfstandige zin.",
    )
    assert proposal == {
        "performed": True,
        "merged_text": MERGED,
        "parts": [FIRST, CONTINUATION],
        "kind": "sentence_continuation",
        "source_bound": True,
        "direction": "next",
    }
    assert propose_expand_merge(
        candidate_paragraph=FIRST,
        next_paragraph="Deze passage begint als een nieuwe zelfstandige zin.",
    )["performed"] is False


def test_open_sentence_is_always_blocked_when_no_safe_continuation_exists() -> None:
    open_text = "De werkgroep adviseert de gevalideerde schaal te gebruiken"
    fields = dict(
        candidate_id="cand-open-sentence",
        document_id="doc-complete-sentence",
        document_version="1.0",
        source_hash="a" * 64,
        section_path=["Aanbevelingen"],
        source_locator_start="lines:1-1",
        source_locator_end="lines:1-1",
        source_text_exact=open_text,
        candidate_text=open_text,
        subject_span="De werkgroep",
        predicate_span="adviseert",
        proposed_type="recommendation",
        type_evidence_spans=["adviseert"],
        context_before="",
        context_after="Deze tekst begint aantoonbaar als een nieuwe zin.",
        actor_of_scope="De werkgroep",
        recommended_action="te gebruiken",
        action_object_or_goal="de gevalideerde schaal",
        recommendation_evidence_span=open_text,
    )
    blocked = admit_candidate(build_candidate_record(**fields))
    assert blocked["gate_result"] == GATE_BLOCKED
    assert "incomplete_sentence" in blocked["reason_codes"]
    assert blocked["expand_merge"]["performed"] is False

    complete_text = f"{open_text}."
    fields.update(source_text_exact=complete_text, candidate_text=complete_text)
    allowed = admit_candidate(build_candidate_record(**fields))
    assert allowed["gate_result"] == GATE_ALLOWED
    assert "incomplete_sentence" not in allowed["reason_codes"]


def test_sentence_boundary_rule_covers_the_reported_break() -> None:
    assert has_terminal_sentence_boundary(FIRST) is False
    assert is_truncated_sentence(FIRST) is True
    assert has_terminal_sentence_boundary(MERGED) is True
    assert is_truncated_sentence(MERGED) is False


def test_reviewer_can_create_new_version_from_literal_source_context(tmp_path: Path) -> None:
    console, researcher, reviewer = _console(tmp_path)
    source = f"<html><body><h1>Eenzaamheid</h1><p>{FIRST}</p><p>{CONTINUATION}</p></body></html>"
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="eenzaamheid.html",
        data=source.encode("utf-8"),
        content_type="text/html",
        ingest_kind="new",
        title="Eenzaamheid",
        version="1.0",
        date="2026-09-09",
        live_url="",
        class_="richtlijn",
        family="eenzaamheid",
        named_reviewers=[reviewer["account_id"]],
    )
    snapshot_id = receipt["snapshot_id"]
    initial = console.snapshot_objects(snapshot_id)
    initial_texts = [str((row.get("content") or {}).get("clean_text") or "") for row in initial]
    assert any("Jong Gierveld 6-item versie voor wijkverpleegkundigen" in text for text in initial_texts)
    assert not any(text.endswith("Jong Gierveld 6-item") for text in initial_texts)
    object_id = _split_existing_object(console, snapshot_id)
    target = next(row for row in console.snapshot_objects(snapshot_id) if row["object_id"] == object_id)
    assert admission_of(target)["gate_result"] == GATE_BLOCKED
    assert "incomplete_sentence" in admission_of(target)["reason_codes"]

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    page = client.get(f"/review?document={snapshot_id}&object={object_id}")
    assert page.status_code == 200
    assert "Metis heeft waarschijnlijk een afgebroken zin gevonden" in page.text
    assert "Ontbrekende brontekst:" in page.text
    assert CONTINUATION in page.text
    assert "Passage aanvullen met brontekst" in page.text
    assert "voegt alleen de letterlijk aangetroffen vervolgregel toe" in page.text

    stale_revision = console.objects_revision(snapshot_id)
    rows = console._load_objects(snapshot_id)
    continuation = next(row for row in rows if row["object_id"].endswith("-continuation"))
    continuation["structure"]["sequence"] += 1
    stamp_canonical_hashes(continuation)
    console._save_objects(snapshot_id, rows)
    stale = client.post(
        "/review/context/accept",
        data={
            "snapshot_id": snapshot_id,
            "object_id": object_id,
            "snapshot_revision": stale_revision,
        },
        follow_redirects=False,
    )
    assert stale.status_code == 400
    assert "snapshot_object_write_conflict" in stale.text
    unchanged = next(row for row in console.snapshot_objects(snapshot_id) if row["object_id"] == object_id)
    assert unchanged["object_version"] == target["object_version"]

    response = client.post(
        "/review/context/accept",
        data={
            "snapshot_id": snapshot_id,
            "object_id": object_id,
            "snapshot_revision": console.objects_revision(snapshot_id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    revised = next(row for row in console.snapshot_objects(snapshot_id) if row["object_id"] == object_id)
    assert revised["object_version"] != target["object_version"]
    assert revised["content"]["clean_text"] == MERGED
    assert revised["content"]["raw_text"] == MERGED
    assert revised["governance"]["validation_status"] == "needs_review"
    assert revised["governance"]["publication_status"] == "unpublished"
    assert len(revised["provenance"]["source_fragments"]) == 2
    assert revised["provenance"]["previous_object_version"] == target["object_version"]
