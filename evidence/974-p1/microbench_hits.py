"""#974 P1 micro-benchmark: one build and the per-hit cost of _read_source_blocks.

Run: cp evidence/974-p1/microbench_hits.py tests/p1_micro_tmp.py
     python -m pytest -q -s tests/p1_micro_tmp.py; rm tests/p1_micro_tmp.py
Compares the stored HTML extraction (plain list, as on trunk) with the same
rows frozen once (head), and a PDF-shaped variant whose rows carry numeric
bbox/page fields like Docling fragments, where trunk's deep comparison
through _SourceNumber is far more expensive.
"""
import time
from copy import deepcopy
from tests.semantic_fixture_support import bind_fixture_selections


def test_microbench(tmp_path, production_console):
    import src.vorming.knowledge_materialisation_v1 as km
    from src.vorming.prepared_source_views_v1 import freeze_extraction
    from src.vorming.source_preparation_context_v1 import stored_extraction
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg." for i in range(2000)]
    bind_fixture_selections(console, [(t, "definition") for t in texts[:200]])
    sid = console.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{t}</p>" for t in texts) + "</body></html>").encode(),
        ingest_kind="new", title="P", version="1.0", date="2026-11-04", live_url="",
        class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    plain = stored_extraction(console._processing_history_envelope(sid))
    frozen = freeze_extraction(deepcopy(plain))
    pdfish = deepcopy(plain)
    for i, row in enumerate(pdfish):
        row["bbox"] = [72.0 + i % 7, 100.5, 523.25, 140.75]; row["source_page"] = 1 + i // 40
        row["spans"] = [{"bbox": [72.0, 100.5 + k, 300.25, 110.75], "font_size": 10.5, "page": 1 + i // 40} for k in range(4)]
    for name, rows in (("plain", plain), ("frozen", frozen), ("pdfish-plain", pdfish), ("pdfish-frozen", freeze_extraction(deepcopy(pdfish)))):
        for heads in (False, True):
            with km.source_reconstruction_scope():
                t = time.perf_counter(); km._read_source_blocks(rows, include_headings=heads); b = time.perf_counter() - t
                t = time.perf_counter()
                for _ in range(20):
                    km._read_source_blocks(km.preserve_fragments(rows), include_headings=heads)
                h = (time.perf_counter() - t) / 20
            print(f"TIMING {name} headings={heads} build_ms={b*1000:.1f} hit_ms={h*1000:.3f}")
