"""Passage-first context decisions through the real HTTP/domain boundary.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from html.parser import HTMLParser

from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app, _source_context_panel
from src.review_closure_v1 import ReviewClosureConsole
from src.source_context_review_v1 import links_of, role_of
from tests.test_source_context_review_v1 import _system


class Forms(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            assert self.current is None, 'Context forms must not nest inside knowledge review'
            self.current = {'attrs': attrs, 'inputs': []}
            self.forms.append(self.current)
        if tag == 'input' and self.current is not None:
            self.current['inputs'].append(attrs)

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


def _client(state, username='bert', password='bert-secret'):
    client = TestClient(create_console_app(state))
    assert client.post('/login', data={'username': username, 'password': password}, follow_redirects=False).status_code == 303
    return client


def _link_form(page):
    return next(form for form in Forms(page.text).forms if 'data-source-context-form' in form['attrs'])


def _payload(form, role='label', reason='Dit label hoort bij de geselecteerde passages.'):
    values = {field['name']: field.get('value', '') for field in form['inputs'] if field.get('type') == 'hidden'}
    values.update(role=role, reason=reason, source_checked='1')
    values['target_object_ids'] = [field['value'] for field in form['inputs']
                                 if field.get('name') == 'target_object_ids' and 'checked' in field]
    return values


def test_passage_first_navigation_preserves_existing_targets_and_reopens_reviews(tmp_path):
    state, _, reviewer, source, target, command = _system(tmp_path)
    sid = command['snapshot_id']
    client = _client(state)
    before = deepcopy(state.snapshot_objects(sid))
    page = client.get('/review', params={'document': sid, 'object': target['object_id']})
    assert page.status_code == 200
    assert 'Context toevoegen uit de bron' in page.text
    assert 'Bronrol en contextkoppeling' not in page.text
    assert 'data-source-context-form' not in page.text
    assert page.text.index('data-passage-context') < page.text.index('data-review-form')
    Forms(page.text)  # Reject browser-invalid nested forms.
    label_page = client.get('/review', params={'document': sid, 'object': source['object_id'], 'context_target': target['object_id']})
    form = _link_form(label_page)
    assert not any('checked' in field for field in form['inputs'] if field.get('name') == 'role')
    assert 'Passage waarvoor je context kiest' in label_page.text
    assert 'Eerdere goedkeuringen vervallen' in label_page.text
    assert state.snapshot_objects(sid) == before  # Viewing/selection never confirms context.
    first = client.post('/review/source-context', data=_payload(form), follow_redirects=False)
    assert first.status_code == 303
    assert target['object_id'] in first.headers['location']
    after = client.get(first.headers['location'])
    assert 'Het contextbesluit is opgeslagen' in after.text
    assert 'Koppeling aanpassen of verwijderen' in after.text
    assert 'Context toevoegen uit de bron' in after.text  # More than one context source remains possible.
    state.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=target['object_id'],
                        decision='approve', confirmed_object_type='definition', relation_review_ack=True,
                        expected_revision=state.objects_revision(sid))
    other = next(row for row in state.snapshot_objects(sid)
                 if 'bespreekt passende ondersteuning' in row.get('content', {}).get('clean_text', ''))
    pair = client.get('/review', params={'document': sid, 'object': source['object_id'], 'context_target': other['object_id']})
    data = _payload(_link_form(pair))
    assert set(data['target_object_ids']) == {target['object_id'], other['object_id']}
    assert client.post('/review/source-context', data=data, follow_redirects=False).status_code == 303
    rows = state.snapshot_objects(sid)
    for target_id in data['target_object_ids']:
        row = next(row for row in rows if row['object_id'] == target_id)
        assert links_of(row)[0]['text'] == 'DOEN'
        assert row['governance']['validation_status'] == 'needs_review'
    assert not any(binding.get('valid') for binding in state.object_review_bindings(sid)
                   if binding['object_id'] == target['object_id'])
    restarted = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / 'sources', runtime=tmp_path / 'runtime')
    assert restarted.snapshot_objects(sid) == rows


def test_separate_exclude_and_reset_commands_have_no_hidden_targets(tmp_path):
    state, _, _, source, target, command = _system(tmp_path)
    state.confirm_source_context(**command)
    client = _client(state)
    sid = command['snapshot_id']
    page = client.get('/review', params={'document': sid, 'object': source['object_id']})
    forms = Forms(page.text).forms
    commands = {field['value']: form for form in forms for field in form['inputs']
                if field.get('name') == 'role' and field.get('type') == 'hidden'}
    assert set(commands) == {'excluded', 'reset'}
    for form in commands.values():
        assert not any(field.get('name') == 'target_object_ids' for field in form['inputs'])
    assert client.post('/review/source-context', data=_payload(commands['excluded'], role='excluded'), follow_redirects=False).status_code == 303
    rows = state.snapshot_objects(sid)
    assert not links_of(next(row for row in rows if row['object_id'] == target['object_id']))
    assert role_of(next(row for row in rows if row['object_id'] == source['object_id']))['role'] == 'excluded'
    page = client.get('/review', params={'document': sid, 'object': source['object_id']})
    reset = next(form for form in Forms(page.text).forms if any(field.get('name') == 'role' and field.get('value') == 'reset' for field in form['inputs']))
    assert client.post('/review/source-context', data=_payload(reset, role='reset'), follow_redirects=False).status_code == 303
    row = next(row for row in state.snapshot_objects(sid) if row['object_id'] == source['object_id'])
    assert not role_of(row)
    assert row['governance']['validation_status'] == 'needs_review'


def test_invalid_and_stale_submission_retains_draft_without_mutation(tmp_path):
    state, _, _, source, target, command = _system(tmp_path)
    client = _client(state)
    sid = command['snapshot_id']
    page = client.get('/review', params={'document': sid, 'object': source['object_id'], 'context_target': target['object_id']})
    form = _link_form(page)
    before = deepcopy(state.snapshot_objects(sid))
    data = _payload(form, reason='Mijn gecontroleerde keuze <script>onveilig</script>')
    data['role'] = ''
    invalid = client.post('/review/source-context', data=data)
    assert invalid.status_code == 400
    assert 'Je keuzes zijn niet opgeslagen' in invalid.text
    assert '&lt;script&gt;onveilig&lt;/script&gt;' in invalid.text
    assert '<script>onveilig</script>' not in invalid.text
    assert _payload(_link_form(invalid))['target_object_ids'] == [target['object_id']]
    data.update(role='label', snapshot_revision='stale')
    stale = client.post('/review/source-context', data=data)
    assert stale.status_code == 409
    assert 'Je keuzes zijn niet opgeslagen' in stale.text
    retry = _payload(_link_form(stale))
    assert retry['snapshot_revision'] == state.objects_revision(sid)
    assert retry['target_object_ids'] == [target['object_id']]
    assert state.snapshot_objects(sid) == before


def test_context_ui_keeps_full_text_and_explicit_choices(tmp_path):
    state, _, _, source, target, command = _system(tmp_path)
    rows = deepcopy(state.snapshot_objects(command['snapshot_id']))
    source = next(row for row in rows if row['object_id'] == source['object_id'])
    target = next(row for row in rows if row['object_id'] == target['object_id'])
    target['content']['clean_text'] = 'Volledige passage. ' * 25 + 'Noodzakelijke uitzondering aan het einde.'
    source['content']['clean_text'] = 'Letterlijke context. ' * 25 + 'Laatste bronvoorwaarde.'
    # This is a presentation fixture: retain internally valid source evidence.
    # Corrupt evidence is exercised separately and must never offer a disposition.
    from src.source_accountability_v1 import KEY, record
    evidence = source["metadata"][KEY]
    spans = [{"block_id": evidence["spans"][0]["block_id"], "start": 0,
              "end": len(source["content"]["clean_text"])}]
    source["metadata"]["semantic_passage"]["spans"] = spans
    source["metadata"][KEY] = record(
        text=source["content"]["clean_text"], spans=spans,
        assessment={"role": evidence["proposed_role"], "reason": evidence["reason"]},
        version=evidence["version"],
    )
    panel = _source_context_panel(source, rows, command['snapshot_id'], command['expected_revision'],
                                  context_target=target['object_id'], source_mode=True)
    assert target['content']['clean_text'] in panel
    assert source['content']['clean_text'] in panel
    assert 'context-literal' in panel
    assert not any('checked' in field for field in Forms(panel).forms[0]['inputs'] if field.get('name') == 'role')


def test_context_navigation_cannot_bypass_authorization_or_redirect_externally(tmp_path, monkeypatch):
    state, researcher, _, source, target, command = _system(tmp_path)
    sid = command['snapshot_id']
    client = _client(state)
    before = deepcopy(state.snapshot_objects(sid))
    invalid = client.get('/review', params={'document': sid, 'object': source['object_id'], 'context_target': 'other-snapshot-object'})
    assert invalid.status_code == 400
    data = dict(snapshot_id=sid, source_object_id=source['object_id'], role='label',
                target_object_ids=[target['object_id']], reason=command['reason'], command_id='ui-access',
                snapshot_revision=command['expected_revision'], source_checked='1', return_object_id='https://example.com')
    outsider = _client(state, researcher['username'], 'anne-secret')
    assert outsider.post('/review/source-context', data=data).status_code == 403
    assert state.snapshot_objects(sid) == before
    result = client.post('/review/source-context', data=data, follow_redirects=False)
    assert result.status_code == 303
    assert result.headers['location'].startswith('/review?')
    assert 'example.com' not in result.headers['location']
    monkeypatch.setattr(state, 'snapshot_is_published', lambda sid: True)
    assert 'data-source-context-form' not in client.get('/review', params={'document': sid, 'object': source['object_id']}).text
    assert client.post('/review/source-context', data=data).status_code == 400
