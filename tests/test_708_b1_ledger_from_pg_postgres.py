"""#708 B1: after a commit the ledger mirror is projected from PostgreSQL.

The Storeopdracht owner MOET append the committed review events as read back
from workflow.review_events, not the process-local buffer copies, without a
full ledger scan. A mirror whose tail does not match the committed chain is
rebuilt from PostgreSQL. Rollback, U3 and U4 stay as proven in
test_678_store_command_postgres.py and test_708_reprocessing_guard_postgres.py.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import logging

import psycopg

from tests.complete_workflow_support import complete_postgres  # noqa: F401
from tests.test_678_store_command_postgres import _spy_mirror_writes_inside_transaction
from tests.test_708_reprocessing_guard_postgres import _assert_mirrors, _change_all, prepared  # noqa: F401
from tests.test_r2_rollback_remirror_postgres import _approve, _assert_disk_mirrors_equal_pg

LOGGER = "src.workflows.workflow_review_cutover_v1"


def _corrupt_buffer_and_count_full_reads(monkeypatch, console):
    """Change the buffered copies after the commit; count full ledger scans."""
    full_reads = []
    original_read = console.workflow_review_store.read_events

    def read_events():
        full_reads.append(True)
        return original_read()

    original_remirror = console._remirror_from_pg

    def remirror(command):
        assert command.events, "the command committed review events"
        for event in command.events:
            event["details"] = {**(event.get("details") or {}), "buffer_only": True}
        monkeypatch.setattr(console.workflow_review_store, "read_events", read_events)
        try:
            return original_remirror(command)
        finally:
            monkeypatch.setattr(console.workflow_review_store, "read_events", original_read)

    monkeypatch.setattr(console, "_remirror_from_pg", remirror)
    return full_reads


def test_committed_ledger_projection_reads_postgres_not_the_buffer(prepared, monkeypatch):
    console, reviewer, sid, obj = prepared
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    full_reads = _corrupt_buffer_and_count_full_reads(monkeypatch, console)
    _approve(console, reviewer, sid, obj)
    assert inside == []
    assert full_reads == [], "the projection MAG NIET scan the full ledger"
    assert "buffer_only" not in console._ledger_path.read_text(encoding="utf-8")
    _assert_mirrors(console, sid)


def test_unbuffered_reprocessing_events_are_projected_from_postgres(prepared, monkeypatch):
    console, reviewer, sid, obj = prepared
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    full_reads = _corrupt_buffer_and_count_full_reads(monkeypatch, console)
    with console._reprocessing_transaction(sid):
        _change_all(console, reviewer, sid, obj)
    assert inside == []
    assert full_reads == []
    assert "buffer_only" not in console._ledger_path.read_text(encoding="utf-8")
    _assert_mirrors(console, sid)


def _approve_first_and_pick_second(console, reviewer, sid, first):
    from src.proportionate_review_v1 import normal_risk_batch_queue
    queue = normal_risk_batch_queue(console.snapshot_objects(sid), review_path="richtlijn",
        fragments=console.review_source_fragments(sid), bindings=console.object_review_bindings(sid))
    second = next(obj for obj in queue if obj["object_id"] != first["object_id"])
    _approve(console, reviewer, sid, first)
    lines = console._ledger_path.read_text(encoding="utf-8").splitlines(keepends=True)
    assert lines
    return second, lines


def _assert_rebuilt_with_divergence_warning(console, caplog):
    _assert_disk_mirrors_equal_pg(console)
    messages = [record.getMessage() for record in caplog.records if record.name == LOGGER]
    assert any(m.startswith("store_command_ledger_divergence") for m in messages)
    assert not any(m.startswith("store_command_remirror_failed") for m in messages)


def test_stale_ledger_mirror_is_rebuilt_from_postgres_after_commit(prepared, caplog):
    console, reviewer, sid, first = prepared
    second, lines = _approve_first_and_pick_second(console, reviewer, sid, first)
    # A lost append from an earlier, already committed command.
    console._ledger_path.write_text("".join(lines[:-1]), encoding="utf-8")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    _approve(console, reviewer, sid, second)
    _assert_rebuilt_with_divergence_warning(console, caplog)


def test_tampered_mirror_tail_with_its_old_hash_is_not_an_anchor(prepared, caplog):
    console, reviewer, sid, first = prepared
    second, lines = _approve_first_and_pick_second(console, reviewer, sid, first)
    tail = json.loads(lines[-1])
    tail["details"] = {**(tail.get("details") or {}), "tampered": True}
    lines[-1] = json.dumps(tail, ensure_ascii=False, sort_keys=True) + "\n"
    console._ledger_path.write_text("".join(lines), encoding="utf-8")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    _approve(console, reviewer, sid, second)
    _assert_rebuilt_with_divergence_warning(console, caplog)


def test_committed_rows_failing_the_chain_check_are_not_copied(prepared, monkeypatch, caplog):
    console, reviewer, sid, obj = prepared
    before = console._ledger_path.read_bytes() if console._ledger_path.exists() else b""
    full_reads = []
    original_read = console.workflow_review_store.read_events
    original_remirror = console._remirror_from_pg

    def remirror(command):
        # The committed row changes in PostgreSQL without a matching event_hash.
        with psycopg.connect(console.workflow_document_store.config.dsn) as connection:
            connection.execute(
                "UPDATE workflow.review_events SET event_payload = "
                "jsonb_set(event_payload, '{details,tampered}', 'true') WHERE event_hash=%s",
                (command.events[-1]["event_hash"],),
            )
        monkeypatch.setattr(console.workflow_review_store, "read_events",
                            lambda: full_reads.append(True) or original_read())
        return original_remirror(command)

    monkeypatch.setattr(console, "_remirror_from_pg", remirror)
    caplog.set_level(logging.WARNING, logger=LOGGER)
    _approve(console, reviewer, sid, obj)
    assert full_reads == [], "a failed chain check MAG NIET trigger a full copy"
    assert console._ledger_path.read_bytes() == before
    messages = [record.getMessage() for record in caplog.records if record.name == LOGGER]
    assert any(m.startswith("store_command_remirror_failed") for m in messages)
    assert not any(m.startswith("store_command_ledger_divergence") for m in messages)
