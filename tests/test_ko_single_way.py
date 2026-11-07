"""KO5: every human KO decision reaches the KO4 policy before durable commit.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale restart rollback
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from pathlib import Path
import ast

import pytest

from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.review import ko_transitions_v1 as policy
from src.review.review_command_state_v1 import active_review_command
from src.workflows.workflow_transaction_v1 import workflow_transaction_active
from tests.test_review_command_bounded_http_v1 import physical_state
from tests.test_ko_transitions_postgres import YES, _approval
from tests.test_t12_publication_readiness_authority import _console
from src.review.knowledge_path_v1 import content_reviewable

pytestmark = [pytest.mark.release_control_scope_belofte, pytest.mark.release_control_opslag,
              pytest.mark.release_control_toegang, pytest.mark.release_control_kwaliteit,
              pytest.mark.release_control_slop, pytest.mark.release_control_releasebewijs]
ROOT = Path(__file__).resolve().parents[1]
REFUSAL = 'ko5_distinctive_policy_refusal'


def _refuses_without_writes(console, sid, monkeypatch, invoke, *, prepared=False):
    before = deepcopy(physical_state(console, sid))
    events = console.workflow_review_store.read_events_for_snapshots([sid])
    seen = []
    def refuse(**kwargs):
        state = active_review_command(console)
        seen.append((kwargs['event'], bool(state and state.preparing),
                     console._store_lock_depth, workflow_transaction_active()))
        raise ConsoleError(REFUSAL)
    with monkeypatch.context() as guard:
        guard.setattr(policy, 'apply_ko_event', refuse)
        with pytest.raises(ConsoleError) as failure:
            invoke()
    assert failure.value.code == REFUSAL
    assert seen
    if prepared:
        assert all(preparing and depth == 0 and not transaction
                   for _event, preparing, depth, transaction in seen)
    assert physical_state(console, sid) == before
    assert console.workflow_review_store.read_events_for_snapshots([sid]) == events
    assert console.workflow_review_store._buffer.get() is None
    assert active_review_command(console) is None


@pytest.mark.parametrize('entry', ['approve', 'direct_approve', 'correct', 'direct_correct', 'confirm_type', 'relations', 'reject', 'later'])
def test_native_human_commands_cannot_commit_around_policy(tmp_path, production_console, monkeypatch, entry):
    console, sid = _console(tmp_path, production_console=production_console)
    target = next(obj for obj in console.snapshot_objects(sid) if content_reviewable(obj))
    actor = console._envelope(sid)['named_reviewers'][0]
    common = dict(actor_id=actor, snapshot_id=sid, object_id=target['object_id'],
                  expected_revision=console.objects_revision(sid))
    if entry == 'approve':
        invoke = lambda: _approval(console, sid, target, assessment=YES, evidence_not_applicable=True)
    elif entry == 'direct_approve':
        invoke = lambda: OperationsConsole.review_object(console, **common, decision='approve',
            confirmed_object_type='definition', suitability='ja', eindoordeel='goedkeuren',
            assessment=YES, evidence_not_applicable=True)
    elif entry in {'correct', 'direct_correct'}:
        method = console.correct_object if entry == 'correct' else lambda **values: OperationsConsole.correct_object(console, **values)
        invoke = lambda: method(**common, patch={'reason': 'Explicit correction',
            'operations': [{'op': 'set', 'path': 'uncertainty.has_uncertainty', 'value': True}]}, rereview_scope='object')
    elif entry in {'reject', 'later'}:
        invoke = lambda: console.review_object(**common, decision=entry, comment='Explicit human decision')
    elif entry == 'confirm_type':
        invoke = lambda: console.confirm_object_type(**common, confirmed_object_type='explanation')
    else:
        invoke = lambda: console.confirm_relations(**common, relations=[])
    _refuses_without_writes(console, sid, monkeypatch, invoke)


@pytest.mark.parametrize('entry', ['support', 'merge'])
def test_existing_repair_commands_cannot_commit_around_policy(tmp_path, production_console, production_app, monkeypatch, entry):
    from tests.test_deterministic_review_repair_v1 import _system
    from src.review.deterministic_review_repair_v1 import REPAIR_SUPPORT_RELATION, REPAIR_MERGE_OBJECTS
    console, _client, _author, actor, sid, objects = _system(tmp_path,
        production_console=production_console, production_app=production_app)
    values = dict(actor_id=actor['account_id'], snapshot_id=sid, object_id=objects[0]['object_id'],
                  expected_revision=console.objects_revision(sid), comment='Explicit repair')
    if entry == 'support':
        values.update(suitability='alleen_onderbouwing', repair_kind=REPAIR_SUPPORT_RELATION,
                      claim_object_id=objects[1]['object_id'])
    else:
        values.update(suitability='samenvoegen', repair_kind=REPAIR_MERGE_OBJECTS,
                      merge_object_ids=[objects[1]['object_id']])
    _refuses_without_writes(console, sid, monkeypatch, lambda: console.submit_review_resolution(**values))


def test_prepared_source_policy_runs_outside_lock_and_transaction(tmp_path, production_console, monkeypatch):
    from tests.test_a09_source_repair import setup_repair
    from tests.test_prepared_source_resolution import command_for
    console, sid, obj, actor, _fresh = setup_repair(tmp_path, production_console=production_console)
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    command = command_for(console, sid, obj, actor, units[:1])
    assert command['expected_revision'] and command['source_unit_ids']
    _refuses_without_writes(console, sid, monkeypatch,
        lambda: console.submit_review_resolution(**command), prepared=True)


def test_second_review_uses_same_policy_and_exact_binding_transaction(tmp_path, production_console, monkeypatch):
    from tests.test_v225_beslisboom_path import _console as boom_console, _accounts
    from tests.test_decision_graph_chain import ingest, complete_graph, command
    from src.review.review_duty_v1 import authoritative_review_type
    console = boom_console(tmp_path, production_console=production_console)
    people = _accounts(console)
    sid = ingest(console, people, 'required')['snapshot_id']
    console.update_decision_graph(**command(console, people, sid, 'ko5-graph', graph=complete_graph(console, sid)))
    obj = next(row for row in console.snapshot_objects(sid) if authoritative_review_type(row) == 'node')
    console.review_object(actor_id=people['researcher']['account_id'], snapshot_id=sid,
        object_id=obj['object_id'], decision='approve', confirmed_object_type='node',
        type_action='dit_klopt', suitability='ja', eindoordeel='goedkeuren',
        assessment=YES, evidence_not_applicable=True, expected_revision=console.objects_revision(sid))
    _refuses_without_writes(console, sid, monkeypatch, lambda: console.approve_second_review(
        actor_id=people['reviewer']['account_id'], snapshot_id=sid, object_id=obj['object_id'],
        expected_revision=console.objects_revision(sid), assessment=YES, evidence_not_applicable=True))


def test_retired_entrypoints_and_duplicate_completion_sets_stay_absent():
    from src.review import review_workflow_v3
    from src.review.review_closure_v1 import ReviewClosureConsole
    from src.documents import document_status_v1
    assert not hasattr(review_workflow_v3, 'apply_reviews')
    assert not hasattr(review_workflow_v3, 'main')
    assert not hasattr(ReviewClosureConsole, 'migrate_legacy_revise_to_review')
    assert not hasattr(document_status_v1, '_local_release_serving_status')
    assert not (ROOT / 'src/publication/canonical_store.py').exists()
    assert not (ROOT / 'src/canonical_store.py').exists()
    # A bounded final-status contract belongs to KO derivation. Candidate
    # initialization and staged writers remain legitimate KO4 mechanisms.
    duplicates = []
    for file in (ROOT / 'src').rglob('*.py'):
        if file.name == 'knowledge_object_state_v1.py':
            continue
        for node in ast.walk(ast.parse(file.read_text())):
            if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
                values = {item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)}
                if {'approved', 'rejected', 'superseded'} <= values:
                    duplicates.append(f'{file.relative_to(ROOT)}:{node.lineno}')
    assert duplicates == []


def test_contradictory_mirrors_neither_approve_nor_seal_current_work(tmp_path, production_console):
    from tests.semantic_fixture_support import install_fixture_history
    from src.integrity_kernel import schema_errors
    from src.review.review_duty_v1 import review_stage, FIRST_REVIEW
    console, sid = _console(tmp_path, production_console=production_console)
    target = next(obj for obj in console.snapshot_objects(sid) if content_reviewable(obj))
    target = console.confirm_object_type(actor_id=console._envelope(sid)['named_reviewers'][0],
        snapshot_id=sid, object_id=target['object_id'], confirmed_object_type='definition',
        expected_revision=console.objects_revision(sid))
    history = console._load_objects(sid, remember=False)
    row = next(obj for obj in reversed(history) if obj['object_id'] == target['object_id'])
    row['governance'].update(publication_status='published',
        second_review={'required': False, 'status': 'approved', 'reviewer': 'forged',
                       'review_date': '2026-11-07', 'snapshot_hash': '0' * 64})
    install_fixture_history(console, sid, history)
    envelope = console._envelope(sid)
    envelope.update(review_passes={'forged': {'passed': True}}, clinical_rereview_required=True)
    console.workflow_document_store.write_bundle(envelope=envelope)
    current = console._current_object(sid, target['object_id'])
    assert review_stage(current, review_path='richtlijn', bindings=[], fragments=console.review_source_fragments(sid)) == FIRST_REVIEW
    assert console.document_release_serving_status(sid) == {'release_status': 'none', 'serving_status': 'inactive'}
    assert console.publication_readiness(sid)['publication_ready'] is False
    mirror = deepcopy(current['governance']['second_review'])
    _approval(console, sid, current, assessment=YES, evidence_not_applicable=True)
    approved = console._current_object(sid, target['object_id'])
    assert console.object_review_bindings(sid)[0]['valid']
    retained = next(row for row in console._load_objects(sid, remember=False)
                    if row['object_id'] == current['object_id'] and row['object_version'] == current['object_version'])
    assert retained['governance']['second_review'] == mirror
    assert retained['governance']['publication_status'] == 'published'
    assert approved['object_version'] != current['object_version']  # final reviewed disposition is new canonical work
    assert approved['governance']['second_review']['reviewer'] is None
    assert not schema_errors(approved, console.schema_path)
    assert console._envelope(sid)['review_passes'] == {'forged': {'passed': True}}
    assert console._envelope(sid)['clinical_rereview_required'] is True
    successor = console.correct_object(actor_id=envelope['named_reviewers'][0], snapshot_id=sid,
        object_id=target['object_id'], expected_revision=console.objects_revision(sid),
        patch={'reason': 'New review work', 'operations': [
            {'op': 'set', 'path': 'uncertainty.has_uncertainty', 'value': True}]}, rereview_scope='object')
    assert successor['governance']['publication_status'] == 'unpublished'
    assert successor['governance']['second_review'] == {
        'required': bool(successor['risk']['requires_second_review']),
        'status': 'pending' if successor['risk']['requires_second_review'] else 'not_required',
        'reviewer': None, 'review_date': None, 'snapshot_hash': None}
    assert not schema_errors(successor, console.schema_path)
    assert not any(binding['valid'] for binding in console.object_review_bindings(sid))


def test_boom_duty_without_bindings_cannot_trust_completed_second_review():
    from src.review.review_duty_v1 import review_stage, FIRST_REVIEW
    from src.vorming.admission_gate_v1 import is_boom_object
    obj = {'object_id': 'boom-node', 'object_type': 'node'}
    obj.setdefault('governance', {}).update(validation_status='approved',
        second_review={'required': True, 'status': 'approved'})
    assert is_boom_object(obj)
    assert review_stage(obj, review_path='boom', bindings=None) == FIRST_REVIEW


def test_missing_canonical_store_never_infers_serving_from_envelope():
    from src.documents.document_status_v1 import DocumentStatusReadinessMixin
    from src.workflows.workflow_badge_counts_postgres_v1 import _PostgresBadgeCountsMixin
    subject = DocumentStatusReadinessMixin()
    with pytest.raises(ConsoleError, match='durable_publication_store_required'):
        subject.document_release_serving_status('published-looking', envelope={'state': 'published'})
    badges = _PostgresBadgeCountsMixin()
    badges.canonical_publication_store = None
    with pytest.raises(ConsoleError, match='durable_publication_store_required'):
        badges._canonical_list_release_rows(['published-looking'])


@pytest.mark.parametrize('mode', ['legacy', 'compact'])
def test_retired_document_badge_cannot_duplicate_review_work_or_context_headings(
        tmp_path, production_console, monkeypatch, mode):
    from tests.test_vsa_meaningful_document_status_v1 import _system, _complete_review
    from src.vorming.passage_register_v1 import passage_register_of
    from src.workflows.review_card_inputs_postgres_v1 import prepare_review_cards
    console, accounts, receipt, _source = _system(tmp_path, production_console=production_console)
    sid = receipt['snapshot_id']
    console.review_card_read_mode = mode
    if mode == 'compact':
        prepare_review_cards(console.workflow_document_store, sid)
    # Review remains the one personal work queue. Documenten is a catalogue,
    # not a second global review counter, including for unassigned publishers.
    for role, person in accounts.items():
        counts = console.waiting_task_counts(person['account_id'])
        assert counts['tree'] == 0
        assert counts['review'] == (1 if role in {'researcher', 'reviewer'} else 0)
    _complete_review(console, accounts, receipt)
    ready = console.publication_readiness(sid)
    assert ready['curation_ready'] and ready['review_complete'] and ready['source_passage_review_complete']
    assert ready['publication_ready']
    headings = [obj for obj in console.snapshot_objects(sid)
                if obj['object_type'] == 'heading'
                and passage_register_of(obj).get('status') == 'used_as_context'
                and obj['governance']['validation_status'] == 'needs_review']
    assert headings, 'Fixture must retain the raw-status trap from the independent repro'
    envelope = console._envelope(sid)
    envelope.update(clinical_rereview_required=True, review_passes={'forged': {'passed': True}})
    console.workflow_document_store.write_bundle(envelope=envelope)
    if mode == 'compact':
        prepare_review_cards(console.workflow_document_store, sid)
    # Navigation must not evaluate source durability or the publication gate.
    with monkeypatch.context() as guard:
        guard.setattr(console, 'publication_readiness', lambda *a, **k: pytest.fail('badge ran full readiness'))
        guard.setattr(console, 'consider_publish', lambda *a, **k: pytest.fail('badge ran publication gate'))
        for person in accounts.values():
            assert console.waiting_task_counts(person['account_id'])['tree'] == 0
        assert console.waiting_task_counts(accounts['reviewer']['account_id'])['review'] == 0
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    assert result['status'] == 'PASS'
    assert console.document_release_serving_status(sid)['serving_status'] == 'active'
    for person in accounts.values():
        assert console.waiting_task_counts(person['account_id'])['tree'] == 0
    assert console.waiting_task_counts(accounts['reviewer']['account_id'])['review'] == 0


def _offline_integrity_fixture(tmp_path):
    import json
    from src.integrity_kernel import stamp_canonical_hashes, exact_review_snapshot_hash, sha256_file, schema_errors
    binary = tmp_path / 'synthetic.html'
    binary.write_text('<html><body>Offline integrity fixture.</body></html>')
    rows = [json.loads(line) for line in (ROOT / 'data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v21.jsonl').read_text().splitlines() if line.strip()]
    obj = deepcopy(next(row for row in rows if row['object_type'] == 'document'))
    obj['source'].update(source_type='html', source_checksum=sha256_file(binary), integrity_status='verified')
    obj.update(parent_object_id=None, relations=[], uncertainty={'has_uncertainty': False, 'items': []})
    obj['provenance']['source_fragments'] = []
    obj['governance'].update(validation_status='approved', validated_by='Synthetic reviewer', validation_date='2026-11-07')
    stamp_canonical_hashes(obj)
    obj['governance']['review_snapshot_hash'] = exact_review_snapshot_hash(obj)
    schema = ROOT / 'schemas/knowledge_object.schema.v1.1.json'
    assert not schema_errors(obj, schema)
    source = tmp_path / 'objects.jsonl'
    source.write_text(json.dumps(obj) + '\n')
    raw = tmp_path / 'raw.jsonl'
    raw.write_text('')
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({'sources': [{'source_id': obj['source']['source_id'],
        'source_checksum': sha256_file(binary), 'binary_path': str(binary), 'integrity_status': 'verified'}]}))
    return obj, source, schema, raw, registry


@pytest.mark.parametrize('entry', ['command', 'wrapper', 'package'])
def test_offline_publication_verdict_is_retired_without_output_files(tmp_path, entry):
    import subprocess
    import sys
    _obj, source, schema, raw, registry = _offline_integrity_fixture(tmp_path)
    report = tmp_path / 'publication-verdict.json'
    invocation = {'command': ['src.cli', 'prepublish'], 'wrapper': ['src.prepublication_gate_v3'],
                  'package': ['src.publication.prepublication_gate_v3']}[entry]
    result = subprocess.run([sys.executable, '-m', *invocation, '--input', str(source),
        '--schema', str(schema), '--source-registry', str(registry), '--raw-extract', str(raw),
        '--report', str(report)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert ('invalid choice' if entry == 'command' else 'No module named') in result.stderr
    assert not report.exists()
    assert not (ROOT / 'src/publication/eligibility_policy.py').exists()


@pytest.mark.parametrize('tampered', [False, True])
def test_offline_audit_keeps_integrity_checks_without_publication_verdict(tmp_path, tampered):
    import json
    import subprocess
    import sys
    obj, source, schema, raw, _registry = _offline_integrity_fixture(tmp_path)
    if tampered:
        obj['content']['clean_text'] += ' Unstamped alteration.'
        source.write_text(json.dumps(obj) + '\n')
    report = tmp_path / 'integrity-audit.json'
    result = subprocess.run([sys.executable, '-m', 'src.cli', 'audit-current', '--input', str(source),
        '--schema', str(schema), '--raw-extract', str(raw), '--report', str(report)],
        cwd=ROOT, capture_output=True, text=True)
    audit = json.loads(report.read_text())
    assert result.returncode == (2 if tampered else 0)
    assert audit['integrity_ok'] is not tampered
    assert audit['status'] == ('BLOCKED' if tampered else 'PASS')
    assert bool(audit['object_errors']) == tampered
    assert 'publication_gate' not in audit and 'publication_blocker_count' not in audit
