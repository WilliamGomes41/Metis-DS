"""Translation/security tests supplement, NEVER replace, real PDF acceptance.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale retry version-compat
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import pytest

from src.docling_contract_v1 import CONTRACT, DoclingError, stored_fragments, top_left_box, translate
from src.docling_pdf_v1 import extract, supervise
from src.integrity_kernel import schema_errors, stable_hash
from src.quality_evidence_v1 import record_processing


def test_render_font_build_identity_rejects_missing_changed_or_added_fonts(tmp_path, monkeypatch):
    import hashlib
    from src import docling_render_fonts_v1 as fonts
    monkeypatch.setattr(fonts, "FONT_ROOTS", (tmp_path,))
    standard = tmp_path / "standard.otf"
    standard.write_bytes(b"controlled font file")
    monkeypatch.setattr(fonts, "STANDARD_FONT", str(standard))
    monkeypatch.setattr(fonts, "STANDARD_FONT_SHA256", hashlib.sha256(standard.read_bytes()).hexdigest())
    expected = fonts.font_inventory()
    fonts.verify_fonts(expected)
    extra = tmp_path / "substitute.ttf"
    extra.write_bytes(b"changes native font resolver inventory")
    with pytest.raises(DoclingError, match="render_fonts_invalid"):
        fonts.verify_fonts(expected)
    extra.unlink()
    standard.write_bytes(b"changed")
    with pytest.raises(DoclingError, match="render_fonts_invalid"):
        fonts.verify_fonts(expected)
    standard.unlink()
    with pytest.raises(DoclingError, match="render_fonts_invalid"):
        fonts.verify_fonts(expected)


def result():
    return {"contract": CONTRACT, "source_sha256": "a" * 64,
            "versions": {"docling-slim": "2.132.0", "docling-core": "2.99.0"},
            "document": {"pages": {"1": {"size": {"width": 600, "height": 800}}},
                         "texts": [{"self_ref": "#/texts/0", "text": "één  advies",
                                    "orig": "één\nadvies", "label": "text", "content_layer": "body",
                                    "prov": [{"page_no": 1, "charspan": [0, 11],
                                              "bbox": {"l": 10, "t": 780, "r": 200, "b": 760,
                                                       "coord_origin": "BOTTOMLEFT"}}]}]},
            "reading_order": ["#/texts/0"], "page_text_origins": {"1": [True, False]},
            "models": {"files": {"layout": "b" * 64}}, "settings": {"do_ocr": False},
            "metrics": {"conversion_seconds": 1}}


def rows(payload=None):
    return translate(payload or result(), document_id="doc", source_id="src", source_sha256="a" * 64)


def test_mapping_hash_offsets_origin_and_atomic_evidence():
    fragments = rows()
    row = fragments[0]
    assert row["raw_text"] == "één  advies"
    assert row["clean_text"] == "één advies"
    assert row["bbox"] == [10, 20, 200, 40]
    assert row["source_locator"]["locator_value"] == "page:1;bbox:10.000000,20.000000,200.000000,40.000000"
    assert not schema_errors(row, Path("schemas/raw_fragment.schema.v1.1.json"))
    binding = fragments.extraction_record["bindings"][0]
    assert binding["text_origin"] == "ocr_or_mixed"
    assert fragments.extraction_record["document"]["texts"][0]["orig"] == "één\nadvies"
    envelope = {"sha256": "a" * 64}
    record_processing(envelope, [], fragments=fragments, replay=None, started_at="test")
    restored = stored_fragments(json.loads(json.dumps(envelope)))
    assert restored == fragments
    from io import BytesIO
    from zipfile import ZipFile
    from src.processing_evidence_export_v1 import processing_evidence_zip
    with ZipFile(BytesIO(processing_evidence_zip(snapshot_id="snap", revision="r", envelope=envelope, objects=[]))) as archive:
        retained = json.loads(archive.read("extractions/000000.json"))
        assert retained["document"] == fragments.extraction_record["document"]
        assert retained["record_hash"]
    changed = deepcopy(envelope)
    changed["quality_processing_runs"][-1]["document_extraction"]["prepared_fragments"][0]["raw_text"] += "invented"
    with pytest.raises(DoclingError, match="stored_evidence_invalid"):
        stored_fragments(changed)
    assert stored_fragments({"sha256": "a" * 64}) is None


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p.update(source_sha256="c" * 64), "result_identity_invalid"),
    (lambda p: p["document"]["texts"][0]["prov"][0].update(charspan=[0, 999]), "charspan_invalid"),
    (lambda p: p["document"]["texts"][0]["prov"][0].update(page_no=0), "page_invalid"),
    (lambda p: p["document"]["texts"][0]["prov"][0]["bbox"].update(coord_origin="unknown"), "geometry_invalid"),
    (lambda p: p.update(reading_order=[]), "inventory_incomplete"),
])
def test_bad_contract_fails_closed(mutation, code):
    payload = result(); mutation(payload)
    with pytest.raises(DoclingError, match=code):
        rows(payload)


def test_table_structure_furniture_and_missing_table_page_fail_closed():
    payload = result()
    prov = deepcopy(payload["document"]["texts"][0]["prov"])
    payload["document"]["tables"] = [{"self_ref": "#/tables/0", "label": "table", "prov": prov,
         "data": {"num_rows": 1, "num_cols": 1, "table_cells": [{"text": "ouderen", "row_span": 1,
                  "col_span": 1, "start_row_offset_idx": 0, "start_col_offset_idx": 0}]}}]
    payload["reading_order"].append("#/tables/0")
    payload["document"]["texts"][0].update(content_layer="furniture", label="page_header")
    fragments = rows(payload)
    assert [r["raw_text"] for r in fragments] == ["ouderen"]
    assert fragments.extraction_record["exclusions"][0]["reason"] == "docling_furniture"
    assert fragments.extraction_record["document"]["tables"][0]["data"]["num_cols"] == 1
    payload["document"]["tables"][0]["prov"].extend(prov)
    with pytest.raises(DoclingError, match="multipage_table_mapping_unresolved"):
        rows(payload)


def test_real_supervisor_kills_hung_native_process_and_suppresses_stderr(tmp_path, monkeypatch):
    import subprocess
    processes = []
    original = subprocess.Popen
    def observe(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(subprocess, "Popen", observe)
    pidfile = tmp_path / "pid"
    script = f"import os,time,pathlib; pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(30)"
    with pytest.raises(DoclingError, match="docling_timeout"):
        supervise([sys.executable, "-c", script], pass_fds=(), env=dict(os.environ),
                  timeout=.3, max_rss_bytes=256 * 1024 * 1024)
    assert pidfile.is_file()
    assert processes[-1].returncode == -9
    assert processes[-1].poll() == -9
    with pytest.raises(DoclingError, match="worker_failed") as error:
        supervise([sys.executable, "-c", "raise ValueError('private source and secret')"],
                  pass_fds=(), env=dict(os.environ), timeout=2, max_rss_bytes=256 * 1024 * 1024)
    assert "private" not in str(error.value)


def test_not_configured_is_explicit_and_never_legacy_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("METIS_DOCLING_PYTHON", raising=False)
    source = tmp_path / "source.pdf"; source.write_bytes(b"%PDF-test")
    with pytest.raises(DoclingError, match="runtime_not_configured"):
        extract(source, document_id="doc", source_id="src")


def test_missing_true_pipeline_persists_failed_attempt_and_duplicate_restarts_safely(tmp_path, monkeypatch):
    import fitz
    from src.operations_console_v1 import OperationsConsole
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    monkeypatch.delenv("METIS_DOCLING_PYTHON", raising=False)
    with fitz.open() as doc:
        doc.new_page().insert_text((72, 72), "Broninhoud blijft behouden.")
        data = doc.tobytes()
    def create():
        return OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    console = create()
    author = console.create_account(username="author", password="long-test-secret", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="long-test-secret", roles=("reviewer",))
    command = dict(actor_id=author["account_id"], filename="source.pdf", data=data,
                   content_type="application/pdf", ingest_kind="new", title="Bron", version="1.0",
                   date="2026-10-03", live_url="", class_="richtlijn", family="test",
                   named_reviewers=[reviewer["account_id"]], command_id="docling-failure")
    receipt = console.ingest(**command); sid = receipt["snapshot_id"]
    assert not console.snapshot_objects(sid)
    assert receipt["processing_attempts"][-1]["state"] == "failed"
    assert receipt["processing_attempts"][-1]["error_code"] == "docling_runtime_not_configured"
    restarted = create()
    assert restarted.ingest(**command)["snapshot_id"] == sid
    assert len(restarted._envelope(sid)["processing_attempts"]) == 1
    assert restarted.processing_status(sid)["retry_allowed"]
    assert restarted._verified_source_bytes(restarted._envelope(sid))[1] == data


def test_official_list_marker_full_original_span_is_preserved_not_clamped():
    payload = result()
    item = payload["document"]["texts"][0]
    item.update(label="list_item", text="één advies", orig="· één advies", marker="·")
    item["prov"][0]["charspan"] = [0, len(item["orig"])]
    fragments = rows(payload)
    assert fragments[0]["raw_text"] == "· één advies"
    assert fragments.extraction_record["bindings"][0]["charspan_text_field"] == "orig"
    assert fragments.extraction_record["document"]["texts"][0]["text"] == "één advies"
    item["orig"] = "x één advies"
    with pytest.raises(DoclingError, match="charspan_invalid"):
        rows(payload)
