"""#974 design prototype: cost of repeated source reads per formation validator.

Run (needs the tests/conftest.py fixtures and a test PostgreSQL):
    cp evidence/974-design/prototype_source_reads.py tests/proto_974_tmp.py
    python -m pytest -q -s tests/proto_974_tmp.py; rm tests/proto_974_tmp.py
Compares, for one ingested document, N validator-style reads of the full source
view through the unchanged `_read_source_blocks`:
  current  plain list from the stored extraction (formation detail today)
  A        the existing prepared SourceFragments carrier (Review's reader)
  B        a deep-frozen list with an identity fast path (prototype patch only)
"""
import time
from copy import deepcopy

import pytest

from src.vorming import knowledge_materialisation_v1 as km
from src.vorming.prepared_source_views_v1 import FrozenList, freeze
from src.vorming.source_preparation_context_v1 import stored_extraction
from tests.test_navigation_source_reuse import bind_fixture_selections

PARAGRAPHS, CALLS = 2000, 200


def _timed(fragments, calls, keep=False):
    # Callers pass preserve_fragments(...): a copy for plain lists. Design B
    # would make preserve_fragments keep a FrozenList, modelled by keep=True.
    with km.source_reconstruction_scope():
        start = time.perf_counter()
        for _ in range(calls):
            km._read_source_blocks(fragments if keep else km.preserve_fragments(fragments), include_headings=True)
        return (time.perf_counter() - start) / calls * 1000


def test_prototype(tmp_path, production_console, monkeypatch):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg." for i in range(PARAGRAPHS)]
    bind_fixture_selections(console, [(text, "definition") for text in texts[:5]])
    sid = console.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{t}</p>" for t in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Prototype 974", version="1.0", date="2026-11-04", live_url="",
        class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    envelope = console._processing_history_envelope(sid)
    plain = stored_extraction(envelope)
    from src.console_performance_v1 import performance_scope
    t0 = time.perf_counter()
    with performance_scope() as metrics:
        carrier = console._prepared_review_source(console._envelope(sid))
    load_a = (time.perf_counter() - t0) * 1000
    a_bytes = metrics.json_bytes
    assert carrier is not None and len(plain) == len(carrier)
    current = _timed(plain, 20)

    a = _timed(carrier, CALLS)

    t0 = time.perf_counter(); frozen = freeze(deepcopy(plain)); freeze_ms = (time.perf_counter() - t0) * 1000
    cache = {}
    real = km._read_source_blocks
    def identity_first(fragments, *, include_headings=False):
        if isinstance(fragments, FrozenList):
            key = (id(fragments), include_headings)
            if key not in cache:
                cache[key] = (fragments, real(fragments, include_headings=include_headings))
            return cache[key][1]
        return real(fragments, include_headings=include_headings)
    monkeypatch.setattr(km, '_read_source_blocks', identity_first)
    b = _timed(frozen, CALLS, keep=True)
    print(f"\nPROTOTYPE fragments={len(plain)} per-call-ms current={current:.2f} A={a:.4f} B={b:.4f} "
          f"one-time-ms A_load={load_a:.1f} A_json_bytes={a_bytes} B_freeze={freeze_ms:.1f} "
          f"projected-945-calls-s current={current*945/1000:.1f} A={(a*945+load_a)/1000:.2f} "
          f"B_first_build_plus_hits={(b*CALLS+freeze_ms)/1000:.2f}")
