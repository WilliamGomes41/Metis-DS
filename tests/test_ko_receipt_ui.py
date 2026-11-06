"""KO-2 receipt uses committed evidence and preserves the normal review route.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import html
import re
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from src.review.ko_receipt_ui_v1 import read_saved_review, render_ko_receipt
from tests.test_review_command_bounded_http_v1 import submission
from tests.test_review_formation_problems import received, execute
from tests.test_availability_repair import login
from tests.production_support import restart_production


def prepared(tmp_path, production_console, monkeypatch, *, source_html=None):
    console, sid, author, reviewer, calls, mode, provider = received(
        tmp_path, production_console, monkeypatch, source_html=source_html)
    mode['broken'] = False
    execute(console, sid, author, 'ko2-start')
    obj = next(row for row in console.snapshot_objects(sid) if row.get('proposed_object_type') == 'recommendation')
    client = TestClient(console._metis_test_application)
    login(client, 'reviewer')
    page = client.get('/review', params={'document': sid, 'object': obj['object_id'], 'task': 'contextual'})
    data = submission(page, sid, obj)
    data['interaction_id'] = re.search(r'name="interaction_id" value="([^"]+)"', page.text).group(1)
    return console, sid, reviewer, obj, client, page, data


def test_card_then_exact_receipt_after_durable_save_and_restart(tmp_path, production_console, monkeypatch):
    console, sid, reviewer, obj, client, page, data = prepared(tmp_path, production_console, monkeypatch)
    assert page.status_code == 200
    assert 'data-review-receipt' not in page.text
    assert 'Bekijk in documentcontext' in page.text
    assert 'Is dit toepasbaar?' in page.text and 'Is dit compleet?' in page.text
    assert 'Staat dit op de juiste plek?' in page.text
    assert not re.search(r'<input[^>]+type="radio"[^>]+checked', page.text)
    response = client.post('/review', data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert parse_qs(urlsplit(response.headers['location']).query)['receipt_interaction'] == [data['interaction_id']]
    direct = read_saved_review(console, console._account(reviewer), sid, obj['object_id'], data['interaction_id'])
    assert direct is not None
    result = client.get(response.headers['location'])
    assert result.status_code == 200, result.text
    assert 'data-review-receipt' in result.text
    assert html.escape(obj['content']['clean_text']) in result.text
    assert 'Dit heb je goedgekeurd' in result.text
    assert 'Zo is het kennisobject vastgelegd' in result.text
    assert 'data-knowledge-connections' in result.text
    receipt = read_saved_review(console, console._account(reviewer), sid, obj['object_id'], data['interaction_id'])
    assert receipt is not None
    restarted = restart_production(console)
    reopened = read_saved_review(restarted, restarted._account(reviewer), sid, obj['object_id'], data['interaction_id'])
    assert reopened is not None
    assert reopened.event == receipt.event
    assert reopened.object['content'] == receipt.object['content']


def test_unknown_or_foreign_interaction_cannot_claim_success(tmp_path, production_console, monkeypatch):
    console, sid, reviewer, obj, client, page, data = prepared(tmp_path, production_console, monkeypatch)
    response = client.get('/review', params={'document': sid, 'object': obj['object_id'],
        'receipt_interaction': 'ri_missing', 'receipt_object': obj['object_id']})
    assert response.status_code == 200
    assert 'data-review-receipt' not in response.text
    assert 'data-review-outcome-unconfirmed' in response.text
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303
    altered = client.get('/review', params={'document': sid, 'receipt_interaction': data['interaction_id'],
        'receipt_object': 'different-object'})
    assert altered.status_code == 200
    assert 'data-review-receipt' not in altered.text
    assert 'data-review-outcome-unconfirmed' in altered.text


def test_stale_save_has_no_receipt_and_complete_context_is_read_only(tmp_path, production_console, monkeypatch):
    console, sid, reviewer, obj, client, page, data = prepared(tmp_path, production_console, monkeypatch)
    before = console.objects_revision(sid)
    expanded = client.get('/review/context-section', params={'document': sid, 'object': obj['object_id']})
    assert expanded.status_code == 200, expanded.text
    assert 'Hele sectie en naburige bronpassages' in expanded.text
    assert 'data-full-section' in expanded.text
    assert console.objects_revision(sid) == before
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303
    stale = client.post('/review', data=data, follow_redirects=False)
    assert stale.status_code == 409, stale.text
    assert 'data-review-receipt' not in stale.text


def test_original_outline_and_adjacent_paragraphs_use_scoped_immutable_source(tmp_path, production_console, monkeypatch):
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    source = (b'<html><body><h1>Richtlijn</h1><h2>Huidzorg</h2>'
        b'<p>Gebruik geen zalf.</p><p>Controleer dagelijks de huid.</p>'
        b'<p>Bespreek de verzorging.</p><h2>Evaluatie</h2><p>Evalueer morgen.</p></body></html>')
    console, sid, author, reviewer, calls, mode, provider = received(
        tmp_path, production_console, monkeypatch, source_html=source)
    mode['broken'] = False
    execute(console, sid, author, 'ko2-context')
    obj = next(row for row in console.snapshot_objects(sid)
        if (row.get('content') or {}).get('clean_text') == 'Controleer dagelijks de huid.')
    before = console.objects_revision(sid)
    original = FormationTaskStore.read_review_source
    source_reads = []
    def bounded(self, envelope, *, objects=None, con=None):
        source_reads.append(objects)
        return original(self, envelope, objects=objects, con=con)
    monkeypatch.setattr(FormationTaskStore, 'read_review_source', bounded)
    client = TestClient(console._metis_test_application)
    login(client, 'reviewer')
    page = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert page.status_code == 200
    assert len(source_reads) == 1
    assert 'Koppen uit de vastgelegde oorspronkelijke bron.' in page.text
    panel = re.search(r'<details class="ko-document-context"[^>]*>(.*?)</details>', page.text, re.S)
    assert panel is not None
    text = html.unescape(re.sub('<[^>]+>', ' ', panel.group(1)))
    assert 'Richtlijn' in text and 'Huidzorg' in text and 'Evaluatie' in text
    assert 'Gebruik geen zalf.' in text and 'Bespreek de verzorging.' in text
    assert 'Evalueer morgen.' not in text
    assert console.objects_revision(sid) == before


def test_bon_excludes_later_noncanonical_admission_and_governance(tmp_path, production_console, monkeypatch):
    import json
    console, sid, reviewer, obj, client, page, data = prepared(tmp_path, production_console, monkeypatch)
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303
    before = read_saved_review(console, console._account(reviewer), sid, obj['object_id'], data['interaction_id'])
    assert before is not None
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload, '{metadata,admission}', %s::jsonb) "
            "WHERE snapshot_id=%s AND object_id=%s", (json.dumps({'context_scan': {'required_context': [
                {'role': 'condition', 'text': 'Deze latere aanname is geen oorspronkelijk reviewbewijs.'}]}}), sid, obj['object_id']))
    after = read_saved_review(console, console._account(reviewer), sid, obj['object_id'], data['interaction_id'])
    assert after is not None
    assert after.object == before.object
    assert 'Deze latere aanname' not in render_ko_receipt(after)


def test_bon_keeps_confirmed_condition_and_support_with_readable_exact_targets(tmp_path, production_console):
    from tests.test_d4_3_human_relation_confirmation import _console, _accounts, _ingest, _plant_proposals, COND, REC, EXPL
    from src.review.knowledge_relation_review_v1 import relation_choice_value
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    sid = _ingest(console, accounts)['snapshot_id']
    obj, proposals = _plant_proposals(console, sid)
    client = TestClient(console._metis_test_application)
    assert client.post('/login', data={'username': 'reviewer.d43', 'password': 'reviewer-secret'},
        follow_redirects=False).status_code == 303
    page = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    primary_context = re.search(r'<section data-essential-context[^>]*>(.*?)</section>', page.text, re.S)
    assert primary_context is not None
    assert COND in html.unescape(primary_context.group(1)) and EXPL in html.unescape(primary_context.group(1))
    assert 'Voorstel, nog niet bevestigd' in primary_context.group(1)
    assert 'Geen afzonderlijke onderbouwing gekoppeld.' not in primary_context.group(1)
    data = submission(page, sid, obj)
    data['interaction_id'] = re.search(r'name="interaction_id" value="([^"]+)"', page.text).group(1)
    data['relation_choice'] = [relation_choice_value(row) for row in proposals]
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    result = client.get(saved.headers['location'])
    assert result.status_code == 200
    receipt = read_saved_review(console, console._account(accounts['reviewer']['account_id']),
        sid, obj['object_id'], data['interaction_id'])
    assert receipt is not None
    output = render_ko_receipt(receipt)
    assert REC in output and COND in output and EXPL in output
    assert 'Geldt wanneer' in output and 'Onderbouwd door' in output
    assert 'Voorstel, nog niet bevestigd' not in output
    assert 'Geen afzonderlijke uitzondering vastgelegd.' in output
    assert len(receipt.related) >= 2


def test_display_source_rejects_tampering_even_with_rewritten_raw_checksum(tmp_path, production_console, monkeypatch):
    import json
    import pytest
    from src.integrity_kernel import stable_hash
    from src.review.review_passage_read_v1 import read_review_passage
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    from tests.test_review_formation_problems import FIRST, SECOND
    source = f'<html><body><h1>Advies</h1><p>{FIRST}</p><p>{SECOND}</p></body></html>'.encode()
    console, sid, reviewer, obj, client, page, data = prepared(
        tmp_path, production_console, monkeypatch, source_html=source)
    inputs = read_review_passage(console, console._account(reviewer), sid, obj['object_id'])
    owner = FormationTaskStore(console.workflow_document_store)
    original = owner.read_review_document_context(inputs.envelope, obj, source=inputs.fragments)
    assert original and any(row.get('clean_text') == SECOND for row in original.fragments)
    with console.workflow_document_store._connect() as con:
        row = con.execute("SELECT * FROM workflow.source_read_fragments WHERE views_id=%s "
            "AND payload->>'clean_text'=%s", (inputs.fragments.root.reference['views_id'], SECOND)).fetchone()
        assert row is not None
        con.execute('ALTER TABLE workflow.source_read_fragments DISABLE TRIGGER ALL')
        row['payload']['clean_text'] = 'Deze tekst stond niet in de oorspronkelijke bron.'
        con.execute('UPDATE workflow.source_read_fragments SET payload=%s::jsonb WHERE views_id=%s AND fragment_id=%s',
            (json.dumps(row['payload']), row['views_id'], row['fragment_id']))
    with pytest.raises(WorkflowDocumentStoreError, match='source_read_integrity_failed'):
        owner.read_review_document_context(inputs.envelope, obj, source=inputs.fragments)
    digest = stable_hash({key: row[key] for key in ('ordinal','views','blocks','payload')})
    with console.workflow_document_store._connect() as con:
        con.execute('UPDATE workflow.source_read_fragments SET payload_hash=%s WHERE views_id=%s AND fragment_id=%s',
            (digest, row['views_id'], row['fragment_id']))
    with pytest.raises(WorkflowDocumentStoreError, match='source_read_integrity_failed'):
        owner.read_review_document_context(inputs.envelope, obj, source=inputs.fragments)
