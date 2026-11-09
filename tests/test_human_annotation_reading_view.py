"""The annotation reader presents one document while retaining exact anchors."""
from html.parser import HTMLParser

from src.vorming.human_annotation_ui_v1 import source_document_html


class Reader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.spans = {}
        self.current = None
        self.pages = []
        self.details = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'span' and attrs.get('data-source-block'):
            self.current = attrs['data-source-block']
            self.spans[self.current] = ''
        if tag == 'section' and 'annotation-page' in attrs.get('class', '').split():
            self.pages.append(attrs['aria-label'])
        if tag == 'details':
            self.details += 1

    def handle_endtag(self, tag):
        if tag == 'span':
            self.current = None

    def handle_data(self, data):
        if self.current:
            self.spans[self.current] += data


def block(number, page, text, *, path=None, heading=None):
    return {'block_id': f'block-{number}', 'position': number - 1, 'text': text,
            'section_path': path or [], 'heading': heading,
            'locations': [{'page': page, 'locator': None}]}


def test_reader_keeps_every_exact_block_and_folds_contents_without_repeated_controls():
    blocks = [block(1, 1, 'Conceptrichtlijn Smetten', heading='Conceptrichtlijn Smetten', path=['Conceptrichtlijn Smetten']),
              block(2, 3, 'Inhoudsopgave', heading='Inhoudsopgave', path=['Inhoudsopgave']),
              block(3, 4, 'Aanbevelingen ................................', path=['Inhoudsopgave']),
              block(4, 4, '25', path=['Inhoudsopgave']),
              block(5, 40, 'De behandeling volgt uit de beoordeling.', path=['Behandeling']),
              block(6, 40, '40', path=['Behandeling']),
              block(7, 41, 'Aanbevelingen', heading='Aanbevelingen', path=['Behandeling', 'Aanbevelingen']),
              block(8, 41, '· Houd de huid droog', path=['Behandeling', 'Aanbevelingen'])]
    html = source_document_html(blocks)
    reader = Reader()
    reader.feed(html)
    assert reader.spans == {b['block_id']: b['text'] for b in blocks}
    assert reader.pages == ['Pagina 1', 'Pagina 3', 'Pagina 4', 'Pagina 40', 'Pagina 41']
    assert reader.details == 1
    assert '<p class="annotation-toc-row"><span' in html
    assert 'class="annotation-page-number"' in html
    assert 'class="annotation-list-item"' in html
    assert 'Dit hele tekstblok aanwijzen' not in html


def test_reader_escapes_source_text_without_changing_the_visible_selection():
    original = 'Gebruik <script> & controleer "tekst".'
    html = source_document_html([block(1, None, original)])
    reader = Reader()
    reader.feed(html)
    assert reader.spans['block-1'] == original
    assert '<script>' not in html
