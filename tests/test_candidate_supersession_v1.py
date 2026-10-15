"""A3-3: superseded candidates are retained, lose approvals and are refused at the gate.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag stale retry version-compat recovery concurrent
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import threading
from copy import deepcopy

import pytest

from src.candidate_supersession_v1 import REASON_CODE, supersede_for_contract_change
from src.revision_workflow import current_revisions
from tests.test_durable_publication_console_v1 import MemoryCanonicalStore, _ready_console


@pytest.fixture
def ready(tmp_path):
    console, accounts, receipt = _ready_console(tmp_path, MemoryCanonicalStore())
    sid, publisher = receipt['snapshot_id'], accounts['publisher']['account_id']
    verdict = console.consider_publish(actor_id=publisher, snapshot_id=sid)
    assert verdict['publish_allowed'], verdict.get('blockers')
    return console, sid, publisher, verdict


def _with_superseded(console, sid, verdict):
    approved = set(verdict['publishable_object_ids'])
    objects = deepcopy(console.snapshot_objects(sid))
    bindings = deepcopy(console.object_review_bindings(sid, objects=console.snapshot_objects(sid)))
    target = next(o for o in objects if o['object_id'] in approved)
    target['governance']['validation_status'] = 'superseded'
    console.snapshot_objects = lambda *_a, **_k: deepcopy(objects)
    console.object_review_bindings = lambda *_a, **_k: deepcopy(bindings)
    return target['object_id']


def test_gate_refuses_superseded_approved_candidate_with_one_reason_code(ready):
    console, sid, publisher, verdict = ready
    _with_superseded(console, sid, verdict)
    refused = console.consider_publish(actor_id=publisher, snapshot_id=sid)
    assert not refused['publish_allowed']
    assert refused['blockers'].count(REASON_CODE) == 1


def test_publish_is_refused_for_superseded_candidate(ready):
    console, sid, publisher, verdict = ready
    _with_superseded(console, sid, verdict)
    result = console.publish(actor_id=publisher, snapshot_id=sid)
    assert result['status'] == 'BLOCKED' and REASON_CODE in result['blockers']
    assert not console.snapshot_is_published(sid)


def test_gate_without_superseded_candidates_is_unchanged(ready):
    console, sid, publisher, verdict = ready
    again = console.consider_publish(actor_id=publisher, snapshot_id=sid)
    assert REASON_CODE not in (again.get('blockers') or [])
    assert again['publish_allowed'] == verdict['publish_allowed']


def test_supersession_retains_every_row_and_marks_every_current_candidate(ready):
    console, sid, publisher, _ = ready
    rows = console._load_objects(sid, remember=False)  # full append-only history
    history = supersede_for_contract_change(rows, snapshot_id=sid, actor=publisher)
    before = {(r['object_id'], r['object_version']) for r in rows}
    after = {(r['object_id'], r['object_version']) for r in history}
    assert before <= after, 'NOOIT verwijderen'
    from src.revision_workflow import knowledge_revision
    current = current_revisions(history, snapshot_id=sid)
    candidates = [r for r in current if knowledge_revision(r)]
    assert candidates and all(r['governance']['validation_status'] == 'superseded' for r in candidates)
    # idempotent: a second pass adds nothing
    assert len(supersede_for_contract_change(history, snapshot_id=sid, actor=publisher)) == len(history)


def test_approvals_do_not_carry_over_to_superseded_successors(ready):
    console, sid, publisher, verdict = ready
    rows = console._load_objects(sid, remember=False)  # full append-only history
    bindings = console.object_review_bindings(sid, objects=rows)
    history = supersede_for_contract_change(rows, snapshot_id=sid, actor=publisher)
    current = {r['object_id']: r for r in current_revisions(history, snapshot_id=sid)}
    approved = [b for b in bindings if b.get('decision') == 'approve' and b.get('valid')]
    assert approved
    for binding in approved:
        successor = current[binding['object_id']]
        assert successor['object_version'] != binding.get('object_version')


def test_concurrent_gate_evaluations_all_refuse_superseded(ready):
    console, sid, publisher, verdict = ready
    _with_superseded(console, sid, verdict)
    results, barrier = [], threading.Barrier(4)

    def run():
        barrier.wait()
        results.append(console.consider_publish(actor_id=publisher, snapshot_id=sid))
    threads = [threading.Thread(target=run) for _ in range(4)]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    assert len(results) == 4 and all(REASON_CODE in r['blockers'] and not r['publish_allowed'] for r in results)


# --- trigger: fresh attempt after a full-contract change ---------------------

def _fresh_ready(tmp_path):
    from src.operations_console_v1 import OperationsConsole
    from tests.test_attempt_diagnostics_postgres import bound, ingest
    console = OperationsConsole(root=tmp_path, source_store=tmp_path / 's', runtime=tmp_path / 'r')
    bound(console, reject=False)
    sid, actor, _ = ingest(console)
    return console, sid, actor


def _set_stored_contract(console, sid, value):
    envelope = deepcopy(console._envelope(sid))
    envelope['semantic_replay']['identity']['components']['semantic_contract_version'] = value
    console._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)


def _candidate_ids(console, sid):
    from src.revision_workflow import knowledge_revision
    return {r['object_id'] for r in current_revisions(console._load_objects(sid, remember=False), snapshot_id=sid)
            if knowledge_revision(r)}


def _reextract(console, sid, actor):
    from src.operations_console_v1 import ConsoleError
    try:
        console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    except ConsoleError:
        pass


def test_fresh_attempt_after_contract_change_supersedes_existing_candidates(tmp_path):
    console, sid, actor = _fresh_ready(tmp_path)
    before = console._load_objects(sid, remember=False)
    prior = _candidate_ids(console, sid)
    assert prior
    _set_stored_contract(console, sid, 'older-contract/v0')
    _reextract(console, sid, actor)
    history = console._load_objects(sid, remember=False)
    keys = {(r['object_id'], r['object_version']) for r in history}
    assert {(r['object_id'], r['object_version']) for r in before} <= keys, 'NOOIT verwijderen'
    from src.revision_workflow import lineage_evidence
    superseded = {r['object_id'] for r in history
                  if r['governance'].get('validation_status') == 'superseded'
                  and (lineage_evidence(r) or {}).get('reason') == 'contract change supersession'}
    assert prior <= superseded


def test_fresh_attempt_without_contract_change_supersedes_nothing(tmp_path):
    console, sid, actor = _fresh_ready(tmp_path)
    _reextract(console, sid, actor)
    from src.revision_workflow import lineage_evidence
    assert not [r for r in console._load_objects(sid, remember=False)
                if (lineage_evidence(r) or {}).get('reason') == 'contract change supersession']


def test_legacy_replay_without_contract_supersedes_nothing():
    from src.candidate_supersession_v1 import contract_changed
    assert not contract_changed({}, 'current')
    assert not contract_changed({'semantic_replay': {'identity': {'components': {}}}}, 'current')
    assert not contract_changed({'semantic_replay': {'identity': {'components': {'semantic_contract_version': 'a'}}}}, None)
    assert contract_changed({'semantic_replay': {'identity': {'components': {'semantic_contract_version': 'a'}}}}, 'b')
