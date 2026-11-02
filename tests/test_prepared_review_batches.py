"""Native prepared batch guards, pure preparation and all-or-nothing writes.
# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit metrics slop releasebewijs
"""
from contextlib import contextmanager
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from src.integrity_kernel import stable_hash, compute_canonical_object_hash
from src.operations_console_v1 import ConsoleError
from src.review.review_passage_read_v1 import _revision
from tests.test_v233_review_audit_regressions import review_system


def durable(console, sid):
    tables = ('documents','document_objects','document_reviewers','publish_authorizations',
              'review_events','object_revision_frontiers','review_object_facts','review_fact_state','document_inputs')
    out = {}
    with console.workflow_document_store._connect() as con:
        for name in tables:
            if con.execute('SELECT to_regclass(%s) AS name', ('workflow.'+name,)).fetchone()['name'] is None:
                continue
            rows = con.execute('SELECT to_jsonb(t) AS value FROM workflow.'+name+' t WHERE snapshot_id=%s', (sid,)).fetchall()
            out[name] = sorted(stable_hash(r['value']) for r in rows)
        rows=con.execute("SELECT account_id,username,display_name,roles,to_jsonb(a)->'retirement' AS retirement FROM workflow.accounts a").fetchall()
        out['accounts'] = sorted(stable_hash(r) for r in rows)
    return out


def before_commit(console, monkeypatch, mutation):
    lock=console._store_write_lock
    entered=[]
    @contextmanager
    def intervening():
        if not entered:
            from src.review.review_command_state_v1 import active_review_command
            active = active_review_command(console)
            assert active is None or not active.preparing, 'write lock during pure preparation'
            entered.append(True)
            mutation()
        with lock():yield
    monkeypatch.setattr(console,'_store_write_lock',intervening)
    return entered


def execute(system):
    console,_client,sid,actor,ids=system
    _,generation=console.workflow_document_store.review_document_input(sid)
    return lambda: console.batch_review_normal_risk(actor_id=actor,snapshot_id=sid,
                    object_ids=ids,expected_revision=_revision(sid,generation))


@pytest.mark.parametrize('change', ['role','identity','roster','policy','source','quality','native0','binding','new_inbound'])
def test_changed_preparation_inputs_refuse_without_overwriting_winner(review_system, monkeypatch, change):
    console,_client,sid,actor,ids=review_system
    command=execute(review_system)
    winner=[]
    current=console.snapshot_objects(sid)
    actor_name=console._account(actor)['display_name']
    def mutation():
        with console.workflow_document_store._connect() as con:
            if change=='role':con.execute("UPDATE workflow.accounts SET roles=ARRAY['researcher']::text[] WHERE account_id=%s",(actor,))
            elif change=='identity':con.execute("UPDATE workflow.accounts SET display_name='Changed reviewer' WHERE account_id=%s",(actor,))
            elif change=='native0':con.execute('UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id=%s AND object_id=%s',(sid,ids[0]))
            elif change=='new_inbound':
                other=next(row for row in current if row['object_id'] not in ids and row.get('object_type')!='document')
                edges=[{'relation_type':'supported_by','target_object_id':ids[0]}]
                con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{confirmed_relations}',%s::jsonb,true) WHERE snapshot_id=%s AND object_id=%s AND object_version=%s",(json.dumps(edges),sid,other['object_id'],other['object_version']))
            elif change=='binding':
                obj=next(row for row in current if row['object_id']==ids[0])
                binding={'object_id':ids[0],'object_version':obj['object_version'],
                         'canonical_object_hash':compute_canonical_object_hash(obj),
                         'confirmed_object_type':obj.get('confirmed_object_type') or obj.get('proposed_object_type'),'reviewer_id':actor,
                         'reviewer':actor_name,'decision':'approve','valid':True}
                console.workflow_review_store.apply_review_binding_delta(sid,[],[binding])
            else:
                key,value={'roster':('named_reviewers',[]),'policy':('review_policy',{'contract':'changed'}),
                           'source':('sha256','0'*64),'quality':('quality_processing_runs',[{'run_id':'changed','candidates':[]}])}[change]
                con.execute('UPDATE workflow.documents SET envelope_payload=jsonb_set(envelope_payload,%s,%s::jsonb,true),review_read_envelope=NULL WHERE snapshot_id=%s',([key],json.dumps(value),sid))
                if change=='source':con.execute('UPDATE workflow.documents SET source_sha256=%s WHERE snapshot_id=%s',('0'*64,sid))
        winner.append(durable(console,sid))
    entered=before_commit(console,monkeypatch,mutation)
    with pytest.raises(ConsoleError) as refused:command()
    assert entered and winner, refused.value.code
    assert durable(console,sid)==winner[0]
    assert console.workflow_review_store._buffer.get() is None
    from src.review.review_command_state_v1 import active_review_command
    assert active_review_command(console) is None


def test_pure_kernel_cannot_open_workflow_database_or_flush_audit(review_system, monkeypatch):
    console,_client,sid,_actor,_ids=review_system
    command=execute(review_system)
    from src.review.review_command_state_v1 import active_review_command
    from src.workflows.workflow_transaction_v1 import WorkflowTransactionError
    original=console.review_object
    canonical=console.canonical_publication_store._connect
    def canonical_read():
        state=active_review_command(console)
        assert state is None or not state.preparing, 'canonical SQL during pure preparation'
        return canonical()
    monkeypatch.setattr(console.canonical_publication_store,'_connect',canonical_read)
    observed=[]
    def probe(**kwargs):
        state=active_review_command(console)
        assert state is not None and state.preparing
        assert not console._store_lock_depth
        from src.workflows.workflow_transaction_v1 import workflow_transaction_active
        assert not workflow_transaction_active()
        with pytest.raises(WorkflowTransactionError,match='workflow_io_during_review_preparation'):
            console.workflow_document_store._connect()
        from src.workflows.workflow_review_postgres_v1 import WorkflowReviewStoreError
        with pytest.raises(WorkflowReviewStoreError) as refused:
            console.workflow_review_store._flush_buffer([{'event_hash':'forbidden'}])
        assert isinstance(refused.value.__cause__, WorkflowTransactionError)
        observed.append(kwargs['object_id'])
        return original(**kwargs)
    monkeypatch.setattr(console,'review_object',probe)
    result=command()
    assert len(observed)==len(result)==2
    assert console.workflow_review_store._buffer.get() is None


def test_unrelated_audit_advance_does_not_erase_prepared_user_decisions(review_system,monkeypatch):
    console,_client,sid,_actor,ids=review_system
    command=execute(review_system)
    def mutation():
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(console.workflow_review_store.append_event,event_type='independent_observation',
                object_id='another-object',object_version='1.0',actor='separate-runtime',
                details={'snapshot_id':sid,'kind':'unrelated'}).result(timeout=5)
    before_commit(console,monkeypatch,mutation)
    result=command()
    assert {r['object_id'] for r in result}==set(ids)
    assert all(r['governance']['validation_status']=='approved' for r in result)
    from src.review.review_ledger import verify_ledger
    assert verify_ledger(console._ledger_path)==[]


def prepared_write(system):
    console,_client,sid,_actor,ids=system
    store=console.workflow_document_store
    from src.workflows.workflow_transaction_v1 import workflow_read_transaction
    with workflow_read_transaction(store):
        envelope,_=store.review_document_input(sid,command=True)
        before=store.review_command_window(sid,ids)
    after=deepcopy(before)
    after[0]['governance']['validation_status']='approved'
    return store,sid,before,after,envelope


def test_prepared_write_owns_immutable_values_and_is_single_use(review_system):
    console=review_system[0]
    store,sid,before,after,envelope=prepared_write(review_system)
    handle=store.prepare_review_changes(sid,before,after,envelope,envelope,transitions=[after])
    expected=deepcopy(after)
    after[0]['content']['clean_text']='Caller mutated after validation'
    envelope['review_passes']={'forged':True}
    store.apply_prepared_review_changes(sid,handle)
    assert store.review_command_histories(sid,[r['object_id'] for r in expected])==list(expected)
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    winner=durable(console,sid)
    with pytest.raises(WorkflowDocumentStoreError,match='workflow_review_preparation_invalid'):
        store.apply_prepared_review_changes(sid,handle)
    assert durable(console,sid)==winner


@pytest.mark.parametrize('kind',['forged','wrong_store','wrong_snapshot','stale'])
def test_prepared_write_handle_cannot_bypass_physical_or_owner_guard(review_system,kind):
    console=review_system[0]
    store,sid,before,after,envelope=prepared_write(review_system)
    handle=store.prepare_review_changes(sid,before,after,envelope,envelope,transitions=[after])
    target=store
    if kind=='forged':
        from src.workflows.workflow_document_concurrency_v1 import _PreparedReviewWrite
        handle=_PreparedReviewWrite()
    elif kind=='wrong_store':target=type(store)(store.config)
    elif kind=='wrong_snapshot':sid='another-snapshot'
    elif kind=='stale':
        with store._connect() as con:
            con.execute('UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id=%s AND object_id=%s',
                        (sid,before[0]['object_id']))
    winner=durable(console,review_system[2])
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    with pytest.raises(WorkflowDocumentStoreError):target.apply_prepared_review_changes(sid,handle)
    assert durable(console,review_system[2])==winner


@pytest.mark.parametrize('kind',['meaning','removed','reordered'])
def test_store_preparation_keeps_original_revision_and_shape_refusals(review_system,kind):
    console=review_system[0]
    store,sid,before,after,envelope=prepared_write(review_system)
    if kind=='meaning':after[0]['content']['clean_text']='Undeclared replacement of protected knowledge'
    elif kind=='removed':after.pop(0)
    else:after.reverse()
    winner=durable(console,sid)
    with pytest.raises((ValueError,RuntimeError)):
        store.prepare_review_changes(sid,before,after,envelope,envelope,transitions=[after])
    assert durable(console,sid)==winner


@pytest.mark.parametrize('table', ['document_objects','publish_authorizations','review_events','documents'])
@pytest.mark.parametrize('timing',['BEFORE','AFTER'])
def test_actual_prepared_member2_sql_failure_rolls_back_all_native_state(review_system,table,timing):
    from tests.test_a08_heading_batch_atomic import _fail_native_write
    console,_client,sid,_actor,ids=review_system
    command=execute(review_system)
    _fail_native_write(console,sid,table,object_id=ids[1] if table!='documents' else None,timing=timing)
    before=durable(console,sid)
    with pytest.raises(ConsoleError) as refused:command()
    cause=refused.value
    while cause.__cause__ is not None:cause=cause.__cause__
    assert 'a08_native_write_failure' in str(cause)
    assert durable(console,sid)==before
    assert console.workflow_review_store._buffer.get() is None


def test_actual_deferred_commit_failure_rolls_back_prepared_events_and_objects(review_system,monkeypatch):
    console,_client,sid,_actor,_ids=review_system
    command=execute(review_system)
    applied=[]
    store=console.workflow_document_store
    original=store.apply_prepared_review_changes
    def observe(*args,**kwargs):
        original(*args,**kwargs)
        applied.append(True)
    monkeypatch.setattr(store,'apply_prepared_review_changes',observe)
    with store._connect() as con:
        con.execute("CREATE FUNCTION workflow.prepared_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'prepared_deferred_commit_failure'; END $$")
        con.execute('CREATE CONSTRAINT TRIGGER prepared_commit_failure AFTER UPDATE ON workflow.documents DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.prepared_commit_failure()')
    before=durable(console,sid)
    with pytest.raises(Exception) as refused:command()
    cause=refused.value
    while cause.__cause__ is not None:cause=cause.__cause__
    assert 'prepared_deferred_commit_failure' in str(cause)
    assert applied==[True]
    assert durable(console,sid)==before
    assert console.workflow_review_store._buffer.get() is None
    with store._connect() as con:
        con.execute('DROP TRIGGER prepared_commit_failure ON workflow.documents')
    assert len(command())==2  # A failed COMMIT cannot poison the next request.


@pytest.mark.parametrize('tamper',['payload','hash','reverse','append'])
def test_changed_sealed_audit_intents_refuse_and_rollback(review_system,monkeypatch,tamper):
    console,_client,sid,_actor,_ids=review_system
    command=execute(review_system)
    reviews=console.workflow_review_store
    def mutation():
        buffer=reviews._buffer.get()
        assert buffer._sealed is not None
        if tamper=='payload':buffer[0]['details']['forged']=True
        elif tamper=='hash':buffer[0]['event_hash']='0'*64
        elif tamper=='reverse':buffer.reverse()
        else:buffer.append(deepcopy(buffer[0]))
    before=durable(console,sid)
    before_commit(console,monkeypatch,mutation)
    with pytest.raises(ConsoleError):command()
    assert durable(console,sid)==before
    assert reviews._buffer.get() is None


def test_ordinary_serial_audit_buffer_retains_strict_head_conflict(review_system):
    console,_client,sid,_actor,_ids=review_system
    reviews=console.workflow_review_store
    from src.workflows.workflow_review_postgres_v1 import WorkflowReviewStoreError
    with pytest.raises(WorkflowReviewStoreError,match='workflow_review_chain_conflict'):
        with reviews.buffered():
            reviews.append_event(event_type='serial-pending',object_id='one',object_version='1.0',
                                 actor='serial',details={'snapshot_id':sid})
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(reviews.append_event,event_type='concurrent',object_id='two',object_version='1.0',
                            actor='other',details={'snapshot_id':sid}).result(timeout=5)
    assert not any(e['event_type']=='serial-pending' for e in reviews.read_events())
    assert reviews._buffer.get() is None


def test_foreign_interaction_committed_between_phases_is_rejected(review_system,monkeypatch):
    from src.review.review_interaction_v1 import build_review_interaction_evidence,new_review_interaction_id
    console,_client,sid,actor,ids=review_system
    store,reviews=console.workflow_document_store,console.workflow_review_store
    _,generation=store.review_document_input(sid)
    members=store.review_command_current_heads(sid,ids)
    evidence=build_review_interaction_evidence(interaction_id=new_review_interaction_id(),
        interaction_kind='batch',reviewer_account_id=actor,snapshot_id=sid,
        review_stage='first_review',members=members)
    winner=[]
    def mutation():
        foreign={**deepcopy(evidence),'snapshot_id':'other-snapshot'}
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(reviews.append_event,event_type='review_object',object_id='foreign',object_version='1.0',
                        actor='another-runtime',details={'snapshot_id':'other-snapshot','review_interaction':foreign}).result(timeout=5)
        winner.append((durable(console,sid),reviews.read_events()))
    before_commit(console,monkeypatch,mutation)
    with pytest.raises(ConsoleError):
        console.batch_review_normal_risk(actor_id=actor,snapshot_id=sid,object_ids=ids,
            expected_revision=_revision(sid,generation),interaction_evidence=evidence)
    assert (durable(console,sid),reviews.read_events())==winner[0]


def test_independent_document_batches_both_commit_across_preparation(
    review_system,tmp_path,production_console,monkeypatch,
):
    from tests.test_a08_heading_batch_atomic import _setup
    first,_client,sid,_actor,ids=review_system
    command=execute(review_system)
    other,accounts,other_sid,other_ids=_setup(tmp_path/'independent',production_console=production_console)
    assert other_sid!=sid
    _,generation=other.workflow_document_store.review_document_input(other_sid)
    outcomes=[]
    def mutation():
        with ThreadPoolExecutor(max_workers=1) as pool:
            outcomes.extend(pool.submit(other.batch_confirm_headings,
                actor_id=accounts['reviewer']['account_id'],snapshot_id=other_sid,
                object_ids=other_ids,expected_revision=_revision(other_sid,generation)).result(timeout=10))
    before_commit(first,monkeypatch,mutation)
    result=command()
    assert {r['object_id'] for r in result}==set(ids)
    assert {r['object_id'] for r in outcomes}==set(other_ids)
    from src.review.review_ledger import verify_ledger
    assert verify_ledger(first._ledger_path)==[]
    assert all(r['governance']['validation_status']=='approved' for r in result+outcomes)


def test_canonical_commit_without_workflow_projection_seals_prepared_batch(
    tmp_path,production_console,monkeypatch,
):
    from tests.test_durable_publication_console_v1 import _ready_console
    console,accounts,receipt=_ready_console(tmp_path,production_console=production_console)
    sid=receipt['snapshot_id']
    ids=[r['object_id'] for r in console.snapshot_objects(sid) if r.get('object_type')=='heading'][:2]
    assert ids
    _,generation=console.workflow_document_store.review_document_input(sid)
    def no_projection(*args,**kwargs):raise ConsoleError('prepared_projection_failure')
    monkeypatch.setattr(console,'_apply_release_state',no_projection)
    monkeypatch.setattr(console,'snapshot_is_published',lambda _sid:False)
    winner=[]
    def mutation():
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(ConsoleError,match='prepared_projection_failure'):
                pool.submit(console.publish,actor_id=accounts['publisher']['account_id'],snapshot_id=sid).result(timeout=15)
        assert console.canonical_publication_store.release_for_snapshot(sid) is not None
        winner.append(durable(console,sid))
    before_commit(console,monkeypatch,mutation)
    with pytest.raises(ConsoleError,match='published_working_revision_immutable'):
        console.batch_confirm_headings(actor_id=accounts['reviewer']['account_id'],snapshot_id=sid,
                                      object_ids=ids,expected_revision=_revision(sid,generation))
    assert winner and durable(console,sid)==winner[0]
    assert console.workflow_review_store._buffer.get() is None


@pytest.mark.parametrize('table',['document_objects','review_events','publish_authorizations'])
@pytest.mark.parametrize('fault',['suppress','rewrite'])
def test_silent_member2_sql_suppression_or_rewrite_is_not_success(review_system,table,fault):
    from psycopg import sql
    console,_client,sid,_actor,ids=review_system
    command=execute(review_system)
    if fault=='suppress':body='RETURN NULL;'
    elif table=='document_objects':
        body="NEW.payload:=jsonb_set(NEW.payload,'{content,clean_text}','\"Unexpected SQL replacement\"'::jsonb); RETURN NEW;"
    elif table=='review_events':body="NEW.event_payload:=jsonb_set(NEW.event_payload,'{details,unexpected}','true'::jsonb,true); RETURN NEW;"
    else:body="NEW.authorization_payload:=jsonb_set(NEW.authorization_payload,'{unexpected}','true'::jsonb,true); RETURN NEW;"
    with console.workflow_document_store._connect() as con:
        con.execute(sql.SQL('CREATE FUNCTION workflow.prepared_silent_fault() RETURNS trigger LANGUAGE plpgsql AS {}').format(sql.Literal('BEGIN '+body+' END;')))
        operation=sql.SQL('INSERT OR UPDATE') if table=='document_objects' else sql.SQL('INSERT')
        con.execute(sql.SQL('CREATE TRIGGER prepared_silent_fault BEFORE {} ON workflow.{} FOR EACH ROW WHEN (NEW.snapshot_id={} AND NEW.object_id={}) EXECUTE FUNCTION workflow.prepared_silent_fault()').format(
            operation,sql.Identifier(table),sql.Literal(sid),sql.Literal(ids[1])))
    before=durable(console,sid)
    with pytest.raises(ConsoleError) as refused:command()
    assert refused.value.code==('snapshot_object_write_conflict' if table=='document_objects' else 'workflow_review_write_failed')
    assert durable(console,sid)==before
    assert console.workflow_review_store._buffer.get() is None


@pytest.mark.parametrize('abort',[False,True])
@pytest.mark.parametrize('buffered',[False,True])
def test_existing_outer_native_transaction_retains_join_and_rollback_contract(review_system,abort,buffered):
    from src.workflows.workflow_transaction_v1 import workflow_transaction
    from contextlib import nullcontext
    console,_client,sid,_actor,ids=review_system
    command=execute(review_system)
    before=durable(console,sid)
    def run():
        with workflow_transaction(console.workflow_review_store), (console.workflow_review_store.buffered() if buffered else nullcontext()):
            result=command()
            assert {r['object_id'] for r in result}==set(ids)
            if abort:raise RuntimeError('original outer caller abort')
    if abort:
        with pytest.raises(RuntimeError,match='original outer caller abort'):run()
        assert durable(console,sid)==before
    else:
        run()
        selected=[r for r in console.snapshot_objects(sid) if r['object_id'] in ids]
        assert all(r['governance']['validation_status']=='approved' for r in selected)
    assert console.workflow_review_store._buffer.get() is None


def test_outer_event_buffer_without_native_transaction_refuses_before_mutation(review_system):
    console,_client,sid,_actor,_ids=review_system
    command=execute(review_system)
    before=durable(console,sid)
    with console.workflow_review_store.buffered():
        with pytest.raises(ConsoleError,match='workflow_review_outer_transaction_required'):
            command()
    assert durable(console,sid)==before
    assert console.workflow_review_store._buffer.get() is None


@pytest.mark.parametrize('preface',[False,True])
def test_buffer_created_before_outer_transaction_is_not_valid_atomic_owner(review_system,preface):
    from src.workflows.workflow_transaction_v1 import workflow_transaction
    console,_client,sid,_actor,_ids=review_system
    command=execute(review_system)
    before=durable(console,sid)
    reviews=console.workflow_review_store
    with reviews.buffered():
        if preface:
            reviews.append_event(event_type='unrelated_parent',object_id='outside',object_version='1.0',
                actor='fixture',details={'snapshot_id':'external'})
        with workflow_transaction(reviews):
            with pytest.raises(ConsoleError,match='workflow_review_outer_transaction_required'):
                command()
    assert durable(console,sid)==before
    assert reviews._buffer.get() is None


@pytest.mark.parametrize('fault',['suppress','rewrite','after_extra'])
def test_bulk_update_checks_actual_second_row_and_same_connection_extra_write(review_system,fault):
    from psycopg import sql
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console=review_system[0]
    store,sid,before,after,envelope=prepared_write(review_system)
    assert len(before)==2
    first=deepcopy(before)
    first[0]['governance']['validation_status']='approved'
    after=deepcopy(first)
    after[1]['governance']['validation_status']='approved'
    handle=store.prepare_review_changes(sid,before,after,envelope,envelope,2,transitions=[first,after])
    if fault=='suppress':body=sql.SQL('RETURN NULL;')
    elif fault=='rewrite':body=sql.SQL("NEW.payload:=jsonb_set(NEW.payload,'{content,clean_text}','\"Rewritten actual row\"'::jsonb); RETURN NEW;")
    else:
        body=sql.SQL("UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id={} AND object_id={}; RETURN NEW;").format(sql.Literal(sid),sql.Literal(before[0]['object_id']))
    timing=sql.SQL('AFTER' if fault=='after_extra' else 'BEFORE')
    with store._connect() as con:
        con.execute(sql.SQL('CREATE FUNCTION workflow.bulk_actual_fault() RETURNS trigger LANGUAGE plpgsql AS {}').format(sql.Literal('BEGIN '+body.as_string(con)+' END;')))
        con.execute(sql.SQL('CREATE TRIGGER bulk_actual_fault {} UPDATE ON workflow.document_objects FOR EACH ROW WHEN (NEW.snapshot_id={} AND NEW.object_id={}) EXECUTE FUNCTION workflow.bulk_actual_fault()').format(
            timing,sql.Literal(sid),sql.Literal(before[1]['object_id'])))
    winner=durable(console,sid)
    with pytest.raises(WorkflowDocumentStoreError,match='snapshot_object_write_conflict'):
        store.apply_prepared_review_changes(sid,handle)
    assert durable(console,sid)==winner


@pytest.mark.parametrize('fault',['suppress','rewrite'])
def test_authorization_renewal_checks_actual_sql_row(review_system,fault):
    from psycopg import sql
    from src.workflows.workflow_review_postgres_v1 import WorkflowReviewStoreError
    console,_client,sid,actor,ids=review_system
    obj=console.workflow_document_store.review_command_current_heads(sid,[ids[0]])[0]
    row={'object_id':ids[0],'object_version':obj['object_version'],
         'canonical_object_hash':compute_canonical_object_hash(obj),
         'confirmed_object_type':obj.get('confirmed_object_type') or obj.get('proposed_object_type'),
         'reviewer_id':actor,'reviewer':console._account(actor)['display_name'],'decision':'approve','valid':True}
    reviews=console.workflow_review_store
    reviews.apply_review_binding_delta(sid,[],[row])
    changed={**deepcopy(row),'valid':False}
    body='RETURN NULL;' if fault=='suppress' else "NEW.authorization_payload:=jsonb_set(NEW.authorization_payload,'{unexpected}','true'::jsonb,true); RETURN NEW;"
    with console.workflow_document_store._connect() as con:
        con.execute(sql.SQL('CREATE FUNCTION workflow.renewal_fault() RETURNS trigger LANGUAGE plpgsql AS {}').format(sql.Literal('BEGIN '+body+' END;')))
        con.execute('CREATE TRIGGER renewal_fault BEFORE UPDATE ON workflow.publish_authorizations FOR EACH ROW EXECUTE FUNCTION workflow.renewal_fault()')
    winner=durable(console,sid)
    with pytest.raises(WorkflowReviewStoreError,match='workflow_review_binding_write_conflict'):
        reviews.apply_review_binding_delta(sid,[row],[changed])
    assert durable(console,sid)==winner


def test_binding_metadata_typed_json_is_written_and_stale_input_refused(review_system):
    from src.workflows.workflow_review_postgres_v1 import WorkflowReviewStoreError
    console,_client,sid,actor,ids=review_system
    obj=console.workflow_document_store.review_command_current_heads(sid,[ids[0]])[0]
    row={'object_id':ids[0],'object_version':obj['object_version'],
         'canonical_object_hash':compute_canonical_object_hash(obj),
         'confirmed_object_type':obj.get('confirmed_object_type') or obj.get('proposed_object_type'),
         'reviewer_id':actor,'reviewer':console._account(actor)['display_name'],
         'decision':'approve','valid':True,'metadata_score':1}
    reviews=console.workflow_review_store
    reviews.apply_review_binding_delta(sid,[],[row])
    changed={**deepcopy(row),'metadata_score':1.0}
    assert changed==row  # Python equality would silently drop this exact JSON write.
    reviews.apply_review_binding_delta(sid,[row],[changed])
    stored=reviews.read_bindings([sid],object_ids=[ids[0]])[sid][0]
    assert type(stored['metadata_score']) is float
    winner=durable(console,sid)
    with pytest.raises(WorkflowReviewStoreError,match='snapshot_object_write_conflict'):
        reviews.apply_review_binding_delta(sid,[row],[{**row,'valid':False}])
    assert durable(console,sid)==winner


def test_generation_structure_batch_preserves_decision_tree_path_contract(tmp_path,production_console):
    from tests.test_v225_beslisboom_path import _console,_accounts,_ingest_boom
    console=_console(tmp_path,production_console=production_console)
    accounts=_accounts(console)
    sid=_ingest_boom(console,accounts)['snapshot_id']
    ids=[r['object_id'] for r in console.snapshot_objects(sid)
         if (r.get('proposed_object_type') or r.get('object_type'))=='path']
    assert ids
    _,generation=console.workflow_document_store.review_document_input(sid)
    result=console.batch_confirm_headings(actor_id=accounts['reviewer']['account_id'],snapshot_id=sid,
        object_ids=ids,expected_revision=_revision(sid,generation))
    assert {r['object_id'] for r in result}==set(ids)
    assert all(r['confirmed_object_type']=='path' for r in result)
    fresh={r['object_id']:r for r in console.snapshot_objects(sid)}
    assert all(fresh[oid]['confirmed_object_type']=='path' for oid in ids)


@pytest.mark.parametrize('fault',['suppress','rewrite','hash','after_extra'])
def test_bulk_frontier_install_refuses_actual_second_row_fault(review_system,fault):
    from psycopg import sql
    console,_client,sid,_actor,ids=review_system
    command=execute(review_system)
    body={'suppress':'RETURN NULL;',
          'rewrite':"NEW.certificate:=jsonb_set(NEW.certificate,'{head_version}','\"unexpected\"'::jsonb); RETURN NEW;",
          'hash':"NEW.certificate_hash:='wrong'; RETURN NEW;",'after_extra':''}[fault]
    if fault=='after_extra':
        body=sql.SQL('UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id={} AND object_id={}; RETURN NEW;').format(sql.Literal(sid),sql.Literal(ids[0])).as_string()
    with console.workflow_document_store._connect() as con:
        con.execute(sql.SQL('CREATE FUNCTION workflow.frontier_set_fault() RETURNS trigger LANGUAGE plpgsql AS {}').format(sql.Literal('BEGIN '+body+' END;')))
        con.execute(sql.SQL('CREATE TRIGGER frontier_set_fault {} UPDATE ON workflow.object_revision_frontiers FOR EACH ROW WHEN (NEW.snapshot_id={} AND NEW.object_id={} AND NEW.certificate IS NOT NULL) EXECUTE FUNCTION workflow.frontier_set_fault()').format(sql.SQL('AFTER' if fault=='after_extra' else 'BEFORE'),sql.Literal(sid),sql.Literal(ids[1])))
    before=durable(console,sid)
    with pytest.raises(ConsoleError):command()
    assert durable(console,sid)==before
    assert console.workflow_review_store._buffer.get() is None


def test_prepared_audit_set_checks_relational_projection(review_system):
    from psycopg import sql
    console,_client,sid,_actor,ids=review_system
    command=execute(review_system)
    with console.workflow_document_store._connect() as con:
        con.execute("CREATE FUNCTION workflow.audit_projection_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN NEW.event_type:='unexpected'; RETURN NEW; END; $$")
        con.execute(sql.SQL('CREATE TRIGGER audit_projection_fault BEFORE INSERT ON workflow.review_events FOR EACH ROW WHEN (NEW.snapshot_id={} AND NEW.object_id={}) EXECUTE FUNCTION workflow.audit_projection_fault()').format(sql.Literal(sid),sql.Literal(ids[1])))
    before=durable(console,sid)
    with pytest.raises(ConsoleError,match='workflow_review_write_failed'):command()
    assert durable(console,sid)==before
    assert console.workflow_review_store._buffer.get() is None


def test_frontier_set_final_check_covers_unchanged_captured_dependency(review_system):
    from psycopg import sql
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console=review_system[0]
    store,sid,before,after,envelope=prepared_write(review_system)
    assert len(before)==2
    assert after[1]==before[1]
    handle=store.prepare_review_changes(sid,before,after,envelope,envelope,transitions=[after])
    with store._connect() as con:
        body=sql.SQL('BEGIN UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id={} AND object_id={}; RETURN NEW; END;').format(sql.Literal(sid),sql.Literal(before[1]['object_id'])).as_string(con)
        con.execute(sql.SQL('CREATE FUNCTION workflow.unchanged_dependency_fault() RETURNS trigger LANGUAGE plpgsql AS {}').format(sql.Literal(body)))
        con.execute(sql.SQL('CREATE TRIGGER unchanged_dependency_fault AFTER UPDATE ON workflow.object_revision_frontiers FOR EACH ROW WHEN (NEW.snapshot_id={} AND NEW.object_id={} AND NEW.certificate IS NOT NULL) EXECUTE FUNCTION workflow.unchanged_dependency_fault()').format(sql.Literal(sid),sql.Literal(before[0]['object_id'])))
    winner=durable(console,sid)
    with pytest.raises(WorkflowDocumentStoreError,match='snapshot_object_write_conflict'):
        store.apply_prepared_review_changes(sid,handle)
    assert durable(console,sid)==winner
