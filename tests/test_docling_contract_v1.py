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


def test_rss_uses_own_child_in_the_mounted_pid_namespace(monkeypatch):
    from src import docling_pdf_v1 as adapter
    statuses = {
        "/proc/self/status": {"Pid": "100", "NSpid": "100 5"},
        # Host PID 6 is an unrelated process, not the namespace-local child 6.
        "/proc/6/status": {"Pid": "6", "PPid": "1", "NSpid": "6", "VmRSS": "1 kB"},
        "/proc/101/status": {"Pid": "101", "PPid": "100", "NSpid": "101 6", "VmRSS": "12345 kB"},
    }
    monkeypatch.setattr(adapter, "_status", lambda path: statuses.get(str(path), {}))
    monkeypatch.setattr(Path, "read_text", lambda self: "101" if str(self) == "/proc/thread-self/children" else "")
    assert adapter._rss(6) == 12345 * 1024
    def missing_children(self):
        raise FileNotFoundError()
    monkeypatch.setattr(Path, "read_text", missing_children)
    monkeypatch.setattr(Path, "iterdir", lambda self: iter([Path("/proc/6"), Path("/proc/101")]))
    assert adapter._rss(6) == 12345 * 1024


def test_real_supervisor_terminates_memory_overrun_from_a_thread():
    from concurrent.futures import ThreadPoolExecutor
    def run():
        with pytest.raises(DoclingError, match="docling_memory_limit_exceeded"):
            supervise([sys.executable, "-c", "import time; allocation=bytearray(96*1024*1024); time.sleep(10)"],
                      pass_fds=(), env=dict(os.environ), timeout=5, max_rss_bytes=32*1024*1024)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(run).result(timeout=8)


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


def test_visible_page_intersection_retains_raw_bounds_and_rejects_invalid_geometry():
    size = {"width": 100, "height": 200}
    box = {"l": 20, "r": 80, "t": 5, "b": -1, "coord_origin": "BOTTOMLEFT"}
    with pytest.raises(DoclingError, match="geometry_invalid"):
        top_left_box(box, size)
    assert top_left_box(box, size, intersect_page=True) == [20, 195, 80, 200]
    assert box["b"] == -1
    for invalid in [dict(box, t=-5, b=-10), dict(box, l=90, r=80), dict(box, t=float("nan")),
                    dict(box, coord_origin="unknown")]:
        with pytest.raises(DoclingError, match="geometry_invalid"):
            top_left_box(invalid, size, intersect_page=True)
    payload = result()
    raw = payload["document"]["texts"][0]["prov"][0]["bbox"]
    raw.update(t=5, b=-1)
    fragments = rows(payload)
    assert fragments[0]["bbox"] == [10, 795, 200, 800]
    assert fragments.extraction_record["bindings"][0]["provenance"]["bbox"] == raw


def test_pinned_sdk_merged_text_uses_first_page_height_not_target_page_height():
    payload = result()
    payload["document"]["pages"]["2"] = {"size": {"width": 600, "height": 1200}}
    item = payload["document"]["texts"][0]
    item.update(text="eerste tweede", orig="eerste tweede")
    item["prov"][0]["charspan"] = [0, 6]
    item["prov"].append({"page_no": 2, "charspan": [7, 13],
        "bbox": {"l": 10, "r": 200, "t": 780, "b": 760, "coord_origin": "BOTTOMLEFT"}})
    fragments = rows(payload)
    assert [f["source_page"] for f in fragments] == [1, 2]
    assert [f["bbox"] for f in fragments] == [[10, 20, 200, 40], [10, 20, 200, 40]]
    assert fragments.extraction_record["bindings"][1]["docling_origin_height"] == 800
    assert fragments.extraction_record["document"]["texts"][0]["prov"][1]["bbox"]["t"] == 780


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


def test_missing_true_pipeline_persists_failed_attempt_and_duplicate_restarts_safely(tmp_path, monkeypatch, *, production_console):
    import fitz
    from src.operations_console_v1 import OperationsConsole
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    monkeypatch.delenv("METIS_DOCLING_PYTHON", raising=False)
    with fitz.open() as doc:
        doc.new_page().insert_text((72, 72), "Broninhoud blijft behouden.")
        data = doc.tobytes()
    def create():
        return production_console(processing_binder=lambda console: None, root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
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


def test_later_extraction_free_runs_keep_accepted_fragments_for_source_readers(monkeypatch):
    from src.operations_console_v1 import OperationsConsole
    import src.operations_console_v1 as kernel
    fragments = rows()
    envelope = {"sha256": "a" * 64, "content_kind": "pdf", "class": "richtlijn",
                "document_id": "doc", "source_id": "src"}
    record_processing(envelope, [], fragments=fragments, replay=None, started_at="accepted")
    record_processing(envelope, [], fragments=[], replay=None, started_at="class-change")
    record_processing(envelope, [], fragments=[], replay=None, started_at="failed",
                      outcome="blocked", reason="docling_timeout")
    # Stored history is the input; source reading must not depend on runtime or reconversion.
    restored = json.loads(json.dumps(envelope))
    def forbidden(*args, **kwargs):
        raise AssertionError("Native parser must not replace retained Docling IDs")
    monkeypatch.setattr(kernel, "extract_pdf", forbidden)
    assert OperationsConsole._read_source_fragments(None, restored, Path("unused.pdf")) == fragments
    assert restored == envelope


def test_latest_complete_extraction_wins_and_corruption_never_downgrades():
    first = rows()
    changed = result()
    changed["document"]["texts"][0].update(text="ander advies", orig="ander advies")
    changed["document"]["texts"][0]["prov"][0]["charspan"] = [0, 12]
    second = rows(changed)
    envelope = {"sha256": "a" * 64}
    for fragment_set in [first, second, []]:
        record_processing(envelope, [], fragments=fragment_set, replay=None, started_at="test")
    assert stored_fragments(envelope) == second
    envelope["quality_processing_runs"][-2]["document_extraction"]["prepared_fragments"][0]["raw_text"] += " invented"
    with pytest.raises(DoclingError, match="stored_evidence_invalid"):
        stored_fragments(envelope)


@pytest.mark.parametrize("invalid_record", [None, [], {}])
def test_malformed_latest_extraction_does_not_fall_back(invalid_record):
    envelope = {"sha256": "a" * 64}
    record_processing(envelope, [], fragments=rows(), replay=None, started_at="accepted")
    record_processing(envelope, [], fragments=rows(), replay=None, started_at="latest")
    envelope["quality_processing_runs"][-1]["document_extraction"] = invalid_record
    with pytest.raises(DoclingError, match="stored_evidence_invalid"):
        stored_fragments(envelope)


def test_later_native_extraction_does_not_reuse_older_docling_fragments():
    envelope = {"sha256": "a" * 64}
    record_processing(envelope, [], fragments=rows(), replay=None, started_at="docling")
    native = deepcopy(list(rows()))
    native[0]["parser_version"] = "pdf-fragments-v2.3.2"
    record_processing(envelope, [], fragments=native, replay=None, started_at="native")
    record_processing(envelope, [], fragments=[], replay=None, started_at="class-change")
    assert stored_fragments(envelope) is None
    # A Docling producer must not be mistaken for historical native work if its evidence is lost.
    envelope["quality_processing_runs"][-2]["extractor_versions"] = [CONTRACT + "/2.132.0"]
    with pytest.raises(DoclingError, match="stored_evidence_invalid"):
        stored_fragments(envelope)


def test_selected_page_without_usable_text_is_not_silently_accepted():
    payload = result()
    payload["document"]["pages"]["2"] = {"size": {"width": 600, "height": 800}}
    payload["page_text_origins"]["2"] = []
    with pytest.raises(DoclingError, match="page_text_unverified"):
        rows(payload)

    # Explicit page selection does not require text on an unselected page.
    selected = translate(payload, document_id="doc", source_id="src",
                         source_sha256="a" * 64, pages=[1])
    assert {f["source_page"] for f in selected} == {1}
    furniture = deepcopy(payload["document"]["texts"][0])
    furniture.update(self_ref="#/texts/1", content_layer="furniture", label="page_footer")
    furniture["prov"][0]["page_no"] = 2
    payload["document"]["texts"].append(furniture)
    payload["reading_order"].append(furniture["self_ref"])
    with pytest.raises(DoclingError, match="page_text_unverified"):
        rows(payload)


def test_table_of_contents_page_is_accounted_navigation_not_source_text():
    # Conceptrichtlijn Smetten: a second contents page holds only Docling's
    # document_index. It is navigation; blank and furniture-only pages still fail.
    payload = result()
    payload["document"]["pages"]["2"] = {"size": {"width": 600, "height": 800}}
    prov = deepcopy(payload["document"]["texts"][0]["prov"])
    prov[0]["page_no"] = 2
    cells = [{"text": "Rationale ........ ....", "row_span": 1, "col_span": 1,
              "start_row_offset_idx": 0, "start_col_offset_idx": 1},
             {"text": "25", "row_span": 1, "col_span": 1,
              "start_row_offset_idx": 0, "start_col_offset_idx": 2}]
    payload["document"]["tables"] = [{"self_ref": "#/tables/0", "label": "document_index", "prov": prov,
                                      "data": {"num_rows": 1, "num_cols": 3, "table_cells": cells}}]
    payload["reading_order"].append("#/tables/0")
    fragments = rows(payload)
    assert {f["source_page"] for f in fragments} == {1}
    record = fragments.extraction_record
    assert record["navigation_pages"] == [2]
    assert record["exclusions"] == [{"item_ref": "#/tables/0", "reason": "docling_document_index_navigation",
                                     "provenance": prov}]
    assert record["document"]["tables"][0]["data"]["table_cells"] == cells

    empty = deepcopy(payload)
    for cell in empty["document"]["tables"][0]["data"]["table_cells"]:
        cell["text"] = " "
    with pytest.raises(DoclingError, match="page_text_unverified"):
        rows(empty)
    spanning = deepcopy(payload)
    spanning["document"]["tables"][0]["prov"].append(deepcopy(spanning["document"]["texts"][0]["prov"][0]))
    with pytest.raises(DoclingError, match="page_text_unverified"):
        rows(spanning)
    with_picture = deepcopy(payload)
    with_picture["document"]["pictures"] = [{"self_ref": "#/pictures/0", "label": "picture",
                                             "content_layer": "body", "prov": deepcopy(prov)}]
    with_picture["reading_order"].append("#/pictures/0")
    with pytest.raises(DoclingError, match="page_text_unverified"):
        rows(with_picture)
    only_index = deepcopy(payload)
    only_index["document"]["texts"] = []
    only_index["reading_order"] = ["#/tables/0"]
    with pytest.raises(DoclingError, match="no_source_text"):
        rows(only_index)


@pytest.mark.parametrize("all_text_missing, expected_code", [
    (False, "docling_page_text_unverified"),
    (True, "docling_no_source_text"),
])
def test_unverified_page_failure_is_durable_and_visible_without_partial_activation(tmp_path, monkeypatch, all_text_missing, expected_code, *, production_app, production_console):
    import hashlib
    import fitz
    from fastapi.testclient import TestClient
    from src.operations_console_v1 import OperationsConsole
    from src.operations_console_app import create_console_app
    import src.docling_pdf_v1 as adapter
    payload = result()
    payload["document"]["pages"]["2"] = {"size": {"width": 600, "height": 800}}
    if all_text_missing:
        payload["document"]["texts"] = []
        payload["reading_order"] = []
    with fitz.open() as document:
        document.new_page().insert_text((72, 72), "Brontekst.")
        document.new_page()
        data = document.tobytes()
    payload["source_sha256"] = hashlib.sha256(data).hexdigest()
    def controlled_extract(path, *, document_id, source_id, **kwargs):
        return translate(payload, document_id=document_id, source_id=source_id,
                         source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    monkeypatch.setattr(adapter, "extract", controlled_extract)
    def create():
        return production_console(processing_binder=lambda console: None, root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    console = create()
    author = console.create_account(username="author", password="test-secret-long", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="test-secret-long", roles=("reviewer",))
    command = dict(actor_id=author["account_id"], filename="source.pdf", data=data,
                   content_type="application/pdf", ingest_kind="new", title="Bron", version="1.0",
                   date="2026-10-04", live_url="", class_="richtlijn", family="test",
                   named_reviewers=[reviewer["account_id"]], command_id="missing-page")
    receipt = console.ingest(**command)
    sid = receipt["snapshot_id"]
    restarted = create()
    assert restarted.processing_status(sid)["state"] == "failed"
    assert restarted._envelope(sid)["processing_attempts"][-1]["error_code"] == expected_code
    assert not restarted.snapshot_objects(sid)
    assert stored_fragments(restarted._envelope(sid)) is None
    assert restarted._verified_source_bytes(restarted._envelope(sid))[1] == data
    assert restarted.ingest(**command)["snapshot_id"] == sid
    assert len(restarted._envelope(sid)["processing_attempts"]) == 1
    with TestClient(production_app(restarted), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "reviewer", "password": "test-secret-long"},
                           follow_redirects=False).status_code == 303
        response = client.get("/review/processing-diagnostics", params={"document": sid})
        assert response.status_code == 200
        pre_review = response.json()["pre_review"]
        assert pre_review["blocked"] and pre_review["object_count"] == 0
        assert pre_review["reason_code"] == expected_code
        assert "lege en gescande pagina’s" in pre_review["message"]
        diagnostic = restarted._envelope(sid)["processing_attempts"][-1]["diagnostic"]
        if all_text_missing:
            assert "unverified_pages" not in diagnostic
        else:
            # The failure names the page, never its text.
            assert diagnostic["unverified_pages"] == [2]
            page = client.get("/settings/technical/processing", params={"document": sid}).text
            assert "Pagina’s zonder verwerkbare brontekst: 2" in page
    # A long document's complete list is kept, never silently cut short.
    from src.attempt_diagnostics_v1 import finish_diagnostic
    from src.operations_console_v1 import ConsoleError
    error = ConsoleError("docling_page_text_unverified")
    error.unverified_pages = list(range(1, 1001))
    attempt = {"state": "failed", "error_code": "docling_page_text_unverified"}
    finish_diagnostic(attempt, error)
    assert attempt["diagnostic"]["unverified_pages"] == list(range(1, 1001))


def test_decision_tree_pdf_route_keeps_unverified_page_numbers_on_the_semantic_binding(tmp_path, monkeypatch, *, production_console):
    import src.decision_graph_v1 as decision_graph
    from src.operations_console_v1 import OperationsConsole, ConsoleError
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    def unverified(*args, **kwargs):
        error = DoclingError("docling_page_text_unverified")
        error.pages = [3]
        raise error
    monkeypatch.setattr(decision_graph, "pdf_fragments", unverified)
    console = production_console(processing_binder=lambda console: None, root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    bind_pre_review_semantic_processing(console, environ={"METIS_LLM_API_KEY": "k", "METIS_LLM_MODEL": "m"},
                                        post_json=lambda *a: pytest.fail("no model call before extraction"))
    with pytest.raises(ConsoleError) as raised:
        console._fragments_and_spec("pdf", tmp_path / "boom.pdf", data=b"%PDF", document_id="doc",
            source_id="src", title="Boom", family="test", class_="beslisboom")
    assert raised.value.code == "docling_page_text_unverified"
    assert raised.value.unverified_pages == [3]



def page(payload, number):
    payload["document"]["pages"][str(number)] = {"size": {"width": 600, "height": 800}}


def text_item(ref, text, *spans):
    """A body text item; each span is (page, start, end)."""
    return {"self_ref": ref, "text": text, "label": "text", "content_layer": "body",
            "prov": [{"page_no": number, "charspan": [start, end],
                      "bbox": {"l": 10, "t": 780, "r": 200, "b": 760, "coord_origin": "BOTTOMLEFT"}}
                     for number, start, end in spans]}


EMPTY = {"text_chars": 0, "images": 0, "drawings": 0}


def assessed(payload, **kwargs):
    return translate(payload, document_id="doc", source_id="src", source_sha256="a" * 64,
                     assess_pages=True, **kwargs)


def unresolved(payload, **kwargs):
    with pytest.raises(DoclingError, match="docling_pages_unresolved") as raised:
        assessed(payload, **kwargs)
    return raised.value.page_findings


def test_assessment_names_every_unresolved_page_in_one_pass():
    # Conceptrichtlijn Smetten: the first finding blocked all 46 pages, and each
    # repair only exposed the next. Every page finding is now named at once.
    payload = result()
    for number in range(2, 6):
        page(payload, number)
    prov = deepcopy(payload["document"]["texts"][0]["prov"][0])
    payload["document"]["tables"] = [{"self_ref": "#/tables/0", "label": "table",
         "prov": [dict(deepcopy(prov), page_no=3), dict(deepcopy(prov), page_no=4)],
         "data": {"num_rows": 1, "num_cols": 1, "table_cells": [{"text": "cel", "row_span": 1,
                  "col_span": 1, "start_row_offset_idx": 0, "start_col_offset_idx": 0}]}}]
    payload["document"]["texts"] += [text_item("#/texts/1", "goede tekst", (4, 0, 11)),
                                     text_item("#/texts/2", "kapotte tekst", (5, 0, 99))]
    payload["reading_order"] += ["#/tables/0", "#/texts/1", "#/texts/2"]
    with pytest.raises(DoclingError, match="multipage_table_mapping_unresolved"):
        rows(payload)
    findings = unresolved(payload)
    assert findings == [
        {"page": 2, "reasons": ["docling_page_text_unverified"]},
        {"page": 3, "reasons": ["docling_multipage_table_mapping_unresolved"]},
        {"page": 4, "reasons": ["docling_multipage_table_mapping_unresolved"]},
        {"page": 5, "reasons": ["docling_charspan_invalid"]},
    ]
    # Page numbers and codes only, never source text.
    assert "kapotte" not in json.dumps(findings)


def test_only_a_page_the_pdf_proves_empty_is_accepted_without_accounting():
    payload = result()
    page(payload, 2)
    fragments = assessed(payload, page_facts={1: {"text_chars": 9, "images": 0, "drawings": 0}, 2: EMPTY})
    assert {f["source_page"] for f in fragments} == {1}
    record = fragments.extraction_record
    assert record["page_assessment"] == "metis-docling-page-assessment-v1"
    assert record["set_aside_pages"] == [{"page": 2, "reasons": ["docling_page_text_unverified"],
                                          "basis": "pdf_page_without_content", "page_facts": EMPTY}]
    for facts in ({}, {2: dict(EMPTY, text_chars=40)}, {2: dict(EMPTY, images=1)}, {2: dict(EMPTY, drawings=3)}):
        assert unresolved(payload, page_facts=facts) == [{"page": 2, "reasons": ["docling_page_text_unverified"]}]
    # The strict rule is unchanged and keeps its exact code.
    with pytest.raises(DoclingError, match="docling_page_text_unverified"):
        rows(payload)


def test_a_page_with_only_an_inline_image_is_not_proven_empty(tmp_path):
    import fitz
    from src.docling_pdf_v1 import page_fact
    with fitz.open() as document:
        document.new_page()
        stream = document.get_new_xref()
        document.update_object(stream, "<<>>")
        document.update_stream(stream, b"q 100 0 0 100 50 50 cm BI /W 1 /H 1 /CS /G /BPC 8 ID \x00 EI Q")
        document.xref_set_key(document[0].xref, "Contents", f"{stream} 0 R")
        document.new_page()
        document.save(tmp_path / "inline.pdf")
    assert page_fact(tmp_path / "inline.pdf", 1)["images"] == 1
    assert page_fact(tmp_path / "inline.pdf", 2) == EMPTY
    with pytest.raises(DoclingError, match="docling_timeout"):
        page_fact(tmp_path / "inline.pdf", 2, deadline=0)


def test_scan_and_header_only_pages_are_not_treated_as_empty():
    payload = result()
    page(payload, 2)
    page(payload, 3)
    prov = deepcopy(payload["document"]["texts"][0]["prov"][0])
    payload["document"]["pictures"] = [{"self_ref": "#/pictures/0", "label": "picture", "content_layer": "body",
                                        "prov": [dict(deepcopy(prov), page_no=2)]}]
    footer = text_item("#/texts/1", "© Kennisinstituut", (3, 0, 17))
    footer.update(label="page_footer", content_layer="furniture")
    payload["document"]["texts"].append(footer)
    payload["reading_order"] += ["#/pictures/0", "#/texts/1"]
    # Even PDF facts that look empty do not overrule what Docling saw.
    assert unresolved(payload, page_facts={2: EMPTY, 3: EMPTY}) == [
        {"page": 2, "reasons": ["docling_page_non_text_content"]},
        {"page": 3, "reasons": ["docling_page_text_only_furniture"]},
    ]


def test_a_recorded_accounting_covers_only_its_exact_page_findings_and_source():
    payload = result()
    page(payload, 2)
    accounting = {"accounting_id": "spa_1", "page": 2, "reasons": ["docling_page_text_unverified"],
                  "source_sha256": "a" * 64, "category": "colofon_of_copyright", "note": "Alleen copyrighttekst.",
                  "actor_id": "acc-1", "recorded_at": "2026-10-22T22:00:00+00:00"}
    fragments = assessed(payload, accounted_pages=[accounting])
    assert {f["source_page"] for f in fragments} == {1}
    assert fragments.extraction_record["set_aside_pages"] == [{
        "page": 2, "reasons": ["docling_page_text_unverified"], "basis": "recorded_accounting",
        "accounting": {"accounting_id": "spa_1", "category": "colofon_of_copyright", "actor_id": "acc-1",
                       "recorded_at": "2026-10-22T22:00:00+00:00"}}]
    # The free-text note stays with the accounting, never in extraction evidence.
    assert "copyrighttekst" not in json.dumps(fragments.extraction_record["set_aside_pages"])
    for changed in (dict(accounting, page=3), dict(accounting, reasons=["docling_page_non_text_content"]),
                    dict(accounting, source_sha256="b" * 64)):
        assert unresolved(payload, accounted_pages=[changed])


def test_no_part_of_an_item_reaching_an_unusable_page_is_used():
    payload = result()
    for number in (2, 3, 4):
        page(payload, number)
    prov = deepcopy(payload["document"]["texts"][0]["prov"][0])
    payload["document"]["tables"] = [{"self_ref": "#/tables/0", "label": "table",
         "prov": [dict(deepcopy(prov), page_no=2), dict(deepcopy(prov), page_no=3)],
         "data": {"num_rows": 1, "num_cols": 1, "table_cells": [{"text": "cel", "row_span": 1,
                  "col_span": 1, "start_row_offset_idx": 0, "start_col_offset_idx": 0}]}}]
    payload["document"]["texts"].append(text_item("#/texts/1", "eerste tweede", (3, 0, 6), (4, 7, 13)))
    payload["reading_order"] += ["#/tables/0", "#/texts/1"]
    findings = unresolved(payload)
    assert findings == [
        {"page": 2, "reasons": ["docling_multipage_table_mapping_unresolved"]},
        {"page": 3, "reasons": ["docling_multipage_table_mapping_unresolved"]},
        {"page": 4, "reasons": ["docling_item_spans_set_aside_page"]},
    ]
    accounted = [{"page": row["page"], "reasons": row["reasons"], "source_sha256": "a" * 64} for row in findings]
    fragments = assessed(payload, accounted_pages=accounted)
    assert {f["source_page"] for f in fragments} == {1}
    assert [f["sequence"] for f in fragments] == [1]
    assert [b["fragment_id"] for b in fragments.extraction_record["bindings"]] == [f["fragment_id"] for f in fragments]


def test_a_heading_on_a_set_aside_page_never_enters_a_later_section_path():
    payload = result()
    for number in (2, 3):
        page(payload, number)
    heading = dict(text_item("#/texts/1", "Weggelaten kop", (2, 0, 14)), label="section_header", level=1)
    broken = text_item("#/texts/2", "onvolledig", (2, 0, 4))
    later = text_item("#/texts/3", "Latere tekst", (3, 0, 12))
    payload["document"]["texts"] += [heading, broken, later]
    payload["reading_order"] += ["#/texts/1", "#/texts/2", "#/texts/3"]
    findings = unresolved(payload)
    assert findings == [{"page": 2, "reasons": ["docling_text_coverage_incomplete"]}]
    accounted = [dict(findings[0], source_sha256="a" * 64)]
    fragments = assessed(payload, accounted_pages=accounted)
    assert {f["source_page"] for f in fragments} == {1, 3}
    assert all("Weggelaten kop" not in f["section_path"] for f in fragments)
    assert "#/texts/1" in [row["item_ref"] for row in fragments.extraction_record["exclusions"]
                           if row["reason"] == "docling_page_set_aside"]


@pytest.mark.parametrize("mutation, code", [
    (lambda p: p["document"]["texts"][0].update(prov=[]), "text_provenance_missing"),
    (lambda p: p["document"]["texts"][0]["prov"][0].update(page_no=9), "page_invalid"),
    (lambda p: p.update(reading_order=[]), "inventory_incomplete"),
    (lambda p: p.update(source_sha256="b" * 64), "result_identity_invalid"),
])
def test_unrecoverable_findings_still_reject_the_whole_extraction(mutation, code):
    payload = result()
    page(payload, 2)
    payload["document"]["texts"].append(text_item("#/texts/1", "tweede", (2, 0, 6)))
    payload["reading_order"].append("#/texts/1")
    mutation(payload)
    with pytest.raises(DoclingError, match=code):
        assessed(payload)


def test_unresolved_is_named_before_no_source_text_and_all_set_aside_is_no_source_text():
    payload = result()
    payload["document"]["texts"][0]["prov"][0]["charspan"] = [0, 99]
    assert unresolved(payload) == [{"page": 1, "reasons": ["docling_charspan_invalid"]}]
    with pytest.raises(DoclingError, match="no_source_text"):
        assessed(payload, accounted_pages=[{"page": 1, "reasons": ["docling_charspan_invalid"],
                                            "source_sha256": "a" * 64}])


def test_unresolved_page_blocks_formation_until_accounted_then_is_left_out(tmp_path, monkeypatch, *, production_app, production_console):
    import hashlib
    import fitz
    from fastapi.testclient import TestClient
    import src.docling_pdf_v1 as adapter
    from src.operations_console_v1 import ConsoleError
    payload = result()
    advice = "Beoordeel bij elke zorgvrager dagelijks de huidplooien op roodheid, vocht en schilfering."
    payload["document"]["texts"][0].update(text=advice, orig=advice)
    payload["document"]["texts"][0]["prov"][0]["charspan"] = [0, len(advice)]
    page(payload, 2)
    with fitz.open() as document:
        document.new_page().insert_text((72, 72), advice, fontsize=8)
        document.new_page().insert_text((72, 72), "Alle rechten voorbehouden.")
        data = document.tobytes()
    payload["source_sha256"] = hashlib.sha256(data).hexdigest()
    calls = []
    def controlled_extract(path, *, document_id, source_id, assess_pages=False, accounted_pages=None, **kwargs):
        calls.append(assess_pages)
        return translate(payload, document_id=document_id, source_id=source_id,
                         source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                         assess_pages=assess_pages, page_facts=lambda number: adapter.page_fact(Path(path), number),
                         accounted_pages=accounted_pages)
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    monkeypatch.setattr(adapter, "extract", controlled_extract)
    def create():
        return production_console(processing_binder=lambda console: None, root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    console = create()
    author = console.create_account(username="author", password="test-secret-long", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="test-secret-long", roles=("reviewer",))
    outsider = console.create_account(username="outsider", password="test-secret-long", roles=("reviewer",))
    receipt = console.ingest(actor_id=author["account_id"], filename="source.pdf", data=data,
                             content_type="application/pdf", ingest_kind="new", title="Bron", version="1.0",
                             date="2026-10-04", live_url="", class_="richtlijn", family="test",
                             named_reviewers=[reviewer["account_id"]], command_id="unresolved-page")
    sid = receipt["snapshot_id"]
    assert calls == [True]
    restarted = create()
    envelope = restarted._envelope(sid)
    attempt = envelope["processing_attempts"][-1]
    assert attempt["error_code"] == "docling_pages_unresolved"
    assert attempt["diagnostic"]["page_findings"] == [{"page": 2, "reasons": ["docling_page_text_unverified"]}]
    assert not restarted.snapshot_objects(sid)
    assert stored_fragments(envelope) is None
    command = dict(snapshot_id=sid, page=2, category="colofon_of_copyright", note="Alleen copyrighttekst, geen kennis.")
    with pytest.raises(ConsoleError, match="reviewer_not_named_on_snapshot"):
        restarted.account_source_page(actor_id=outsider["account_id"], **command)
    for bad, code in ((dict(command, page=1), "not_required"), (dict(command, category="x"), "category_invalid"),
                      (dict(command, note="kort"), "note_required")):
        with pytest.raises(ConsoleError, match=code):
            restarted.account_source_page(actor_id=reviewer["account_id"], **bad)
    assert "source_page_accountings" not in restarted._envelope(sid)
    with TestClient(production_app(restarted), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "reviewer", "password": "test-secret-long"},
                           follow_redirects=False).status_code == 303
        html = client.get("/inzicht/document", params={"document": sid}).text
        assert "Onopgeloste pagina’s" in html and "Pagina verantwoorden" in html
        assert "Docling vond op deze pagina geen tekst" in html
        assert "Alle rechten voorbehouden" not in html
        response = client.post("/inzicht/document/pagina-verantwoorden", data=command, follow_redirects=False)
        assert response.status_code == 303
        assert "Verantwoord; start de verwerking opnieuw." in client.get("/inzicht/document", params={"document": sid}).text
    with pytest.raises(ConsoleError, match="already_recorded"):
        restarted.account_source_page(actor_id=reviewer["account_id"], **command)
    # After the accounting, extraction passes and is checkpointed. This console
    # has no formation strategy, so formation then fails closed on its own terms.
    with pytest.raises(ConsoleError, match="source_processing_strategy_unconfigured"):
        restarted.retry_pre_review(actor_id=author["account_id"], snapshot_id=sid, command_id="after-accounting")
    assert calls == [True, True]
    retried = create()._envelope(sid)["processing_attempts"][-1]
    assert retried["error_code"] == "source_processing_strategy_unconfigured"
    assert "extraction_checkpoint" in [row["phase"] for row in retried["diagnostic"]["checkpoints"]]
    assert "page_findings" not in retried["diagnostic"]
    # The retained extraction that formation used leaves page 2 out on the recorded accounting.
    from src.source_preparation_context_v1 import stored_extraction
    extracted = stored_extraction(create()._envelope(sid))
    assert {f["source_page"] for f in extracted} == {1}
    assert [row["basis"] for row in extracted.extraction_record["set_aside_pages"]] == ["recorded_accounting"]
    # The diagnosis names the page the checkpointed extraction left out.
    from src.docling_contract_v1 import set_aside_pages
    assert [row["page"] for row in set_aside_pages(create()._envelope(sid))] == [2]
