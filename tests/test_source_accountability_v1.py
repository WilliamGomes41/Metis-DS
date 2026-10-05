"""Source accountability is not candidate review or automatic exclusion.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from copy import deepcopy

import pytest

from src.operations_console_v1 import ConsoleError
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing, semantic_spec_from_fragments
from src.publication_readiness_v1 import source_passage_closure
from src.review_closure_v1 import ReviewClosureConsole
from src.review_duty_v1 import review_duty_for
from src.source_accountability_v1 import KEY, evidence_of, validate_assessments
from src.source_bound_fields_v2 import FIELDS
from src.source_context_review_v1 import confirm_source_exclusions
from tests.test_workflow_chain_recovery_v1 import recovery_postgres  # noqa: F401

DEFINITION = "Een observatie is een systematische waarneming van gedrag."
CONDITION = "Bij verslechtering is extra observatie nodig."


def proposal(data, *, v3=False, supplemental=False):
    blocks = data["source_blocks"]
    if v3:
        from src.source_bound_fields_v3 import FIELDS as fields
    else:
        fields = FIELDS
    target = next(b for b in blocks if DEFINITION in b["text"])
    def ref(text, owner=target):
        return {"block_id": owner["block_id"], "literal": text, "occurrence": 0}
    evidence = {f: {"span": None, "missing_reason": "not_applicable"} for f in fields}
    for f, literal in {"subject_span": "Een observatie", "predicate_span": "is",
            "type_evidence_spans": "is een", "defined_term": "observatie",
            "definiens_span": "een systematische waarneming van gedrag"}.items():
        evidence[f] = {"span": ref(literal), "missing_reason": None}
    assessments = [{"span": ref(b["text"], b), "role": "metadata", "reason": "document_metadata"}
                   for b in blocks if b["text"] in {"Versie: 1", "Datum: juli 2026"}]
    return {"objects": [{"spans": [ref(DEFINITION)], "proposed_object_type": "definition",
             "recommendation_semantics": None, "field_evidence": evidence, "context_evidence": []}],
            "source_assessments": assessments, "relations": [], "abstain_reason": None}


def system(tmp_path, console=None):
    state = console or ReviewClosureConsole(root=tmp_path, source_store=tmp_path/"sources", runtime=tmp_path/"runtime")
    author = state.create_account(username="author", password="long-test-password", roles=("researcher",))
    reviewer = state.create_account(username="reviewer", password="long-test-password", roles=("reviewer",))
    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal(data))}]}]}
    bind_pre_review_semantic_processing(state, environ={"METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v2",
        "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "fixture"}, post_json=provider)
    data = ("<html><body><h1>Observatie</h1><p>Versie: 1</p><p>Datum: juli 2026</p>"
            f"<p>{DEFINITION}</p><p>{CONDITION}</p></body></html>").encode()
    receipt = state.ingest(actor_id=author["account_id"], filename="source.html", data=data, content_type="text/html",
        ingest_kind="new", title="Observatie", version="1", date="2026-10-04", live_url="",
        class_="richtlijn", family="observatie", named_reviewers=[reviewer["account_id"]])
    sid = receipt["snapshot_id"]
    rows = state.snapshot_objects(sid)
    metadata = [r for r in rows if evidence_of(r).get("proposed_role") == "metadata"]
    command = dict(actor_id=reviewer["account_id"], snapshot_id=sid,
        source_object_ids=[r["object_id"] for r in metadata], reason="Documentversie en datum, geen inhoudelijke kennis.",
        command_id="metadata-1", expected_revision=state.objects_revision(sid))
    return state, rows, command


def test_metadata_batch_preserves_unselected_condition_history_and_restart(tmp_path):
    state, before, command = system(tmp_path)
    source = [r for r in before if KEY in (r.get("metadata") or {})]
    assert len(source) == 3
    assert all(r["governance"]["review_track"] == "technical" for r in source)
    assert all(review_duty_for(r, review_path="richtlijn", bindings=None) is None for r in source)
    assert not source_passage_closure(before)["source_passage_review_complete"]
    from src.operations_console_app import _render_review_index
    page = _render_review_index(command["snapshot_id"], before, "richtlijn",
        snapshot_revision=command["expected_revision"], task="inventory")
    assert 'data-source-accountability' in page and '/review/source-exclusions' in page
    assert 'data-source-record' in page and CONDITION in page
    definition = next(r for r in before if r.get("proposed_object_type") == "definition")
    assert definition["metadata"]["admission"]["gate_result"] == "allowed"
    assert f'data-passage-id="{definition["object_id"]}"' in page
    assert f'data-source-record="{definition["object_id"]}"' not in page
    result = confirm_source_exclusions(state, **command)
    assert len(result["source_versions"]) == 2
    current = state.snapshot_objects(command["snapshot_id"])
    condition = next(r for r in current if (r.get("content") or {}).get("clean_text") == CONDITION)
    assert condition["object_id"] in source_passage_closure(current)["unresolved_source_passage_ids"]
    for row in current:
        if row["object_id"] in result["source_versions"]:
            assert row["metadata"]["passage_register"]["status"] == "excluded_with_reason"
            assert row["governance"]["validation_status"] == "rejected"
            assert row["governance"]["publication_status"] == "unpublished"
    assert all(row in state._load_objects(command["snapshot_id"], remember=False) for row in before)
    restarted = ReviewClosureConsole(root=tmp_path, source_store=tmp_path/"sources", runtime=tmp_path/"runtime")
    assert restarted.snapshot_objects(command["snapshot_id"]) == current
    assert confirm_source_exclusions(restarted, **command)["idempotent"] is True


def test_source_records_cannot_be_approved_or_distributed_as_knowledge(tmp_path):
    state, rows, command = system(tmp_path)
    source = next(r for r in rows if r["object_id"] in command["source_object_ids"])
    with pytest.raises(ConsoleError, match="source_context_not_knowledge"):
        state.review_object(actor_id=command["actor_id"], snapshot_id=command["snapshot_id"],
            object_id=source["object_id"], decision="approve", confirmed_object_type="definition")
    from tests.test_retrieval_projection_v2 import published_envelope
    from src.retrieval.retrieval_projection_v2 import build_projection
    from src.integrity_kernel import stamp_canonical_hashes
    tampered = deepcopy(source)
    tampered["confirmed_object_type"] = "definition"
    env = published_envelope(tampered)
    stamp_canonical_hashes(env["knowledge_object"])
    records, blocked = build_projection([env])
    assert records == []
    assert "source_context_not_knowledge" in blocked[0]["errors"]


def test_http_source_batch_requires_named_reviewer_and_explicit_confirmation(tmp_path):
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app
    state, before, command = system(tmp_path)
    with TestClient(create_console_app(state), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "reviewer", "password": "long-test-password"},
                           follow_redirects=False).status_code == 303
        data = {"snapshot_id": command["snapshot_id"], "source_object_ids": command["source_object_ids"],
                "reason": command["reason"], "command_id": command["command_id"],
                "snapshot_revision": command["expected_revision"]}
        assert client.post("/review/source-exclusions", data=data).status_code == 400
        assert state.snapshot_objects(command["snapshot_id"]) == before
        response = client.post("/review/source-exclusions", data={**data, "source_checked": "1"}, follow_redirects=False)
        assert response.status_code == 303, response.text


def test_native_source_batch_commit_failure_stale_worker_and_restart(recovery_postgres, tmp_path):
    import psycopg
    from tests.test_lifecycle_withdrawal_recovery_v1 import _console
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore
    blobs = FakeBlobStore()
    root = tmp_path/"writer"
    root.mkdir()
    state, before, command = system(root, _console(root, recovery_postgres, blobs))
    with psycopg.connect(recovery_postgres.dsn) as con:
        con.execute("""CREATE FUNCTION workflow.fail_source_batch_test() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'source_batch_commit_failure'; END; $$""")
        con.execute("""CREATE CONSTRAINT TRIGGER fail_source_batch_test
            AFTER INSERT ON workflow.document_objects DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION workflow.fail_source_batch_test()""")
    try:
        with pytest.raises(Exception, match="source_batch_commit_failure"):
            confirm_source_exclusions(state, **command)
        assert state.snapshot_objects(command["snapshot_id"]) == before
    finally:
        with psycopg.connect(recovery_postgres.dsn) as con:
            con.execute("DROP TRIGGER fail_source_batch_test ON workflow.document_objects")
            con.execute("DROP FUNCTION workflow.fail_source_batch_test()")
    other_root = tmp_path/"other"
    other_root.mkdir()
    other = _console(other_root, recovery_postgres, blobs)
    confirm_source_exclusions(state, **command)
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        confirm_source_exclusions(other, **{**command, "command_id": "stale-worker"})
    fresh_root = tmp_path/"restart"
    fresh_root.mkdir()
    fresh = _console(fresh_root, recovery_postgres, blobs)
    assert fresh.snapshot_objects(command["snapshot_id"]) == state.snapshot_objects(command["snapshot_id"])
    assert confirm_source_exclusions(fresh, **command)["idempotent"] is True


def test_batch_fails_closed_for_stale_substantive_unauthorized_and_failed_commit(tmp_path, monkeypatch):
    state, before, command = system(tmp_path)
    sid = command["snapshot_id"]
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        confirm_source_exclusions(state, **{**command, "expected_revision": "stale"})
    condition = next(r for r in before if (r.get("content") or {}).get("clean_text") == CONDITION)
    with pytest.raises(ConsoleError, match="source_exclusion_not_proposed"):
        confirm_source_exclusions(state, **{**command, "source_object_ids": command["source_object_ids"]+[condition["object_id"]]})
    monkeypatch.setattr(state, "_commit_prepared_store", lambda **kw: (_ for _ in ()).throw(RuntimeError("commit failed")))
    with pytest.raises(RuntimeError, match="commit failed"):
        confirm_source_exclusions(state, **command)
    assert state.snapshot_objects(sid) == before
    monkeypatch.setattr(state, "snapshot_is_published", lambda _: True)
    with pytest.raises(ConsoleError, match="published_working_revision_immutable"):
        confirm_source_exclusions(state, **command)


def test_invalid_source_classifications_cannot_drop_or_overlap_content():
    blocks = [{"block_id": "b", "text": "Versie: 1. Bij verslechtering observeren."}]
    row = {"span": {"block_id": "b", "start": 0, "end": 9}, "role": "metadata", "reason": "document_metadata"}
    assert validate_assessments([row], blocks, []) == [row]
    for bad in [{**row, "reason": "unformed_meaning"}, {**row, "span": {"block_id": "b", "start": 0, "end": 500}}]:
        with pytest.raises(ValueError):
            validate_assessments([bad], blocks, [])
    with pytest.raises(ValueError, match="overlap"):
        validate_assessments([row], blocks, [{"spans": [row["span"]]}])
    with pytest.raises(ValueError, match="overlap"):
        validate_assessments([row, row], blocks, [])


def test_v3_supplement_examines_unselected_definition_outside_recommendations():
    from tests.test_recommendation_context_v3 import response_for
    texts = ["Gebruik geen zalf", DEFINITION, CONDITION]
    fragments = [{"fragment_id": str(i), "fragment_hash": str(i), "raw_text": text, "clean_text": text,
                  "section_path": ["Achtergrond"], "source_locator": {"locator_type": "web_line_range", "locator_value": f"lines:{i+1}-{i+1}"}}
                 for i, text in enumerate(texts)]
    calls = []
    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        calls.append(data)
        p = proposal(data, v3=True) if data.get("selection_targets") else response_for(payload, texts[0])
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(p)}]}]}
    spec = semantic_spec_from_fragments(document_id="doc", title="Test", family="test", class_="richtlijn",
        fragments=fragments, content_kind="html", api_key="fixture", model="fixture", post_json=provider, field_contract_v3=True)
    assert len(calls) == 2
    assert {r["literal"] for r in calls[1]["selection_targets"]} == {DEFINITION, CONDITION}
    assert {r.get("proposed_object_type") for r in spec["objects"]} >= {"recommendation", "definition"}
    assert any(r.get(KEY, {}).get("text") == CONDITION for r in spec["objects"])


def test_partial_supplement_preserves_unresolved_prefix_and_suffix():
    from src.recommendation_coverage_v1 import merge_proposals
    span = {"block_id": "b", "start": 0, "end": 100}
    primary = {"objects": [], "relations": [], "source_assessments": [
        {"span": span, "role": "unresolved", "reason": "unformed_meaning"}]}
    supplement = {"objects": [{"spans": [{**span, "start": 20, "end": 60}]}],
                  "relations": [], "source_assessments": []}
    merged = merge_proposals(primary, supplement)
    assert [row["span"] for row in merged["source_assessments"]] == [
        {**span, "end": 20}, {**span, "start": 60}]
    assert primary["source_assessments"][0]["span"] == span
    primary["source_assessments"][0].update(role="metadata", reason="document_metadata")
    with pytest.raises(ConsoleError, match="source_assessment_overlap"):
        merge_proposals(primary, supplement)


def test_damaged_source_evidence_cannot_close_after_human_disposition(tmp_path):
    state, _, command = system(tmp_path)
    confirm_source_exclusions(state, **command)
    current = state.snapshot_objects(command["snapshot_id"])
    metadata = next(row for row in current if row["object_id"] in command["source_object_ids"])
    metadata["metadata"][KEY]["text"] = "different source"
    assert evidence_of(metadata) == {}
    assert not source_passage_closure([metadata])["source_passage_review_complete"]
    assert review_duty_for(metadata, review_path="richtlijn", bindings=None) is None


def test_exact_duplicate_source_occurrence_keeps_principal_span_and_role():
    from src.source_accountability_v1 import record
    from src.source_occurrence_authority_v1 import prefer_authoritative_exact_occurrences
    text = "A repeated source sentence."
    summary_span = {"block_id": "summary", "start": 0, "end": len(text)}
    primary_span = {"block_id": "primary", "start": 0, "end": len(text)}
    def unit(span, path, role):
        return {"text": text, "clean_text": text, "object_type": "unclassified",
            "source_fragment_ids": [span["block_id"]], "section_path": path,
            "semantic_passage": {"selection_origin": "coverage_remainder", "spans": [span]},
            KEY: record(text=text, spans=[span], assessment=role)}
    rows = prefer_authoritative_exact_occurrences([
        unit(summary_span, ["Samenvatting"], {"role": "metadata", "reason": "document_metadata"}),
        unit(primary_span, ["Klinische beschrijving"], {"role": "unresolved", "reason": "unformed_meaning"}),
    ])
    assert len(rows) == 1
    assert rows[0]["semantic_passage"]["spans"] == [primary_span]
    assert rows[0][KEY]["spans"] == [primary_span]
    assert rows[0][KEY]["proposed_role"] == "unresolved"
    assert len(rows[0]["metadata"]["source_occurrence_authority"]["alternate_occurrences"]) == 1
    selected = unit(summary_span, ["Samenvatting"], {"role": "unresolved", "reason": "unformed_meaning"})
    selected.pop(KEY)
    selected["semantic_passage"]["selection_origin"] = "proposal_selected"
    selected["proposed_object_type"] = "definition"
    promoted = prefer_authoritative_exact_occurrences([
        selected,
        unit(primary_span, ["Klinische beschrijving"], {"role": "unresolved", "reason": "unformed_meaning"}),
    ])
    assert promoted[0]["semantic_passage"]["selection_origin"] == "proposal_selected"
    assert KEY not in promoted[0]
