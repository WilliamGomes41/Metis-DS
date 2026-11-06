"""Display-only source capture shares I/O without widening semantic evidence.

# release-control-evidence: scope/belofte opslag toegang metrics slop releasebewijs
"""
from src.console_performance_v1 import performance_scope
from src.review.review_passage_read_v1 import read_review_passage
from src.workflows.formation_task_store_v1 import FormationTaskStore
from tests.test_ko_receipt_ui import prepared
from tests.test_review_command_bounded_http_v1 import physical_state


def test_prefetch_reuses_source_connection_with_identical_logical_window(tmp_path, production_console, monkeypatch):
    source = (b'<html><body><h1>Richtlijn</h1><h2>Huidzorg</h2><p>Gebruik geen zalf.</p>'
              b'<p>Controleer dagelijks de huid.</p><h2>Evaluatie</h2><p>Evalueer morgen.</p></body></html>')
    console, sid, reviewer, obj, _, _, _ = prepared(tmp_path, production_console, monkeypatch, source_html=source)
    inputs = read_review_passage(console, console._account(reviewer), sid, obj['object_id'])
    owner = FormationTaskStore(console.workflow_document_store)
    before = physical_state(console, sid)
    with performance_scope() as old_cost:
        ordinary = owner.read_review_source(inputs.envelope, objects=inputs.objects)
        old_display = owner.read_review_document_context(inputs.envelope, obj, source=ordinary)
    with performance_scope() as cost:
        prefetched = owner.read_review_source(inputs.envelope, objects=inputs.objects, display_target=obj)
        display = owner.read_review_document_context(inputs.envelope, obj, source=prefetched)
    assert cost.connections == old_cost.connections - 1 == 1
    assert cost.queries == old_cost.queries
    assert display == old_display
    assert prefetched.root.raw == ordinary.root.raw
    assert prefetched.root.payload == ordinary.root.payload
    assert prefetched.root.reference == ordinary.root.reference
    assert prefetched.root.complete == ordinary.root.complete is False
    assert prefetched.root.fragment_ordinals == ordinary.root.fragment_ordinals
    for name, carrier in ordinary.root.carriers.items():
        assert list(prefetched.root.carriers[name]) == list(carrier)
        assert list(prefetched.root.carriers[name].blocks) == list(carrier.blocks)
    assert any(row.get('clean_text') == 'Evaluatie' for row in display.fragments)
    assert not any(row.get('clean_text') == 'Evalueer morgen.' for row in display.fragments)
    assert physical_state(console, sid) == before


def test_uncaptured_target_uses_existing_verified_display_read(tmp_path, production_console, monkeypatch):
    console, sid, reviewer, obj, _, _, _ = prepared(tmp_path, production_console, monkeypatch)
    inputs = read_review_passage(console, console._account(reviewer), sid, obj['object_id'])
    owner = FormationTaskStore(console.workflow_document_store)
    source = owner.read_review_source(inputs.envelope, objects=inputs.objects, display_target=obj)
    changed = {**obj, 'object_id': 'different-target'}
    with performance_scope() as cost:
        display = owner.read_review_document_context(inputs.envelope, changed, source=source)
    assert cost.connections == 1 and cost.queries == 1
    assert display.target_object_id == 'different-target'
    assert display.focal_fragment_ids == source.root.review_document_context.focal_fragment_ids


def test_existing_request_source_cache_is_reused_without_sidecar_recapture(tmp_path, production_console, monkeypatch):
    from src.console_read_snapshot_v1 import CURRENT_READ, ConsoleReadSnapshot
    console, sid, reviewer, obj, _, _, _ = prepared(tmp_path, production_console, monkeypatch)
    inputs = read_review_passage(console, console._account(reviewer), sid, obj['object_id'])
    token = CURRENT_READ.set(ConsoleReadSnapshot(console))
    try:
        source = console._prepared_review_source(inputs.envelope, objects=inputs.objects)
        assert source.root.review_document_context is None
        with performance_scope() as cost:
            reused = console._prepared_review_source(inputs.envelope, objects=inputs.objects, display_target=obj)
        assert reused is source and reused.root.review_document_context is None
        assert cost.connections == cost.queries == 0
        with performance_scope() as display_cost:
            display = FormationTaskStore(console.workflow_document_store).read_review_document_context(
                inputs.envelope, obj, source=reused)
        assert display and display_cost.connections == display_cost.queries == 1
    finally:
        CURRENT_READ.reset(token)


def test_display_prefetch_never_reconstructs_or_reads_original_inside_workflow_transaction(
        tmp_path, production_console, monkeypatch):
    from src.vorming import semantic_passage_v1, source_reconstruction_v1
    from src.workflows.workflow_transaction_v1 import workflow_transaction_active
    console, sid, reviewer, obj, _, _, _ = prepared(tmp_path, production_console, monkeypatch)
    before = physical_state(console, sid)

    def no_reconstruction(*args, **kwargs):
        raise AssertionError('Display capture must use raw verified source rows')

    monkeypatch.setattr(semantic_passage_v1, '_reconstructed_blocks', no_reconstruction)
    monkeypatch.setattr(source_reconstruction_v1, 'reconstruct_source_fragments', no_reconstruction)
    verified = console._verified_source_bytes

    def verify_original(*args, **kwargs):
        assert not workflow_transaction_active()
        return verified(*args, **kwargs)

    monkeypatch.setattr(console, '_verified_source_bytes', verify_original)
    inputs = read_review_passage(console, console._account(reviewer), sid, obj['object_id'],
                                 include_document_context=True)
    assert inputs.fragments.root.review_document_context is not None
    assert physical_state(console, sid) == before
