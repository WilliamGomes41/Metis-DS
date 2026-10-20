"""D6a: source-selection key reads must not construct full document receipts.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from tests.test_attempt_diagnostics_postgres import bound, ingest


def test_postgres_scoped_key_list_never_constructs_full_receipts(production_console, monkeypatch):
    console = production_console(processing_binder=lambda console: None)
    bound(console, reject=False)
    sid, *_ = ingest(console)
    def forbidden(*args, **kwargs):
        raise AssertionError('key-only read constructed a full document receipt')
    monkeypatch.setattr(console, '_receipt', forbidden)
    with console.source_selection_read_scope():
        assert console.list_snapshot_ids() == [sid]
        assert console._envelope(sid)['snapshot_id'] == sid
        assert console.list_snapshot_ids() == [sid]
