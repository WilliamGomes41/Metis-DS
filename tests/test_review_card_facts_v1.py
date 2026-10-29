"""Explicit intrinsic card inputs preserve the existing Review owners.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json

import pytest

from src.review.review_card_facts_v1 import (
    ReviewObjectFacts, ReviewFactSources, prepare_source_proof, prepare_object_facts,
)
from src.review.review_workboard_v1 import ReviewWorkInputs, review_work_item
from tests.personal_review_fixture_support import bind, prepare


def facts_for(objects, fragments):
    return [ReviewObjectFacts(prepare_object_facts(obj, proof=prepare_source_proof(obj, fragments)))
            for obj in objects]


def test_mixed_card_facts_preserve_full_oracle_without_source_reads(tmp_path, production_console, monkeypatch):
    console = production_console(root=tmp_path, processing_binder=bind)
    accounts, docs = prepare(console)
    for doc in docs.values():
        sid = doc['snapshot_id']
        envelope = console._envelope(sid)
        objects = console.snapshot_objects(sid)
        fragments = console.review_source_fragments(sid)
        facts = facts_for(objects, fragments)
        assert all('content' not in row for row in facts)
        with pytest.raises(TypeError):
            json.dumps(facts[0])  # Cannot accidentally persist the projection as a KnowledgeObject.
        for account in (accounts['a'], accounts['b'], accounts['outsider']):
            expected = review_work_item(console, account=account, envelope=envelope)
            inputs = ReviewWorkInputs(facts, console.object_review_bindings(sid),
                console.document_lifecycle_status(sid), console.snapshot_is_published(sid), ReviewFactSources(tuple(facts)))
            with monkeypatch.context() as patch:
                patch.setattr(console, 'review_source_fragments', lambda *a, **k: pytest.fail('Card read raw source'))
                actual = review_work_item(console, account=account, envelope=envelope, inputs=inputs)
            assert actual == expected


def test_proofs_are_intrinsic_immutable_and_capture_bound(tmp_path, production_console):
    from tests.test_d5_4_review_interaction_evidence import _system
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    objects = console.snapshot_objects(sid)
    fragments = console.review_source_fragments(sid)
    facts = facts_for(objects, fragments)
    sources = ReviewFactSources(tuple(facts))
    with pytest.raises(ValueError, match='capture_mismatch'):
        sources.proof_for(facts_for(objects, fragments)[0])
    with pytest.raises(Exception, match='immutable'):
        facts[0]['governance']['validation_status'] = 'approved'
    obj = deepcopy(next(o for o in objects if o.get('content', {}).get('clean_text')))
    proof = prepare_source_proof(obj, fragments)
    obj['content']['clean_text'] += ' different'
    with pytest.raises(ValueError, match='source_input_mismatch'):
        prepare_object_facts(obj, proof=proof)


def test_explicit_preparation_then_native_writer_seals_current_card_inputs(tmp_path, production_console):
    from tests.test_d5_4_review_interaction_evidence import _system
    from src.workflows.review_card_inputs_postgres_v1 import capture_review_cards, prepare_review_cards
    console, users, sid, oid = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    # This helper deliberately replaces native history through SQL. It must
    # invalidate the original ingestion's facts until explicit preparation.
    with store._connect() as con:
        assert 'unavailable' in capture_review_cards(store, con, [sid])[sid]
    prepare_review_cards(store, sid)
    console.review_object(actor_id=users['reviewer_a']['account_id'], snapshot_id=sid,
                          object_id=oid, decision='approve', confirmed_object_type='definition')
    with console.workflow_document_store._connect() as con:
        captured = capture_review_cards(console.workflow_document_store, con, [sid])[sid]
        state = con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s',(sid,)).fetchone()
    assert 'unavailable' not in captured, state
    assert {o['object_id'] for o in captured['objects']} == {o['object_id'] for o in console.snapshot_objects(sid)}


@pytest.mark.parametrize('damage',[None, 'bad_link_text', 'bad_role', 'bound_context_none', 'bound_context_bad_entries'])
def test_context_primitives_preserve_full_oracle(tmp_path, production_console, damage):
    from tests.test_source_context_review_v1 import _system
    from src.review.source_context_review_v1 import context_issues
    from src.vorming.source_containers_v1 import source_accountability
    console, author, reviewer, source, target, command = _system(tmp_path, production_console=production_console)
    console.confirm_source_context(**command)
    sid = command['snapshot_id']
    if damage is None:
        # The actual context command must seal affected facts, including a
        # partially formed source; not only the pure carrier comparison below.
        console.review_card_read_mode = 'compact'
        actual = console.review_workboard_summaries(reviewer['account_id'], sid)[sid]['work_item']
        expected = review_work_item(console, account=reviewer, envelope=console._envelope(sid))
        expected['envelope'] = actual['envelope']
        assert actual == expected
    objects = console.snapshot_objects(sid)
    fragments = console.review_source_fragments(sid)
    by_id = {o['object_id']:o for o in objects}
    if damage == 'bad_link_text':
        by_id[target['object_id']]['metadata']['confirmed_source_context'][0]['text'] = None
    if damage == 'bad_role':
        by_id[source['object_id']]['metadata']['source_role_review'] = 'bad'
    if damage == 'bound_context_none':
        by_id[target['object_id']]['metadata']['source_bound_context'] = None
    if damage == 'bound_context_bad_entries':
        by_id[target['object_id']]['metadata']['source_bound_context'] = {'entries':[None]}
    facts = facts_for(objects, fragments)
    assert context_issues(facts) == context_issues(objects)
    assert source_accountability(facts, fragments=ReviewFactSources(tuple(facts)), bindings=[]) == source_accountability(objects, fragments=fragments, bindings=[])


def test_fact_payload_does_not_repeat_passage_archives(tmp_path, production_console):
    from tests.test_d5_4_review_interaction_evidence import _system
    console, users, sid, oid = _system(tmp_path, production_console=production_console)
    obj = next(o for o in console.snapshot_objects(sid) if o['object_id'] == oid)
    canary = 'passage-archive-canary-' + ('z' * 65536)
    obj['metadata']['admission'].update(candidate_text=canary, source_text_exact=canary)
    obj['metadata']['candidate_eligibility'] = {'archive':canary}
    obj['provenance']['source_fragments'][0]['raw_span_text'] = canary
    record = prepare_object_facts(obj, proof=prepare_source_proof(obj, console.review_source_fragments(sid)))
    encoded = json.dumps(record)
    assert canary not in encoded
    assert len(encoded) < 12000


def test_graph_card_facts_preserve_review_and_confirmation_states(tmp_path, production_console):
    from tests.test_v225_beslisboom_path import _console, _accounts
    from tests.test_decision_graph_chain import ingest, complete_graph, command
    from src.review.review_card_facts_v1 import ReviewGraphInventory
    from src.vorming.decision_graph_v1 import graph_issues
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    sid = ingest(console, accounts, 'required')['snapshot_id']

    def parity():
        objects = console.snapshot_objects(sid)
        facts = facts_for(objects, None)
        envelope = console._envelope(sid)
        with console.workflow_document_store._connect() as con:
            compact = con.execute("SELECT review_card_envelope->'decision_graph_evidence' AS inventory "
                                  "FROM workflow.documents WHERE snapshot_id=%s",(sid,)).fetchone()['inventory']
        inventory = ReviewGraphInventory(compact)
        for who in ('researcher','reviewer'):
            account = accounts[who]
            inputs = ReviewWorkInputs(facts, console.object_review_bindings(sid),
                console.document_lifecycle_status(sid), False, ReviewFactSources(tuple(facts)), inventory)
            assert review_work_item(console,account=account,envelope=envelope,inputs=inputs) == review_work_item(console,account=account,envelope=envelope)
        return envelope, objects, facts, inventory

    parity()

    console.update_decision_graph(**command(console,accounts,sid,'facts-initial-graph',graph=complete_graph(console,sid)))
    for obj in console.snapshot_objects(sid):
        if obj['object_type'] != 'document':
            console.review_object(actor_id=accounts['researcher']['account_id'],snapshot_id=sid,
                object_id=obj['object_id'],decision='approve',confirmed_object_type='node')
    console.update_decision_graph(**command(console,accounts,sid,'facts-current-graph',graph=complete_graph(console,sid)))
    console.confirm_decision_graph(**command(console,accounts,sid,'facts-confirm-primary'))
    envelope, objects, facts, inventory = parity()
    # Exercise literal label comparisons independently of graph validity.
    altered = deepcopy(envelope['decision_graph'])
    evidence_id = next(k for k,v in envelope['decision_graph_evidence']['items'].items() if v.get('kind') == 'text')
    altered['edges'][0].update(kind='answer',label=envelope['decision_graph_evidence']['items'][evidence_id]['text'])
    altered['edges'][0]['evidence_ids'].append(evidence_id)
    assert graph_issues(altered,objects,envelope['decision_graph_evidence']) == graph_issues(altered,facts,inventory)
    altered['edges'][0]['label'] += ' wrong'
    assert 'decision_graph_label_not_literal' in graph_issues(altered,facts,inventory)
    for obj in console.snapshot_objects(sid):
        if obj['object_type'] != 'document':
            console.approve_second_review(actor_id=accounts['reviewer']['account_id'],snapshot_id=sid,object_id=obj['object_id'])
    cmd = command(console,accounts,sid,'facts-confirm-secondary')
    cmd['actor_id'] = accounts['reviewer']['account_id']
    console.confirm_decision_graph(**cmd)
    parity()


@pytest.mark.parametrize('azure',[False,True])
def test_native_http_compact_overview_does_not_load_source_or_history(tmp_path, production_console, production_app, monkeypatch, azure):
    from tests.test_d5_4_review_interaction_evidence import _system, PASSWORD
    from fastapi.testclient import TestClient
    from src.workflows.review_card_inputs_postgres_v1 import prepare_review_cards
    console, users, sid, _ = _system(tmp_path, production_console=lambda **options: production_console(
        azure=azure,environment={'CONSOLE_REVIEW_CARD_READS':'compact'},**options))
    prepare_review_cards(console.workflow_document_store,sid)
    client = TestClient(production_app(console),base_url='https://console.example.test' if azure else 'https://testserver',
                        headers={'Origin':'https://console.example.test'} if azure else {})
    assert client.post('/login',data={'username':users['reviewer_a']['username'],'password':PASSWORD},follow_redirects=False).status_code == 303
    expected = console.review_workboard_summaries(users['reviewer_a']['account_id'])[sid]['work_item']
    with console.workflow_document_store._connect() as con:
        before = con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s',(sid,)).fetchone()
    def forbidden(*args,**kwargs):
        pytest.fail('Compact overview read full source/history or processing status')
    monkeypatch.setattr(console,'review_source_fragments',forbidden)
    monkeypatch.setattr(console,'_verified_source_bytes',forbidden)
    monkeypatch.setattr(console,'processing_status',forbidden)
    monkeypatch.setattr(console.workflow_document_store,'list_current_objects_batch',forbidden)
    monkeypatch.setattr(console.workflow_document_store,'review_document_input',forbidden)
    monkeypatch.setattr('src.vorming.prepared_source_views_v1.prepare',forbidden)
    page = client.get('/review')
    assert page.status_code == 200 and f'data-personal-open>{expected["actionable_review_duties"]}<' in page.text
    assert 'data-card-source-check' in page.text and sid in page.text
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s',(sid,)).fetchone() == before


def test_native_http_missing_facts_are_visible_and_never_zero(tmp_path, production_console, production_app):
    from tests.test_d5_4_review_interaction_evidence import _system
    from tests.test_insight_v1 import _login
    console, users, sid, _ = _system(tmp_path,production_console=lambda **options: production_console(
        environment={'CONSOLE_REVIEW_CARD_READS':'compact'},**options))
    client = _login(console,users['reviewer_a']['username'],production_app=production_app)
    page = client.get('/review')
    assert page.status_code == 200
    assert 'data-personal-state="unavailable"' in page.text
    assert 'Het aantal open beoordelingen is onbekend' in page.text
    assert 'Geen open beoordeling voor jou' not in page.text
    assert 'data-personal-open' not in page.text and 'data-personal-review-action' not in page.text


def test_card_uses_retained_extraction_but_corrupt_original_still_blocks_review(tmp_path,production_console,production_app):
    from tests.test_d5_4_review_interaction_evidence import _system
    from tests.test_insight_v1 import _login
    from src.operations_console_v1 import ConsoleError
    from src.workflows.review_card_inputs_postgres_v1 import prepare_review_cards
    console,users,sid,oid = _system(tmp_path,production_console=lambda **options: production_console(
        environment={'CONSOLE_REVIEW_CARD_READS':'compact'},**options))
    prepare_review_cards(console.workflow_document_store,sid)
    client = _login(console,users['reviewer_a']['username'],production_app=production_app)
    before = client.get('/review').text
    assert 'data-personal-open>1<' in before
    objects = console.workflow_document_store.list_document_objects(sid)
    bindings = console.object_review_bindings(sid)
    source = console._source_cache_path(console._envelope(sid))
    original = source.read_bytes()
    try:
        source.write_bytes(b'x'*len(original))
        after = client.get('/review')
        assert after.status_code==200 and 'data-personal-open>1<' in after.text
        assert 'data-card-source-check' in after.text
        with pytest.raises(ConsoleError):
            console.review_object(actor_id=users['reviewer_a']['account_id'],snapshot_id=sid,
                object_id=oid,decision='approve',confirmed_object_type='definition')
        assert console.workflow_document_store.list_document_objects(sid)==objects
        assert console.object_review_bindings(sid)==bindings
    finally:
        source.write_bytes(original)


def test_binding_only_changes_and_live_role_revocation_need_no_fact_rebuild(tmp_path, production_console, production_app):
    from tests.test_d5_4_review_interaction_evidence import _system
    from tests.test_insight_v1 import _login
    from src.workflows.review_card_inputs_postgres_v1 import prepare_review_cards
    console, users, sid, oid = _system(tmp_path, production_console=lambda **options: production_console(
        environment={'CONSOLE_REVIEW_CARD_READS':'compact'}, **options))
    store = console.workflow_document_store
    prepare_review_cards(store, sid)
    actor = users['reviewer_a']
    client = _login(console, actor['username'], production_app=production_app)
    assert 'data-personal-open>1<' in client.get('/review').text
    console.review_object(actor_id=actor['account_id'], snapshot_id=sid, object_id=oid,
                          decision='approve', confirmed_object_type='definition')
    assert 'data-personal-open>1<' not in client.get('/review').text
    with store._connect() as con:
        before = con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s', (sid,)).fetchone()
    bindings = console.workflow_review_store.read_bindings([sid])[sid]
    assert any(row['valid'] for row in bindings)
    for row in bindings:
        row['valid'] = False
    console.workflow_review_store.replace_snapshot_bindings(sid, bindings)
    assert 'data-personal-open>1<' in client.get('/review').text
    with store._connect() as con:
        assert con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s', (sid,)).fetchone() == before
    console.workflow_identity_store.update_roles(actor['account_id'], ['researcher'])
    denied = client.get('/review')
    assert denied.status_code == 403
    assert 'data-personal-open' not in denied.text


def test_participation_policy_changes_use_current_oracle_and_writers(tmp_path, production_console):
    from src.workflows.review_card_inputs_postgres_v1 import prepare_review_cards
    from tests.test_review_participation_management import change
    console = production_console(root=tmp_path, processing_binder=bind,
                                 environment={'CONSOLE_REVIEW_CARD_READS':'compact'})
    accounts, docs = prepare(console)
    sid = docs['Wachten']['snapshot_id']
    publisher = console.create_account(username='card-policy-owner', password='test-only-policy', roles=('publisher',))
    for doc in docs.values():
        prepare_review_cards(console.workflow_document_store, doc['snapshot_id'])

    def parity():
        for actor in accounts.values():
            summaries = console.review_workboard_summaries(actor['account_id'], sid)
            if sid not in summaries:
                continue
            envelope = summaries[sid]['envelope']
            item = summaries[sid]['work_item']
            expected = review_work_item(console, account=actor, envelope=console._envelope(sid))
            # The oracle receives its full source envelope; compare every
            # decision field while the card intentionally carries less metadata.
            expected['envelope'] = envelope
            assert item == expected
            assert 'unavailable' not in item

    parity()
    actors = {**accounts, 'publisher':publisher}
    change(console, actors, sid, 'add_required', accounts['outsider']['account_id'])
    parity()
    change(console, actors, sid, 'archive', accounts['b']['account_id'])
    parity()
def test_reference_equality_keeps_numeric_representation_parity():
    from src.review.source_context_review_v1 import CONTRACT, literal_identity, context_issues
    source={'object_id':'source','object_version':'1.0','content':{'clean_text':'context'},'source':{'source_checksum':'a'*64},'provenance':{'source_fragments':[{'raw_object_id':'raw','bbox':[1,2,3,4]}]},'metadata':{}}
    target={'object_id':'target','object_version':'1.0','content':{'clean_text':'target'},'source':{'source_checksum':'a'*64},'metadata':{}}
    source['metadata']['source_role_review']={'version':CONTRACT,'role':'context','command_id':'command','reviewer_id':'human','reason':'bounded proof','source_sha256':'a'*64,'literal_hash':literal_identity(source)}
    refs=deepcopy(source['provenance']['source_fragments'])
    refs[0]['bbox']=[1.0,2.0,3.0,4.0]
    target['metadata']['confirmed_source_context']=[{'version':CONTRACT,'source_object_id':'source','source_object_version':'1.0','source_literal_hash':literal_identity(source),'target_literal_hash':literal_identity(target),'text':'context','source_fragments':refs,'reviewer_id':'human','target_object_id':'target','role':'context','source_sha256':'a'*64,'command_id':'command','reason':'bounded proof'}]
    rows=[source,target]
    facts=[ReviewObjectFacts(prepare_object_facts(o,proof=prepare_source_proof(o,None))) for o in rows]
    assert context_issues(rows)=={}
    assert context_issues(facts)==context_issues(rows)
    refs[0]['bbox'][-1] = 4.25
    changed = facts_for(rows, None)
    assert context_issues(changed) == context_issues(rows)
    assert 'target' in context_issues(changed)
