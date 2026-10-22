"""D6a: source-selection key reads must not construct full document receipts.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_attempt_diagnostics_postgres import bound, ingest


def test_postgres_scoped_key_list_never_constructs_full_receipts(production_console, monkeypatch):
    console = production_console(processing_binder=bind_fixture_selections)
    bound(console, reject=False)
    sid, *_ = ingest(console)
    def forbidden(*args, **kwargs):
        raise AssertionError('key-only read constructed a full document receipt')
    monkeypatch.setattr(console, '_receipt', forbidden)
    with console.source_selection_read_scope():
        assert console.list_snapshot_ids() == [sid]
        assert console._envelope(sid)['snapshot_id'] == sid
        assert console.list_snapshot_ids() == [sid]


def test_scoped_key_list_does_not_alias_the_process_cache(production_console):
    """#803 P2: another operation's refresh/delete must not change this request's observation."""
    console = production_console(processing_binder=lambda console: None)
    bound(console, reject=False)
    sid, *_ = ingest(console)
    with console.source_selection_read_scope():
        assert console.list_snapshot_ids() == [sid]
        assert console._source_selection_reads()['envelopes'] is not console._envelopes
        console._envelopes.clear()
        console._envelopes['other-operation'] = {'snapshot_id': 'other-operation'}
        assert console.list_snapshot_ids() == [sid]
        assert console._envelope(sid)['snapshot_id'] == sid
