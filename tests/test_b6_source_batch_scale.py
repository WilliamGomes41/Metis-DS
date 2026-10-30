"""Incident 2026-10-30: batch and group source exclusions on a large PDF stay bounded.

Per member the command used to re-read all objects, re-verify the source bytes and
reopen the whole PDF, inside the write transaction. These tests pin one source
read and one PDF open per command, with the same per-member check.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import time
from copy import deepcopy

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.vorming.source_accountability_v1 import evidence_of, is_source_record
from tests.test_source_accountability_v1 import DEFINITION, proposal

LINES = 200


def _large_pdf(tmp_path, *, production_console):
    import fitz
    state = production_console(processing_binder=lambda console: None, root=tmp_path,
                               source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    author = state.create_account(username="author", password="long-test-password", roles=("researcher",))
    reviewer = state.create_account(username="reviewer", password="long-test-password", roles=("reviewer",))

    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        if not any(DEFINITION in b["text"] for b in data["source_blocks"]):
            answer = {"objects": [], "relations": [], "abstain_reason": "uncertain"}
        else:
            answer = proposal(data, v3=True)
            answer["source_assessments"] = [
                {"span": {"block_id": b["block_id"], "literal": b["text"], "occurrence": 0},
                 "role": "metadata", "reason": "document_metadata"}
                for b in data["source_blocks"] if b["text"].startswith("Colofonregel")]
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer)}]}]}
    bind_pre_review_semantic_processing(state, environ={"METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v3",
        "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "fixture"}, post_json=provider)
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Richtlijn Proef", fontsize=20)
        page.insert_text((72, 110), DEFINITION, fontsize=10)
        for i in range(LINES):
            if i % 30 == 0:
                page, y = pdf.new_page(), 72
            page.insert_text((72, y), f"Colofonregel {i} werkgroep", fontsize=10)
            y += 22
        data = pdf.tobytes()
    sid = state.ingest(actor_id=author["account_id"], filename="proef.pdf", data=data,
        content_type="application/pdf", ingest_kind="new", title="Proef", version="1", date="2026-10-04",
        live_url="", class_="richtlijn", family="proef", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    return state, sid, reviewer["account_id"]


def _metadata_ids(state, sid):
    return [r["object_id"] for r in state.snapshot_objects(sid)
            if is_source_record(r) and evidence_of(r).get("proposed_role") == "metadata"]


def _count_heavy_reads(monkeypatch, state):
    import fitz
    calls = {"fitz_open": 0, "source_bytes": 0, "open_source_passage": 0}
    real_open, real_bytes = fitz.open, state._verified_source_bytes

    def counted_open(*args, **kwargs):
        calls["fitz_open"] += 1
        return real_open(*args, **kwargs)

    def counted_bytes(*args, **kwargs):
        calls["source_bytes"] += 1
        return real_bytes(*args, **kwargs)

    def per_member(*_args, **_kwargs):
        calls["open_source_passage"] += 1
        raise AssertionError("per-member open_source_passage")
    monkeypatch.setattr(fitz, "open", counted_open)
    monkeypatch.setattr(state, "_verified_source_bytes", counted_bytes)
    monkeypatch.setattr(state, "open_source_passage", per_member)
    return calls


def test_batch_exclusion_on_a_large_pdf_reads_the_source_once(tmp_path, monkeypatch, *, production_console):
    from src.publication.publication_readiness_v1 import source_passage_closure
    from src.review.source_context_review_v1 import confirm_source_exclusions
    state, sid, reviewer = _large_pdf(tmp_path, production_console=production_console)
    ids = _metadata_ids(state, sid)
    # The fixture model proposes metadata only in the chunk it forms knowledge in.
    assert len(ids) >= 40 and len([r for r in state.snapshot_objects(sid) if is_source_record(r)]) >= LINES
    calls = _count_heavy_reads(monkeypatch, state)
    started = time.monotonic()
    result = confirm_source_exclusions(state, actor_id=reviewer, snapshot_id=sid, source_object_ids=ids,
        reason="Colofon, geen kennis.", command_id="batch-scale", expected_revision=state.objects_revision(sid))
    elapsed = time.monotonic() - started
    assert len(result["source_versions"]) == len(ids)
    # Independent of the number of members: one source read, one open for the
    # checks and at most one for the existing fragment read.
    assert calls["source_bytes"] == 1 and calls["fitz_open"] <= 2 and calls["open_source_passage"] == 0
    assert elapsed < 60, elapsed
    unresolved = set(source_passage_closure(state.snapshot_objects(sid))["unresolved_source_passage_ids"])
    assert not unresolved & set(ids)


def test_group_confirmation_reads_the_source_once(tmp_path, monkeypatch, *, production_console):
    from src.review.source_context_review_v1 import confirm_source_group, group_members_hash, source_group_candidates
    state, sid, reviewer = _large_pdf(tmp_path, production_console=production_console)
    (path, reason), rows = max(source_group_candidates(state.snapshot_objects(sid)).items(), key=lambda kv: len(kv[1]))
    rows = rows[:50]
    assert len(rows) >= 2
    calls = _count_heavy_reads(monkeypatch, state)
    result = confirm_source_group(state, actor_id=reviewer, snapshot_id=sid, section_path=list(path),
        group_reason=reason, shown_object_ids=[r["object_id"] for r in rows],
        source_object_ids=[r["object_id"] for r in rows], members_hash=group_members_hash(rows),
        reason="Geen op te nemen kennis.", command_id="group-scale", expected_revision=state.objects_revision(sid))
    assert len(result["members"]) == len(rows)
    assert calls["source_bytes"] == 1 and calls["fitz_open"] <= 2 and calls["open_source_passage"] == 0


def test_shared_reader_gives_the_single_check_result_for_every_record(tmp_path, *, production_console):
    """Same passage per record, and the same refusal for a record that cannot be opened."""
    state, sid, _reviewer = _large_pdf(tmp_path, production_console=production_console)
    envelope = state._envelope(sid)
    _path, freeze_bytes = state._verified_source_bytes(envelope)
    records = [r for r in state.snapshot_objects(sid) if is_source_record(r)]
    with state._open_original_reader(envelope, freeze_bytes) as require:
        for record in records:
            assert require(record) == state._require_open_original(sid, record["object_id"])
        broken = deepcopy(records[0])
        for bag in (broken, broken.get("provenance") or {}):
            bag.pop("source_locator", None)
            bag.pop("source_fragments", None)
        broken.setdefault("source", {}).pop("source_locator", None)
        with pytest.raises(ConsoleError) as refused:
            require(broken)
        assert refused.value.code == "open_original_required"
