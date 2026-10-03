"""Real official Docling and models: run explicitly in acceptance environment.

No extractor mocks. Controlled semantic provider only removes paid API dependency.
Normal console CI cannot install ML packages into its lean dependency contract.
These tests are an acceptance gate, NOT evidence until they actually pass.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale retry version-compat
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import hashlib
import json
import os
from pathlib import Path

import fitz
import pytest

from src.docling_contract_v1 import CONTRACT, DoclingError, stored_fragments
from src.docling_pdf_v1 import extract
from src.extract_pdf_v2 import extract as legacy
from src.open_original_v1 import passage_from_pdf_freeze
from tests.test_source_bound_fields_v2 import TEXT, proposal

pytestmark = pytest.mark.skipif(os.environ.get("METIS_DOCLING_REAL_ACCEPTANCE") != "1",
                              reason="Real Docling/models acceptance environment required; not proven by unit tests")


def pdf(tmp_path, text=TEXT):
    path = tmp_path / "source.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 80), "Screening", fontsize=20)
        page.insert_text((72, 140), text, fontsize=12)
        doc.save(path)
    return path


def test_true_pipeline_preserves_text_hash_and_original_geometry(tmp_path):
    source = pdf(tmp_path)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    rows = extract(source, document_id="doc", source_id="src")
    row = next(r for r in rows if TEXT in r["clean_text"])
    assert TEXT in passage_from_pdf_freeze(source.read_bytes(), row["source_locator"]["locator_value"])
    evidence = rows.extraction_record
    assert evidence["source_sha256"] == digest
    assert evidence["versions"]["docling-slim"] == "2.132.0"
    assert evidence["models"]["files"] and evidence["settings"]["do_table_structure"] is True
    assert evidence["settings"]["do_ocr"] is False
    assert evidence["metrics"]["worker_reaped"] is True
    assert TEXT in " ".join(r["clean_text"] for r in legacy(source, document_id="doc", source_id="src"))


def test_real_structure_columns_labels_table_and_cross_page(tmp_path):
    source = tmp_path / "structure.pdf"
    with fitz.open() as doc:
        for page_no in range(2):
            page = doc.new_page()
            page.insert_text((72, 60), "1. Aanbevelingen" if page_no == 0 else "1.1. Vervolg", fontsize=20)
            page.insert_text((72, 100), "DOEN" if page_no == 0 else "OVERWEEG", fontsize=14)
            page.insert_textbox(fitz.Rect(72, 130, 280, 270), "Linkerkolom: beoordeel ouderen.\nBewaar deze broninhoud.", fontsize=12)
            page.insert_textbox(fitz.Rect(320, 130, 530, 270), "Rechterkolom: bespreek het vervolg.\nBewaar ook deze broninhoud.", fontsize=12)
            for index, x in enumerate([72, 260, 440]):
                page.draw_line((x, 340), (x, 420))
            for y in [340, 380, 420]:
                page.draw_line((72, y), (440, y))
            page.insert_text((82, 365), "Doelgroep", fontsize=12)
            page.insert_text((270, 365), "Handeling", fontsize=12)
            page.insert_text((82, 405), "Ouderen", fontsize=12)
            page.insert_text((270, 405), "Beoordelen", fontsize=12)
            page.insert_text((72, 800), f"Documentvoet {page_no + 1}", fontsize=8)
        doc.save(source)
    rows = extract(source, document_id="structure", source_id="src")
    texts = " ".join(r["clean_text"] for r in rows)
    for expected in ["DOEN", "OVERWEEG", "Linkerkolom", "Rechterkolom", "Ouderen", "Beoordelen"]:
        assert expected in texts
    assert rows.extraction_record["document"]["tables"], "Model must recognize actual table structure"
    assert {r["source_page"] for r in rows} == {1, 2}
    for page_no in [1, 2]:
        page_rows = [r for r in rows if r["source_page"] == page_no]
        left = next(i for i, r in enumerate(page_rows) if "Linkerkolom" in r["clean_text"])
        right = next(i for i, r in enumerate(page_rows) if "Rechterkolom" in r["clean_text"])
        assert left < right
    # Compare concrete source text, not fragment counts. No quality-gain claim.
    old = legacy(source, document_id="structure", source_id="src")
    assert "Beoordelen" in " ".join(r["clean_text"] for r in old)


def chain(root, create_console):
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.operations_console_v1 import ConsoleError
    from src.source_bound_fields_v2 import KEY, MODE
    source = pdf(root)
    console = create_console()
    env = {"METIS_LLM_API_KEY": "test", "METIS_LLM_MODEL": "controlled",
           "METIS_PASSAGE_FORMATION_MODE": MODE}
    def post(url, headers, payload, timeout):
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal(payload))}]}]}
    bind_pre_review_semantic_processing(console, environ=env, post_json=post)
    author = console.create_account(username="author", password="test-secret-long", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="test-secret-long", roles=("reviewer",))
    command = dict(actor_id=author["account_id"], filename="source.pdf", data=source.read_bytes(),
                   content_type="application/pdf", ingest_kind="new", title="Screening", version="1.0",
                   date="2026-10-03", live_url="", class_="richtlijn", family="test",
                   named_reviewers=[reviewer["account_id"]], command_id="docling-real-command")
    receipt = console.ingest(**command); sid = receipt["snapshot_id"]
    assert console.processing_status(sid)["state"] == "succeeded"
    assert console.ingest(**command)["snapshot_id"] == sid
    target = next(o for o in console.snapshot_objects(sid) if KEY in o.get("metadata", {}))
    assert target["metadata"]["admission"]["gate_result"] == "allowed"
    assert target["governance"]["validation_status"] == "needs_review"
    locator = target["provenance"]["source_fragments"][0]["source_locator"]["locator_value"]
    assert TEXT in passage_from_pdf_freeze(source.read_bytes(), locator)
    before = stored_fragments(console._envelope(sid))
    console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
                          object_id=target["object_id"], decision="reject", comment="Controlled review evidence")
    restarted = create_console()
    assert stored_fragments(restarted._envelope(sid)) == before
    restored_target = next(o for o in restarted.snapshot_objects(sid) if o["object_id"] == target["object_id"])
    assert restored_target["governance"]["validation_status"] == "rejected"
    assert not restarted.object_review_bindings(sid), "Rejection must not grant publication authorization"
    # Capture/extraction/review do not bypass immutable storage/publication gates.
    assert restarted._envelope(sid)["publication_eligibility"] == "blocked_pending_immutable_storage"
    return sid


def test_real_upload_semantic_source_review_restart_existing_publication_gate(tmp_path, monkeypatch):
    from src.operations_console_v1 import OperationsConsole
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    chain(tmp_path, lambda: OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime"))


def test_real_pdf_postgres_chain(tmp_path, workflow_postgres, monkeypatch):
    from tests.test_review_batch_atomic_postgres import _console
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    chain(tmp_path, lambda: _console(tmp_path, workflow_postgres))


from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: E402, F401


def test_real_pdf_postgres_successful_publication_and_restart(tmp_path, recovery_postgres, monkeypatch):
    """Actual models + native PostgreSQL + unchanged review/publication commands.

    The test source-store double avoids an Azure subscription; it does not prove
    Azure Blob immutability or production deployment packaging.
    """
    from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole
    from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
    from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
    from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
    from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
    from src.workflows.workflow_transaction_v1 import bind_workflow_stores
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.source_bound_fields_v2 import KEY, MODE
    from src.operations_console_v1 import ConsoleError, review_lane
    from src.review_disposition_v1 import definitive_review_disposition
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    source_store = MemorySourceStore()
    def create():
        identity = CutoverPostgresWorkflowIdentityStore(recovery_postgres)
        documents = PostgresConcurrentWorkflowDocumentStore(recovery_postgres)
        reviews = PostgresWorkflowReviewStore(recovery_postgres)
        remaining = PostgresWorkflowRemainingStore(recovery_postgres)
        bind_workflow_stores(identity, documents, reviews, remaining)
        return FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole(
            root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime",
            immutable_source_store=source_store, canonical_publication_store=PostgresCanonicalPublicationStore(recovery_postgres),
            workflow_identity_store=identity, workflow_document_store=documents,
            workflow_review_store=reviews, workflow_remaining_store=remaining)
    console = create()
    def post(url, headers, payload, timeout):
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal(payload))}]}]}
    bind_pre_review_semantic_processing(console, environ={"METIS_LLM_API_KEY": "test",
        "METIS_LLM_MODEL": "controlled", "METIS_PASSAGE_FORMATION_MODE": MODE}, post_json=post)
    accounts = {name: console.create_account(username=name, password="test-secret-long", roles=roles)
                for name, roles in [("author", ("researcher",)), ("first", ("reviewer",)),
                                    ("second", ("reviewer",)), ("publisher", ("publisher",))]}
    source = pdf(tmp_path)
    receipt = console.ingest(actor_id=accounts["author"]["account_id"], filename="source.pdf",
        data=source.read_bytes(), content_type="application/pdf", ingest_kind="new", title="Screening",
        version="1.0", date="2026-10-03", live_url="", class_="richtlijn", family="test",
        named_reviewers=[accounts["first"]["account_id"], accounts["second"]["account_id"]])
    sid = receipt["snapshot_id"]
    assert console.processing_status(sid)["state"] == "succeeded"
    target = next(o for o in console.snapshot_objects(sid) if KEY in o.get("metadata", {}))
    with pytest.raises(ConsoleError):
        console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
    assert console.open_source_passage(snapshot_id=sid, object_id=target["object_id"])
    console.review_object(actor_id=accounts["first"]["account_id"], snapshot_id=sid,
        object_id=target["object_id"], decision="approve", confirmed_object_type="recommendation",
        recommendation_direction="against", recommendation_strength_level="not_stated")
    console.approve_second_review(actor_id=accounts["second"]["account_id"], snapshot_id=sid,
                                  object_id=target["object_id"])
    for obj in console.snapshot_objects(sid):
        if obj["object_id"] == target["object_id"] or obj.get("object_type") == "document" or review_lane(obj) == "fast":
            continue
        if definitive_review_disposition(obj)["final"]:
            continue
        console.review_object(actor_id=accounts["first"]["account_id"], snapshot_id=sid,
            object_id=obj["object_id"], decision="reject", suitability="ja", eindoordeel="afwijzen",
            comment="Fixture: no separate knowledge object for this source passage")
    before = stored_fragments(console._envelope(sid))
    console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
    release = console.canonical_publication_store.release_for_snapshot(sid)
    assert release and any(o["object_id"] == target["object_id"] for o in release["objects"])
    restarted = create()
    assert restarted.canonical_publication_store.release_for_snapshot(sid) == release
    assert stored_fragments(restarted._envelope(sid)) == before
    with pytest.raises(ConsoleError):
        restarted.reextract_unpublished(actor_id=accounts["author"]["account_id"], snapshot_id=sid)


from tests.test_workflow_chain_recovery_v1 import recovery_postgres  # noqa: E402, F401


def test_acceptance_requires_native_postgres():
    assert os.environ.get("METIS_TEST_POSTGRES_DSN"), "Acceptance must not pass with skipped PostgreSQL proofs"


@pytest.mark.parametrize("backend", ["local", "postgres"])
def test_real_converter_timeout_restart_retry_no_partial_activation(tmp_path, monkeypatch, request, backend):
    from src.operations_console_v1 import OperationsConsole
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.source_bound_fields_v2 import MODE
    if backend == "postgres":
        from tests.test_review_batch_atomic_postgres import _console
        config = request.getfixturevalue("workflow_postgres")
        create = lambda: _console(tmp_path, config)
    else:
        create = lambda: OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    def bind(console):
        def post(url, headers, payload, timeout):
            return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal(payload))}]}]}
        bind_pre_review_semantic_processing(console, environ={"METIS_LLM_API_KEY": "test",
            "METIS_LLM_MODEL": "controlled", "METIS_PASSAGE_FORMATION_MODE": MODE}, post_json=post)
        return console
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    monkeypatch.setenv("METIS_DOCLING_TIMEOUT_SECONDS", "0.01")
    console = bind(create())
    author = console.create_account(username="author", password="test-secret-long", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="test-secret-long", roles=("reviewer",))
    source = pdf(tmp_path)
    receipt = console.ingest(actor_id=author["account_id"], filename="source.pdf", data=source.read_bytes(),
        content_type="application/pdf", ingest_kind="new", title="Screening", version="1.0", date="2026-10-03",
        live_url="", class_="richtlijn", family="test", named_reviewers=[reviewer["account_id"]])
    sid = receipt["snapshot_id"]
    assert console.processing_status(sid)["state"] == "failed"
    assert receipt["processing_attempts"][-1]["error_code"] == "docling_timeout"
    assert not console.snapshot_objects(sid)
    assert stored_fragments(console._envelope(sid)) is None
    assert console._verified_source_bytes(console._envelope(sid))[1] == source.read_bytes()
    monkeypatch.setenv("METIS_DOCLING_TIMEOUT_SECONDS", "1200")
    restarted = bind(create())
    restarted.retry_pre_review(actor_id=author["account_id"], snapshot_id=sid, command_id="real-retry")
    assert restarted.processing_status(sid)["state"] == "succeeded"
    assert [a["state"] for a in restarted._envelope(sid)["processing_attempts"]] == ["failed", "succeeded"]
    before = stored_fragments(restarted._envelope(sid))
    assert before and restarted.snapshot_objects(sid)
    # A successful duplicate must return durable work even with runtime disabled.
    monkeypatch.delenv("METIS_DOCLING_PYTHON")
    replay = create()
    replay.retry_pre_review(actor_id=author["account_id"], snapshot_id=sid, command_id="real-retry")
    assert stored_fragments(replay._envelope(sid)) == before
    assert len(replay._envelope(sid)["processing_attempts"]) == 2
