"""Coverage omission -> bounded same-provider supplement -> durable evidence.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json

import pytest

from src.pre_review_semantic_v1 import semantic_spec_from_fragments
from src.semantic_transform_generic_v1 import transform
from src.admission_gate_v1 import apply_admission_gate
from src.recommendation_coverage_v1 import assess, inventory
from tests.test_recommendation_context_v3 import response_for, source

FIRST = "Bespreek de voorkeuren"
SECOND = "Controleer de ondersteuning"


def test_inventory_distinguishes_numbered_items_inside_a_single_block():
    blocks = [{"block_id": "b", "section_path": ["Module", "Aanbevelingen"],
               "text": "1. Bespreek de voorkeuren Sterk – voor 2. Controleer de ondersteuning Sterk – voor"}]
    rows = inventory(blocks)
    assert [r["text"] for r in rows] == [FIRST, SECOND]
    selected = {"objects": [{"proposed_object_type": "recommendation", "spans": [rows[0]["span"]]}]}
    assert [r["status"] for r in assess(blocks, selected)["entries"]] == ["selected", "open"]


def test_descriptive_body_ends_possible_scope_label_adjacency():
    texts = ["De klinische verschijnselen zijn:", "Een rode verkleuring", FIRST,
             "Bij een natte plek:", SECOND]
    blocks = [{"block_id": str(i), "section_path": ["Aanbevelingen"], "text": text}
              for i, text in enumerate(texts)]
    rows = inventory(blocks)
    assert rows[0]["scope_cue"] is None
    assert rows[1]["scope_cue"]["text"] == "Bij een natte plek:"


def run(supplement="selected", *, identity=True):
    fragments = [source(FIRST)[0], {**source(SECOND)[0], "fragment_id": "core-2", "fragment_hash": "core-2-hash"}]
    calls = []
    def provider(_url, _headers, payload, timeout):
        calls.append((payload, timeout))
        text = FIRST if len(calls) == 1 else SECOND
        prop = response_for(payload, text)
        if len(calls) == 2 and supplement == "abstain":
            prop = {"objects": [], "relations": [], "abstain_reason": "uncertain"}
        if len(calls) == 2 and supplement == "corrupt":
            prop["objects"][0]["field_evidence"]["recommended_action"]["span"]["literal"] = "Invented"
        return {"id": f"call-{len(calls)}", "status": "completed", "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(prop)}]}]}
    context = {"snapshot_id": "snap", "source_sha256": "a"*64} if identity else None
    spec = semantic_spec_from_fragments(document_id="doc", title="Test", family="test", class_="richtlijn",
        fragments=fragments, content_kind="html", api_key="test", model="test", post_json=provider,
        field_contract_v3=True, formation_context=context)
    manifest = {"canonical_source": {"source_id": "s", "title": "Test", "source_type": "html",
        "source_url": "test", "source_level": "national", "canonicality": "canonical",
        "integrity_status": "verified", "source_checksum": "a"*64, "version": "1"}}
    rows = apply_admission_gate(transform(spec, manifest, fragments), klasse="richtlijn", fragments=fragments,
        document_version="1", source_hash="a"*64)
    return spec, rows, calls, fragments


def test_omitted_recommendation_gets_one_supplement_with_shared_budget_and_both_calls_exported():
    spec, rows, calls, _ = run()
    assert len(calls) == 2 and calls[1][1] < calls[0][1]
    data = json.loads(calls[1][0]["input"][1]["content"])
    assert len(data["source_blocks"]) == 1
    assert data["selection_targets"][0]["literal"] == SECOND
    selected = [o for o in rows if (o.get("metadata") or {}).get("source_bound_fields")]
    assert len(selected) == 2
    assert all(o["metadata"]["admission"]["gate_result"] == "allowed" for o in selected)
    from src.processing_evidence_export_v1 import processing_evidence_tables
    tables, _ = processing_evidence_tables(snapshot_id="snap", revision="r", objects=rows,
        envelope={"semantic_replay": spec["_semantic_replay"]})
    assert [r["call_id"] for r in tables["model_calls"]] == ["call-1", "call-2"]
    assert all(r["request"] and r["output_text"] for r in tables["model_calls"])
    assert [r["status"] for r in tables["recommendation_coverage"]] == ["selected", "selected"]


def test_supplement_abstention_remains_open_in_existing_remainder_no_third_call():
    _, rows, calls, _ = run("abstain")
    assert len(calls) == 2
    pending = [o for o in rows if any(r["status"] == "open" for r in
        ((o.get("metadata") or {}).get("recommendation_coverage") or {}).get("entries", []))]
    assert pending and SECOND in pending[0]["content"]["clean_text"]
    from src.passage_register_v1 import apply_passage_register
    assert apply_passage_register(pending)[0]["metadata"]["passage_register"]["status"] == "not_yet_assessed"


def test_invalid_supplement_keeps_valid_work_and_explicit_unresolved_source():
    spec, rows, calls, _ = run("corrupt")
    assert len(calls) == 2
    candidates = [o for o in rows if (o.get("metadata") or {}).get("source_bound_fields")]
    assert len(candidates) == 1 and candidates[0]["content"]["clean_text"] == FIRST
    evidence = spec["_semantic_replay"]["provider_evidence"]
    assert evidence["formation_incomplete"]
    assert evidence["pending_rejections"][0]["reason_code"] == "semantic_evidence_literal_not_found"
    from src.source_accountability_v1 import evidence_of
    assert any(evidence_of(o).get("text") == SECOND for o in rows)


def test_replay_revalidates_merged_proposal_without_another_provider_call():
    spec, _, _, fragments = run()
    def forbidden(*args):
        raise AssertionError("exact replay must not invoke provider")
    replayed = semantic_spec_from_fragments(document_id="doc", title="Test", family="test", class_="richtlijn",
        fragments=fragments, content_kind="html", api_key="test", model="test", post_json=forbidden,
        field_contract_v3=True, formation_context={"snapshot_id": "snap", "source_sha256": "a"*64,
            "semantic_replay": deepcopy(spec["_semantic_replay"])})
    assert replayed["_semantic_replay"]["semantic_execution"] == "replay"
    assert replayed["_semantic_replay"]["proposal"] == spec["_semantic_replay"]["proposal"]


def console_v3_story(tmp_path, make_console):
    from src.operations_console_v1 import ConsoleError
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing, PASSAGE_FORMATION_MODE_ENV
    from src.llm_provider_v1 import LLM_API_KEY_ENV, LLM_MODEL_ENV
    from src.source_bound_fields_v3 import MODE
    calls, fail = [], []
    def provider(_url, _headers, payload, _timeout):
        calls.append(payload)
        if fail:
            return {"status": "incomplete", "output": []}
        data = json.loads(payload["input"][1]["content"])
        text = SECOND if data.get("selection_targets") else FIRST
        return {"id": f"call-{len(calls)}", "status": "completed", "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(response_for(payload, text))}]}]}
    env = {PASSAGE_FORMATION_MODE_ENV: MODE, LLM_API_KEY_ENV: "test", LLM_MODEL_ENV: "test-model"}
    console = make_console()
    bind_pre_review_semantic_processing(console, environ=env, post_json=provider)
    author = console.create_account(username='author', password='strong-test-password', roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password='strong-test-password', roles=('reviewer',))
    receipt = console.ingest(actor_id=author['account_id'], filename='test.html',
        data=f'<html><body><h1>Aanbevelingen</h1><p>{FIRST}</p><p>{SECOND}</p></body></html>'.encode(),
        content_type='text/html', ingest_kind='new', title='Test', version='1.0', date='2026-10-03',
        live_url='', class_='richtlijn', family='test', named_reviewers=[reviewer['account_id']])
    sid = receipt['snapshot_id']
    initial = console.snapshot_objects(sid, include_blocked=True)
    recommendations = [o for o in initial if (o.get('metadata') or {}).get('source_bound_fields')]
    assert len(recommendations) == 2 and len(calls) == 2
    assert all(o['metadata']['admission']['gate_result'] == 'allowed' for o in recommendations)
    assert all(o['governance']['validation_status'] == 'needs_review' for o in recommendations)
    restarted = make_console()
    bind_pre_review_semantic_processing(restarted, environ=env, post_json=provider)
    assert restarted.snapshot_objects(sid, include_blocked=True) == initial
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app, COOKIE
    import csv, io
    from zipfile import ZipFile
    client = TestClient(create_console_app(restarted))
    url = '/review/processing-evidence-export'
    assert client.get(url, params={'document': sid}, follow_redirects=False).status_code in {302, 303, 307, 401, 403}
    session = restarted.authenticate('reviewer', 'strong-test-password')
    client.cookies.set(COOKIE, session['token'])
    response = client.get(url, params={'document': sid})
    assert response.status_code == 200
    with ZipFile(io.BytesIO(response.content)) as archive:
        calls_export = list(csv.DictReader(io.StringIO(archive.read('model_calls.csv').decode('utf-8-sig'))))
        assert len(calls_export) == 2
        assert 'recommendation_coverage.csv' in archive.namelist()
    restarted.reextract_unpublished(actor_id=author['account_id'], snapshot_id=sid)
    assert len(calls) == 2
    assert len(restarted._envelope(sid)['semantic_replay']['provider_evidence']['supplementary_calls']) == 1
    before, revision = restarted.snapshot_objects(sid, include_blocked=True), restarted.objects_revision(sid)
    fail.append(True)
    env[LLM_MODEL_ENV] = 'different-model'
    with pytest.raises(ConsoleError, match='pre_review_llm_response_not_completed'):
        restarted.reextract_unpublished(actor_id=author['account_id'], snapshot_id=sid)
    assert restarted.snapshot_objects(sid, include_blocked=True) == before
    assert restarted.objects_revision(sid) == revision
    assert restarted._envelope(sid)['processing_attempts'][-1]['state'] == 'failed'


def test_console_v3_survives_restart_replays_and_failed_replacement_is_atomic(tmp_path):
    from src.operations_console_v1 import OperationsConsole
    console_v3_story(tmp_path, lambda: OperationsConsole(
        root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime'))
