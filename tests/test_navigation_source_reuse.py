"""#544: full-source navigation work stays bounded without changing review truth.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_console_navigation_performance import NavigationProbe


@pytest.fixture
def source_navigation(tmp_path, *, production_console):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path, source_store=tmp_path / "source",
                                   runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming." for i in range(20)]
    bind_fixture_selections(console, [(text, "definition") for text in texts])
    sid = console.ingest(
        actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{text}</p>" for text in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Navigation proof", version="1.0", date="2026-10-08",
        live_url="", class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]],
    )["snapshot_id"]
    probe = NavigationProbe(count=0, documents=1)
    probe.objects["synthetic-0"] = console.snapshot_objects(sid)
    fragments = console.review_source_fragments(sid)
    probe.review_source_fragments = lambda *args, **kwargs: deepcopy(fragments)
    return probe, fragments


def test_navigation_reconstructs_each_source_once_per_call(source_navigation, monkeypatch):
    import src.vorming.semantic_passage_v1 as semantic
    probe, fragments = source_navigation
    before = deepcopy((probe.objects, probe.envelopes, probe.bindings, fragments))
    original = semantic._reconstructed_blocks
    calls = []

    def counted(rows):
        from src.vorming.prepared_source_views_v1 import preserve_fragments
        rows = preserve_fragments(rows)
        if rows:
            calls.append(1)
        return original(rows)

    monkeypatch.setattr(semantic, "_reconstructed_blocks", counted)
    for expected_calls in (1, 2):
        assert probe.waiting_task_counts("reviewer-1")["review"] == 1
        assert len(calls) == expected_calls
    assert before == (probe.objects, probe.envelopes, probe.bindings, fragments)


@pytest.mark.parametrize("change", ["none", "candidate_text", "source_text"])
def test_complete_work_item_matches_uncached_validation(source_navigation, change):
    from src.review.review_workboard_v1 import ReviewWorkInputs, review_work_item
    probe, fragments = source_navigation
    sid = "synthetic-0"
    if change == "candidate_text":
        candidate = next(obj for obj in probe.objects[sid] if obj.get("metadata", {}).get("semantic_passage", {}).get("spans"))
        candidate["content"]["clean_text"] = "Dit staat niet in de bron."
    elif change == "source_text":
        fragments[0]["clean_text"] = "Gewijzigde bron."
        fragments[0]["raw_text"] = "Gewijzigde bron."
    before = deepcopy((probe.objects, fragments))
    args = dict(account=probe.account, envelope=probe.envelopes[sid],
                inputs=ReviewWorkInputs(probe.objects[sid], [],
                                        probe.document_lifecycle_status(sid), False))
    expected = review_work_item.__wrapped__(probe, **args)
    assert review_work_item(probe, **args) == expected
    assert before == (probe.objects, fragments)


def test_source_changes_nested_scope_and_failure_do_not_reuse_stale_blocks(source_navigation, monkeypatch):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    probe, fragments = source_navigation
    obj = next(obj for obj in probe.objects["synthetic-0"] if obj.get("metadata", {}).get("semantic_passage", {}).get("spans"))
    spans = obj["metadata"]["semantic_passage"]["spans"]
    original = materialisation._selection_blocks
    calls = []

    def counted(rows):
        calls.append(1)
        return original(rows)

    monkeypatch.setattr(materialisation, "_selection_blocks", counted)

    def resolve():
        return materialisation.resolve_source_selection(spans, fragments=fragments)

    with materialisation.source_reconstruction_scope():
        expected = resolve()
        assert resolve() == expected
        assert len(calls) == 1
        with pytest.raises(RuntimeError, match="scope failure"):
            with materialisation.source_reconstruction_scope():
                assert resolve() == expected
                raise RuntimeError("scope failure")
        assert resolve() == expected
        assert len(calls) == 2
        fragments[-1]["fragment_hash"] = "changed-source-hash"
        resolve()
        assert len(calls) == 3
    resolve()
    resolve()
    assert len(calls) == 5  # No reuse leaks into subsequent independent reads.


def test_reuse_never_caches_candidate_approval(source_navigation):
    from src.vorming.knowledge_materialisation_v1 import source_reconstruction_scope
    from src.review.knowledge_path_v1 import source_lineage_resolves
    probe, fragments = source_navigation
    obj = next(obj for obj in probe.objects["synthetic-0"] if obj.get("metadata", {}).get("semantic_passage", {}).get("spans"))
    original = deepcopy(obj)
    with source_reconstruction_scope():
        assert source_lineage_resolves(obj, fragments=fragments)
        obj["content"]["clean_text"] = "Niet door deze bron onderbouwd."
        assert not source_lineage_resolves(obj, fragments=fragments)
        assert source_lineage_resolves(original, fragments=fragments)


@pytest.mark.parametrize("original,replacement", [(1, True), (1, 1.0), (-0.0, 0.0)])
def test_source_scalar_type_changes_do_not_reuse_prior_representation(source_navigation, original, replacement):
    import src.vorming.knowledge_materialisation_v1 as materialisation

    _, fragments = source_navigation
    fragments[0]["source_page"] = original
    with materialisation.source_reconstruction_scope():
        initial = materialisation._read_source_blocks(fragments)
        fragments[0]["source_page"] = replacement
        changed = materialisation._read_source_blocks(fragments)
        assert changed is not initial
        source = next(iter(changed.values()))[1]
        assert type(source["source_page"]) is type(replacement)


def test_parallel_work_items_have_independent_source_scopes(source_navigation, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, get_ident
    import src.vorming.knowledge_materialisation_v1 as materialisation
    from src.review.knowledge_path_v1 import source_lineage_resolves
    probe, fragments = source_navigation
    obj = next(obj for obj in probe.objects["synthetic-0"] if obj.get("metadata", {}).get("semantic_passage", {}).get("spans"))
    original = materialisation._selection_blocks
    calls = []
    barrier = Barrier(2)

    def counted(rows):
        calls.append(get_ident())
        return original(rows)

    monkeypatch.setattr(materialisation, "_selection_blocks", counted)

    def read():
        with materialisation.source_reconstruction_scope():
            assert source_lineage_resolves(obj, fragments=fragments)
            barrier.wait(timeout=5)
            assert source_lineage_resolves(obj, fragments=fragments)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(read) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)
    assert len(calls) == len(set(calls)) == 2


def test_context_and_source_projection_share_views_without_caching_validation(monkeypatch):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    import src.vorming.semantic_passage_v1 as semantic
    from src.vorming.source_containers_v1 import source_accountability
    from src.vorming.source_accountability_v1 import is_source_record
    from src.review.source_context_review_v1 import verify_literal_source
    from tests.test_source_containers_v1 import context_story
    from tests.test_t10_source_accountability_authority import _context_inputs

    objects = context_story()
    _, fragments = _context_inputs()
    original = semantic._reconstructed_blocks
    calls = []

    def counted(rows):
        calls.append(1)
        return original(rows)

    monkeypatch.setattr(semantic, "_reconstructed_blocks", counted)
    monkeypatch.setattr(materialisation, "_reconstructed_blocks", counted)
    with materialisation.source_reconstruction_scope():
        projection = source_accountability(objects, fragments=fragments)
        assert any(row["kind"] == "linked_context" for row in projection.values())
        assert len(calls) <= 2
        prior_calls = len(calls)
        candidate = next(obj for obj in objects if obj.get("metadata", {}).get("source_bound_context"))
        candidate["content"]["clean_text"] += " niet in de bron"
        invalid = source_accountability(objects, fragments=fragments)
        assert invalid[candidate["object_id"]]["kind"] == "invalid_evidence"
        assert len(calls) == prior_calls
        source = next(obj for obj in objects if is_source_record(obj))
        assert verify_literal_source(source, fragments, source["source"]["source_checksum"])
        source["metadata"]["semantic_passage"]["source_mapping"] = []
        assert not verify_literal_source(source, fragments, source["source"]["source_checksum"])


def test_full_source_keeps_headings_and_input_changes_invalidate_both_views(source_navigation, monkeypatch):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    from src.review.knowledge_path_v1 import source_lineage_resolves
    from src.vorming.source_bound_fields_v2 import bind_context
    from src.vorming.semantic_passage_v1 import semantic_source_blocks

    probe, fragments = source_navigation
    candidate = next(obj for obj in probe.objects["synthetic-0"]
                     if obj.get("metadata", {}).get("semantic_passage", {}).get("spans"))
    heading = {"fragment_id": "heading", "fragment_hash": "heading-hash",
               "raw_text": "Toepassingsgebied", "clean_text": "Toepassingsgebied",
               "object_type": "heading", "section_path": ["Toepassingsgebied"]}
    fragments = [heading, *deepcopy(fragments)]
    block = semantic_source_blocks(fragments)[0]
    context = [{"role": "scope", "span": {"block_id": block["block_id"], "start": 0,
                "end": len(block["text"])}, "unresolved_reason": None}]
    original = materialisation._reconstructed_blocks
    calls = []

    def counted(rows):
        calls.append(1)
        return original(rows)

    monkeypatch.setattr(materialisation, "_reconstructed_blocks", counted)
    with materialisation.source_reconstruction_scope():
        for _ in range(2):
            assert source_lineage_resolves(candidate, fragments=fragments)
            assert bind_context(context, fragments=fragments)[0]["text"] == heading["clean_text"]
        assert len(calls) == 2
        heading["raw_text"] = heading["clean_text"] = "Gewijzigd toepassingsgebied"
        assert source_lineage_resolves(candidate, fragments=fragments)
        with pytest.raises(ValueError, match="source_bound_context_unknown_block"):
            bind_context(context, fragments=fragments)
        assert len(calls) == 4
    # Direct independent operations do not inherit the read's reusable views.
    assert source_lineage_resolves(candidate, fragments=fragments)
    assert source_lineage_resolves(candidate, fragments=fragments)
    assert len(calls) == 6


def test_source_accountability_reads_source_once_with_unchanged_outcome(tmp_path, monkeypatch, *, production_console):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    import src.review.source_context_review_v1 as context_review
    from src.vorming.source_accountability_v1 import is_source_record
    from src.vorming.source_containers_v1 import source_accountability
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path, source_store=tmp_path / "source",
                                   runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming." for i in range(20)]
    bind_fixture_selections(console, [(text, "definition") for text in texts[:2]])
    sid = console.ingest(
        actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{text}</p>" for text in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Source records", version="1.0", date="2026-10-18",
        live_url="", class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]],
    )["snapshot_id"]
    objects = console.snapshot_objects(sid)
    fragments = console.review_source_fragments(sid)
    assert sum(map(is_source_record, objects)) >= 15

    original_verify = context_review.verify_literal_source
    monkeypatch.setattr(context_review, "verify_literal_source",
                        lambda obj, rows, source_hash, **_: original_verify(obj, rows, source_hash))
    expected = source_accountability(objects, fragments=fragments)
    monkeypatch.setattr(context_review, "verify_literal_source", original_verify)

    original_read = materialisation._read_source_blocks
    full_reads = []

    def counted(rows, *, include_headings=False):
        full_reads.append(include_headings)
        return original_read(rows, include_headings=include_headings)

    monkeypatch.setattr(materialisation, "_read_source_blocks", counted)
    assert source_accountability(objects, fragments=fragments) == expected
    assert full_reads.count(True) == 1
