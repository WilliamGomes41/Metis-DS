"""Untrusted draft text stays inert in the compact conflict response."""
from html.parser import HTMLParser
from types import SimpleNamespace

from src.operations_console_v1 import SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.review.review_command_response_v1 import review_command_error


class ParsedHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def test_conflict_draft_cannot_break_out_of_attributes_or_textareas():
    payload = '</textarea><img src=x onerror="alert(1)"> & \'"'
    key = 'custom" autofocus onfocus="alert(2)'
    response = review_command_error(None, None, payload, payload, '', payload,
        {'comment': payload, 'proposed_correction': payload, key: payload,
         'relation_choice': [payload]}, SimpleNamespace(code=SNAPSHOT_OBJECT_WRITE_CONFLICT))
    assert response.status_code == 409
    parsed = ParsedHTML()
    parsed.feed(response.body.decode())
    assert not any(attrs.get('src') == 'x' or any(k.startswith('on') or k == 'autofocus' for k in attrs)
                   for tag, attrs in parsed.elements)
    hidden = {attrs['name']: attrs.get('value') for tag, attrs in parsed.elements
              if tag == 'input' and attrs.get('type') == 'hidden'}
    assert hidden[key] == payload
    assert hidden['relation_choice'] == payload
    assert 'snapshot_revision' not in hidden
    assert parsed.text.count(payload) == 2
