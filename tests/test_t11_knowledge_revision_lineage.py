"""T11 behavioral regressions through existing commands (no invented RED API).
# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import pytest

from src.integrity_kernel import compute_canonical_object_hash
from src.operations_console_v1 import OperationsConsole, ConsoleError
from src.review_duty_v1 import exact_current_approver_ids
from tests.test_t9_review_knowledge_authority import _console, _approve
from tests.test_source_context_review_v1 import _system


def current(console, sid, oid):
    return next(o for o in console.snapshot_objects(sid) if o["object_id"] == oid)


def test_review_type_revision_has_real_predecessor_and_preserves_history(tmp_path):
    console, reviewer, sid, before = _console(tmp_path)
    original = deepcopy(before)
    _approve(console, reviewer, sid, before)
    after = current(console, sid, before["object_id"])
    assert after["object_version"] != original["object_version"]
    assert original in console.snapshot_objects(sid, include_blocked=True)
    assert after["provenance"]["previous_object_version"] == original["object_version"]
    assert after["provenance"]["revision_reason"]
    assert after["provenance"]["revision_patch_hash"]
    bindings = console.object_review_bindings(sid)
    assert exact_current_approver_ids(after, bindings) == (reviewer["account_id"],)


def test_source_context_target_has_explicit_predecessor(tmp_path):
    console, _, _, source, before, command = _system(tmp_path)
    console.confirm_source_context(**command)
    after = current(console, command["snapshot_id"], before["object_id"])
    assert before in console.snapshot_objects(command["snapshot_id"], include_blocked=True)
    assert after["object_version"] != before["object_version"]
    assert after["provenance"]["previous_object_version"] == before["object_version"]
    assert after["provenance"]["revision_reason"]
    assert after["provenance"]["revision_patch_hash"]


@pytest.mark.parametrize("new_version", ["1.0", "0.9"])
def test_correction_cannot_reuse_or_decrease_version(tmp_path, new_version):
    console, reviewer, sid, obj = _console(tmp_path)
    console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
        object_id=obj["object_id"], decision="revise", comment="Expliciete correctie.")
    before = deepcopy(console.snapshot_objects(sid, include_blocked=True))
    with pytest.raises((ValueError, ConsoleError)):
        console.correct_object(actor_id=reviewer["account_id"], snapshot_id=sid,
            object_id=obj["object_id"], patch={"reason": "Correctie",
            "new_object_version": new_version,
            "operations": [{"op": "set", "path": "content.clean_text",
                            "value": obj["content"]["clean_text"]}]},
            expected_revision=console.objects_revision(sid))
    assert console.snapshot_objects(sid, include_blocked=True) == before


def test_unchanged_review_retry_keeps_revision_and_legacy_history(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj)
    rows = deepcopy(console.snapshot_objects(sid, include_blocked=True))
    token = console.objects_revision(sid)
    _approve(console, reviewer, sid, obj)
    assert console.objects_revision(sid) == token
    assert console.snapshot_objects(sid, include_blocked=True) == rows
    restarted = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert restarted.snapshot_objects(sid, include_blocked=True) == rows


def test_stale_review_writes_nothing(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    stale = console.objects_revision(sid)
    _approve(console, reviewer, sid, obj)
    rows = deepcopy(console.snapshot_objects(sid, include_blocked=True))
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        _approve(console, reviewer, sid, obj, expected_revision=stale)
    assert console.snapshot_objects(sid, include_blocked=True) == rows
