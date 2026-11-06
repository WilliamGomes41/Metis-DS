"""Document context from the captured passage and explicit immutable-source reads."""
from html import escape
from urllib.parse import urlencode

from src.review.review_cockpit_v1 import broncontext_parts, found_under_path
from src.vorming.heading_parent_list_v1 import heading_visible_text


def _fragment_rows(source):
    return list(source.fragments if hasattr(source, 'fragments') else source or [])


def read_document_context(console, read_inputs, obj):
    if read_inputs is None or not read_inputs.source_available:
        return None
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    try:
        return FormationTaskStore(console.workflow_document_store).read_review_document_context(
            read_inputs.envelope, obj, source=read_inputs.fragments)
    except WorkflowDocumentStoreError:
        return None


def render_document_context(snapshot_id, obj, objects, *, task='', source=None):
    parts = broncontext_parts(obj)
    heading_items = []
    current_path = tuple((obj.get('structure') or {}).get('section_path') or [])
    original = source is not None
    neighbors = []
    if original:
        from src.object_taxonomy_v1 import extract_object_type
        rows = source.fragments
        for row in rows:
            if extract_object_type(row)[0] == 'heading':
                path = tuple(row.get('section_path') or [])
                active = path == current_path
                text = str(row.get('clean_text') or row.get('raw_text') or '')
                heading_items.append(f'<li class="ko-outline-depth-{min(len(path), 5)}"'
                    + (' aria-current="location"' if active else '') + f'>{escape(text)}'
                    + (' · bronsectie van de passage' if active else '') + '</li>')
        matches = [i for i, row in enumerate(rows) if row['fragment_id'] in source.focal_fragment_ids]
        if matches:
            source_paths = {tuple(rows[index].get('section_path') or []) for index in matches}
            if len(source_paths) == 1:
                source_path = next(iter(source_paths))
                neighbors = [str(row.get('clean_text') or row.get('raw_text') or '') for row in rows
                    if row['fragment_id'] not in source.focal_fragment_ids
                    and tuple(row.get('section_path') or []) == source_path
                    and extract_object_type(row)[0] != 'heading'][:2]
            first, last = min(matches), max(matches)
            parts = {**parts,
                'previous_paragraph': str(rows[first-1].get('clean_text') or rows[first-1].get('raw_text') or '')
                    if first > 0 and extract_object_type(rows[first-1])[0] != 'heading' else '',
                'next_paragraph': str(rows[last+1].get('clean_text') or rows[last+1].get('raw_text') or '')
                    if last+1 < len(rows) and extract_object_type(rows[last+1])[0] != 'heading' else ''}
    else:
        current = str(obj.get('parent_object_id') or '')
        for heading in objects:
            if (heading.get('confirmed_object_type') or heading.get('object_type')) != 'heading':
                continue
            active = heading.get('object_id') == current
            depth = len((heading.get('structure') or {}).get('section_path') or [])
            heading_items.append(f'<li class="ko-outline-depth-{min(depth, 5)}"'
                + (' aria-current="location"' if active else '')
                + f'>{escape(heading_visible_text(heading))}' + (' · huidige plek' if active else '') + '</li>')
    section_url = '/review/context-section?' + urlencode(dict(document=snapshot_id, object=obj['object_id'], task=task))
    original_url = '/review/bronpassage?' + urlencode(dict(document=snapshot_id, object=obj['object_id'], task=task))
    before = str(parts.get('previous_paragraph') or '')
    after = str(parts.get('next_paragraph') or '')
    selected = str(parts.get('source_text_exact') or '')
    from src.operations_console_app import _semantic_selection_markup
    selected_markup, _ = _semantic_selection_markup(selected,
        str(parts.get('semantic_selection_text') or selected))
    paragraphs = ((f'<p class="meta">Voorafgaande bronpassage</p><p>{escape(before)}</p>' if before else '<p class="field-help">Geen voorafgaande alinea in het vastgelegde passagevenster.</p>')
        + f'<p class="meta">Geselecteerde passage</p><p>{selected_markup}</p>'
        + (f'<p class="meta">Volgende bronpassage</p><p>{escape(after)}</p>' if after else '<p class="field-help">Geen volgende alinea in het vastgelegde passagevenster.</p>'))
    outline_attribute = 'data-original-outline' if original else 'data-current-outline'
    heading_note = ('Koppen uit de vastgelegde oorspronkelijke bron.' if original else
        'De oorspronkelijke bronstructuur en buuralinea’s konden niet worden bevestigd. Hier staan de koppen van het huidige kennisvoorstel; open de volledige bron voor de oorspronkelijke structuur.')
    neighbor_list = ('<ul>' + ''.join('<li>' + escape(text) + '</li>' for text in neighbors) + '</ul>'
        if neighbors else '<p class="field-help">Geen naburige passage onder dezelfde bronkop in dit vastgelegde venster. Open de hele sectie voor meer context.</p>')
    return ('<details class="ko-document-context" data-document-context open><summary><span role="heading" aria-level="2">Bekijk in documentcontext</span></summary>'
        '<div class="ko-source-layout"><section><h3>Plek in het document</h3><p class="field-help">'
        + heading_note + '</p>'
        + (f'<ul class="ko-outline" {outline_attribute}>' + ''.join(heading_items) + '</ul>' if heading_items else '<p>Geen koppen vastgelegd.</p>')
        + f'<p><strong>Vindplaats</strong> {escape(found_under_path(obj))}</p></section>'
        '<section><h3>Bronpassage en omliggende tekst</h3>' + paragraphs
        + '<div class="ko-source-neighbors" data-source-neighbors><h3>Naburige passages onder deze kop</h3>'
        + neighbor_list + '</div></section></div>'
        + f'<p><a class="btn-secondary" href="{escape(section_url, quote=True)}">Toon hele sectie en naburige passages</a></p>'
          f'<p><a href="{escape(original_url, quote=True)}">Open volledige bron</a></p></details>')



def render_source_section(console, account, snapshot_id, object_id, *, task=''):
    from src.review.review_passage_read_v1 import read_review_passage
    from src.operations_console_app import _page, _nav
    inputs = read_review_passage(console, account, snapshot_id, object_id)
    obj = next(row for row in inputs.objects if row['object_id'] == object_id)
    source = console.review_source_fragments(snapshot_id, envelope=inputs.envelope)
    rows = _fragment_rows(source)
    path = tuple((obj.get('structure') or {}).get('section_path') or [])
    if not path:
        path = tuple(broncontext_parts(obj)['ancestor_headings'])
    section = [row for row in rows if tuple(row.get('section_path') or []) == path]
    selected = broncontext_parts(obj)['source_text_exact']
    content = []
    for row in section:
        text = str(row.get('clean_text') or row.get('raw_text') or '')
        if not text:
            continue
        marked = text == selected or (selected and selected in text)
        content.append('<li>' + (f'<mark>{escape(text)}</mark>' if marked else escape(text)) + '</li>')
    if not rows or not section or getattr(getattr(source, 'root', source), 'complete', True) is False:
        body = '<p class="banner warn">De volledige sectie kon niet worden bevestigd. Open de volledige oorspronkelijke bron.</p>'
    else:
        body = '<ol class="ko-source-section" data-full-section>' + ''.join(content) + '</ol>'
    original = '/review/bronpassage?' + urlencode(dict(document=snapshot_id, object=object_id, task=task))
    back = '/review?' + urlencode(dict(document=snapshot_id, object=object_id, task=task))
    return _page(_nav(account, 'review') + '<section class="room"><h1>Hele sectie en naburige bronpassages</h1>'
        '<p>Tekst in bronvolgorde uit dezelfde vastgelegde bron. Dit wijzigt geen beoordeling.</p>'
        + body + f'<p><a href="{escape(original, quote=True)}">Open volledige bron</a></p>'
        f'<p><a class="btn-secondary" href="{escape(back, quote=True)}">Terug naar review</a></p></section>', title='Documentcontext')
