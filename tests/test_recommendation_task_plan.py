"""#838 priority changes execution order, never coverage or recommendation admission.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: opslag recovery concurrent stale version-compat
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from copy import deepcopy
from pathlib import Path

from src.bounded_formation_v1 import execute, full_span
from src.bounded_model_call_v1 import ModelCallLimits
from src.semantic_passage_v1 import semantic_source_blocks
from tests.test_recommendation_context_v3 import source

REFERENCE = json.loads((Path(__file__).parent/'fixtures/smetten-reference.json').read_text())
ADVICE = REFERENCE['modules'][0]['recs'][0]['text']


def inputs(texts):
    fragments = [dict(source(text)[0],fragment_id=str(i),fragment_hash=str(i),section_path=path)
                 for i,(text,path) in enumerate(texts)]
    blocks = semantic_source_blocks(fragments)
    return blocks, {'fragments':fragments,'evidence_fragments':fragments,'document_id':'test',
        'allowed_candidate_block_ids':[b['block_id'] for b in blocks], 'field_contract_v3':True}


def test_smetten_recommendation_at_source_task_43_is_planned_first_without_losing_130_tasks():
    texts = [(f'Algemene inhoudelijke bronpassage nummer {i}.',[f'Module {i}']) for i in range(130)]
    texts[42] = (ADVICE,['Module risicofactoren','Aanbevelingen'])
    blocks,data = inputs(texts)
    def forbidden(**kwargs):
        raise AssertionError('budget is exhausted')
    proposal,evidence = execute(blocks=blocks,evidence_blocks=blocks,validator_input=data,
        provider=forbidden,limits=ModelCallLimits(total=0))
    assert evidence['tasks'][0]['target_spans'] == [full_span(blocks[42])]
    assert len(evidence['tasks']) == 130
    assert sorted((s['block_id'],s['start'],s['end']) for t in evidence['tasks'] for s in t['target_spans']) == sorted(
        (b['block_id'],0,len(b['text'])) for b in blocks)
    assert not proposal['objects']  # priority is not automatic selection


def test_inventory_is_not_heading_only_or_automatic_table_admission_and_keeps_context():
    from src.bounded_formation_v1 import tasks_for
    from src.recommendation_task_plan_v1 import build_plan, remaining_tasks
    texts = [('Een beschrijving van de werkwijze.',['Achtergrond']),
             ('Bij een natte huid:',['Behandeling']),
             ('Overweeg maatregelen uit Tabel 1.',['Behandeling']),
             ('Behalve bij overgevoeligheid.',['Behandeling']),
             ('Tabel 1. Preventieve maatregelen',['Bijlage','Tabel 1']),
             ('Houd de huid droog.',['Bijlage','Tabel 1'])]
    blocks,data = inputs(texts)
    tasks = tasks_for(blocks,blocks)
    plan = build_plan(tasks,blocks,blocks)
    pending = [{'span':full_span(b)} for b in blocks]
    restored = remaining_tasks(plan,blocks,blocks,pending)
    assert restored[0]['source_order'] == 2
    assert [b['text'] for b in restored[0]['source_blocks']] == [row[0] for row in texts[1:4]]
    assert [b['text'] for b in restored[0]['evidence_blocks']] == [row[0] for row in texts[4:]]
    assert len(plan['possible_recommendations']) == 2  # both signals, no inferred knowledge objects
    assert plan['detection_completeness'] == 'not_proven'
    assert restored[-1]['priority'] == 'remaining_source'
    assert all(s == full_span(next(b for b in blocks if b['block_id'] == s['block_id']))
               for task in restored for s in task['target_spans'])


def test_pinned_plan_recovers_partial_task_with_old_selection_as_context():
    from src.bounded_formation_v1 import tasks_for
    from src.recommendation_task_plan_v1 import build_plan, remaining_tasks
    blocks,_ = inputs([('Gebruik geen zalf.',['Advies']),('Controleer de huid.',['Advies'])])
    plan = build_plan(tasks_for(blocks,blocks),blocks,blocks)
    pending = [{'span':full_span(blocks[1])}]
    task = remaining_tasks(plan,blocks,blocks,pending)[0]
    assert task['source_blocks'] == [blocks[1]]
    assert task['evidence_blocks'] == [blocks[0]]
    assert task['target_spans'] == [full_span(blocks[1])]


def test_plan_commit_is_atomic_first_writer_wins_and_ref_detects_loss(tmp_path, production_console):
    import pytest
    from concurrent.futures import ThreadPoolExecutor
    from src.bounded_formation_v1 import tasks_for
    from src.recommendation_task_plan_v1 import build_plan
    from src.semantic_replay_v1 import stable_json_hash
    from src.workflows.formation_task_store_v1 import WorkflowDocumentStoreError
    from tests.test_formation_task_store_postgres import prepared, checkpoint_context
    console,envelope,data = prepared(tmp_path,production_console)
    writer = checkpoint_context(console,envelope,data)
    blocks = semantic_source_blocks(data['fragments'])
    evidence = semantic_source_blocks(data['evidence_fragments'])
    plan = build_plan(tasks_for(blocks,evidence),blocks,evidence)
    context_id = writer.input_reference['context_id']
    with pytest.raises(RuntimeError,match='rollback-plan'):
        with writer.store.documents._connect() as con:
            writer.store.retain_task_plan(con,context_id,plan)
            raise RuntimeError('rollback-plan')
    assert writer.load_task_plan() is None
    alternate = deepcopy(plan)
    alternate['tasks'].reverse()
    def retain(candidate):
        with writer.store.documents._connect() as con:
            return writer.store.retain_task_plan(con,context_id,candidate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(retain,[plan,alternate]))
    assert results[0] == results[1]
    kept = writer.load_task_plan()  # binds its immutable ref to the active attempt
    assert kept == results[0]
    ref = deepcopy(writer.plan_reference)
    assert ref['plan_hash'] == stable_json_hash(kept)
    with writer.store.documents._connect() as con:
        con.execute('DELETE FROM workflow.formation_task_plans WHERE context_id=%s',(context_id,))
    with pytest.raises(WorkflowDocumentStoreError,match='formation_task_plan_missing'):
        writer.load_task_plan()


def test_native_resume_keeps_pinned_order_and_completed_work_when_local_grouping_changes(tmp_path,production_console,monkeypatch):
    import pytest
    from src.operations_console_v1 import ConsoleError
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.source_bound_fields_v3 import MODE
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    from tests.production_support import restart_production
    from tests.test_d5_4_review_interaction_evidence import _system
    from tests.test_recommendation_context_v3 import response_for
    console,users,_,_ = _system(tmp_path,production_console=production_console)
    actor = users['researcher']['account_id']
    sid = console.receive_source(actor_id=actor,filename='priority.html',content_type='text/html',
        data=('<html><body><h1>Overig</h1><p>Was dagelijks de handen.</p><h1>Aanbevelingen</h1><p>'+ADVICE+
              '</p><h1>Overige zorg</h1><p>Droog de huid zorgvuldig.</p></body></html>').encode(),
        ingest_kind='new',title='Priority',version='1',date='2026-10-25',live_url='',class_='richtlijn',family='test',
        named_reviewers=[users['reviewer_a']['account_id']])['snapshot_id']
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE','v1')
    calls,plan_hashes = [],[]
    def provider(_url,_headers,payload,_timeout):
        request = json.loads(payload['input'][1]['content'])
        text = request['source_blocks'][0]['text']
        calls.append(text)
        # Read independent connection while provider runs: plan must already be durable.
        with console.workflow_document_store._connect() as con:
            plan_hashes.append(con.execute('SELECT p.plan_hash FROM workflow.formation_task_plans p '
                'JOIN workflow.formation_contexts c USING(context_id) WHERE c.snapshot_id=%s',(sid,)).fetchone()['plan_hash'])
        if len(calls) == 2:
            raise ConsoleError('processing_test_interrupted')
        proposal = response_for(payload,text)
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal)}]}]}
    def bind(target):
        bind_pre_review_semantic_processing(target,environ={'METIS_PASSAGE_FORMATION_MODE':MODE,
            'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'test'},post_json=provider)
    bind(console)
    attempt,_ = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='first',
        expected_revision=console.objects_revision(sid))
    with pytest.raises(ConsoleError,match='processing_test_interrupted'):
        console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    assert calls[0] == ADVICE
    saved = console._envelope(sid)['processing_attempts'][-1]
    ref = saved['diagnostic']['task_plan_ref']
    store = FormationTaskStore(console.workflow_document_store)
    original = store.load_task_plan(ref['context_id'],expected_hash=ref['plan_hash'])
    assert original['tasks'][0]['source_order'] == 2
    restarted = restart_production(console)
    bind(restarted)
    def forbidden(*args,**kwargs):
        raise AssertionError('Resume must read the durable plan instead of regrouping')
    monkeypatch.setattr('src.bounded_formation_v1.tasks_for',forbidden)
    following,_ = restarted.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='resume',
        expected_revision=restarted.objects_revision(sid))
    restarted.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=following)
    assert calls == [ADVICE,'Was dagelijks de handen.','Was dagelijks de handen.','Droog de huid zorgvuldig.']
    assert set(plan_hashes) == {ref['plan_hash']}
    final = restarted._envelope(sid)
    assert final['processing_attempts'][-1]['state'] == 'succeeded'
    diagnostic = FormationTaskStore(restarted.workflow_document_store).diagnostic(final['processing_attempts'][-1])
    assert diagnostic['task_plan'] == original
    assert diagnostic['provider_evidence']['task_plan_summary']['possible_recommendation_count'] == 1
    assert diagnostic['provider_evidence']['task_plan_summary']['selected_recommendation_count'] == 2  # own attempt only
    from src.processing_evidence_export_v1 import processing_evidence_tables
    tables,_ = processing_evidence_tables(snapshot_id=sid,revision=restarted.objects_revision(sid),
        objects=restarted.snapshot_objects(sid),envelope=final,
        diagnostic_reader=FormationTaskStore(restarted.workflow_document_store).diagnostic,
        input_resolver=FormationTaskStore(restarted.workflow_document_store).resolve_input)
    assert tables['attempt_diagnostics'][-1]['diagnostic']['task_plan'] == original
    assert all(obj['governance']['validation_status'] == 'needs_review' for obj in restarted.snapshot_objects(sid)
               if obj.get('object_type') != 'document')


def test_corrupt_plan_and_stale_writer_cannot_start_or_replace_planning(tmp_path,production_console):
    import pytest
    from src.operations_console_v1 import ConsoleError
    from src.bounded_formation_v1 import tasks_for
    from src.recommendation_task_plan_v1 import build_plan,remaining_tasks
    from src.semantic_replay_v1 import stable_json_hash
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError,_json_text
    from tests.test_formation_task_store_postgres import prepared,checkpoint_context
    console,envelope,data = prepared(tmp_path,production_console)
    writer = checkpoint_context(console,envelope,data)
    blocks = semantic_source_blocks(data['fragments'])
    evidence = semantic_source_blocks(data['evidence_fragments'])
    plan = build_plan(tasks_for(blocks,evidence),blocks,evidence)
    token = writer.claim_token
    writer.claim_token = 'obsolete-worker'
    with pytest.raises(ConsoleError,match='processing_command_conflict'):
        writer.retain_task_plan(plan)
    writer.claim_token = token
    assert writer.load_task_plan() is None
    writer.retain_task_plan(plan)
    context_id = writer.input_reference['context_id']
    with writer.store.documents._connect() as con:
        con.execute("UPDATE workflow.formation_task_plans SET payload=jsonb_set(payload,'{tasks}','[]') WHERE context_id=%s",(context_id,))
    with pytest.raises(WorkflowDocumentStoreError,match='formation_task_plan_integrity_failed'):
        writer.load_task_plan()
    bad = {**plan,'source_blocks_hash':'foreign-source'}
    with writer.store.documents._connect() as con:
        con.execute('UPDATE workflow.formation_task_plans SET payload=%s::jsonb,plan_hash=%s WHERE context_id=%s',
            (_json_text(bad),stable_json_hash(bad),context_id))
    with pytest.raises(ConsoleError,match='formation_task_plan_source_mismatch'):
        foreign = writer.store.load_task_plan(context_id)
        remaining_tasks(foreign,blocks,evidence,[{'span':full_span(b)} for b in blocks])
    writer.plan_reference = {'context_id':context_id}
    with pytest.raises(ConsoleError,match='formation_task_plan_conflict'):
        writer.load_task_plan()
    writer.plan_reference = {'context_id':'another-context', 'plan_hash':stable_json_hash(plan)}
    with pytest.raises(ConsoleError,match='formation_task_plan_conflict'):
        writer.load_task_plan()


def test_all_19_independent_smetten_reference_items_remain_possible_not_automatically_selected():
    from src.bounded_formation_v1 import tasks_for
    from src.recommendation_task_plan_v1 import build_plan,report
    known = [rec['text'] for module in REFERENCE['modules'] for rec in module['recs']]
    assert len(known) == 19
    blocks,_ = inputs([(f'{index}. {text}',['Aanbevelingen']) for index,text in enumerate(known,1)])
    plan = build_plan(tasks_for(blocks,blocks),blocks,blocks)
    assert len(plan['possible_recommendations']) == 19
    by_id = {b['block_id']:b['text'] for b in blocks}
    assert [by_id[row['span']['block_id']][row['span']['start']:row['span']['end']]
            for row in plan['possible_recommendations']] == known
    summary = report(plan,{'objects':[]},[{'span':full_span(b)} for b in blocks])
    assert summary['possible_recommendation_count'] == 19
    assert summary['selected_recommendation_count'] == 0
    assert len(summary['remaining_source_ranges']) == 19
