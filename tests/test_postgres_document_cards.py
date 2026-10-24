"""D6a: source-selection key reads must not construct full document receipts.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_attempt_diagnostics_postgres import bound, ingest


def test_postgres_scoped_cards_never_construct_full_receipts(production_console, monkeypatch):
    console = production_console(processing_binder=bind_fixture_selections)
    bound(console, reject=False)
    sid, *_ = ingest(console)
    def forbidden(*args, **kwargs):
        raise AssertionError('card read constructed a full document receipt')
    monkeypatch.setattr(console, '_receipt', forbidden)
    monkeypatch.setattr(console.workflow_document_store, 'list_envelopes', forbidden)
    with console.document_read_operation():
        assert [row["snapshot_id"] for row in console.list_document_cards()] == [sid]
        assert console._envelope(sid)['snapshot_id'] == sid
        assert [row["snapshot_id"] for row in console.list_document_cards()] == [sid]


def test_scoped_cards_do_not_alias_the_process_cache(production_console):
    """#803 P2: another operation's refresh/delete must not change this request's observation."""
    console = production_console(processing_binder=lambda console: None)
    bound(console, reject=False)
    sid, *_ = ingest(console)
    with console.document_read_operation():
        assert [row["snapshot_id"] for row in console.list_document_cards()] == [sid]
        assert console._document_reads().envelopes is not console._envelopes
        console._envelopes.clear()
        console._envelopes['other-operation'] = {'snapshot_id': 'other-operation'}
        assert [row["snapshot_id"] for row in console.list_document_cards()] == [sid]
        assert console._envelope(sid)['snapshot_id'] == sid
