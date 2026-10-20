"""Lex #667 F1/I2 fail-first test (rood op 6a3fb52). Voor Forge om op te nemen in #667."""
"""Lex adversarial review #667 (sandbox only, synthetic data). Not for merge."""
import logging
import threading

import pytest

from src.workflows import workflow_review_cutover_v1 as rc
from tests.complete_workflow_support import complete_postgres as workflow_postgres  # noqa: F401
from tests.test_r2_rollback_remirror_postgres import (
    _setup, _approve, _state, _ledger_state_bytes, _console, _inject_fault,
    _assert_review_authority_without_mirrors,
)


def _orphans(console, sid):
    """Events whose (object_id, object_version) has no binding in PG."""
    bindings = console.workflow_review_store.read_bindings()
    bound = {(b.get("object_id"), str(b.get("object_version"))) for rows in bindings.values() for b in rows}
    out = []
    for e in console.workflow_review_store.read_events():
        if e.get("event_type", "").startswith("review") or "approve" in str(e.get("details", {})):
            if (e.get("object_id"), str(e.get("object_version"))) not in bound:
                out.append((e.get("event_type"), e.get("object_id")))
    return out



def test_adv_i2_caught_nested_fault_leaves_no_orphan_event(workflow_postgres, tmp_path):
    """I2/R1: caller catches an inner fault after an approve and continues.
    The inner savepoint rolls back the binding; the shared event buffer MAG NIET
    still flush the approve's audit event at the outer commit."""
    console, rid, sid, (obj_a, _b) = _setup(tmp_path, workflow_postgres)
    ev0 = console.workflow_review_store.read_events()
    b0 = console.workflow_review_store.read_bindings()
    with console._atomic_snapshot_mutation(sid):
        try:
            with console._atomic_snapshot_mutation(sid):
                _approve(console, rid, sid, obj_a)
                raise RuntimeError("lex_caught_inner")
        except RuntimeError:
            pass
    ev1 = console.workflow_review_store.read_events()
    b1 = console.workflow_review_store.read_bindings()
    new = [(e.get("event_type"), e.get("object_id")) for e in ev1[len(ev0):]]
    print("ADV_I2", {"events_before": len(ev0), "events_after": len(ev1), "new_events": new,
                     "bindings_changed": b0 != b1})
    assert b1 == b0, "inner binding MOET be rolled back"
    assert len(ev1) == len(ev0), f"orphan audit event(s) flushed after caught inner fault: {new}"
