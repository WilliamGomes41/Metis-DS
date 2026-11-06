"""Focused review and saved-result pages over existing authorised read inputs."""
from html import escape
from urllib.parse import urlencode

from src.review.review_cockpit_v1 import found_under_path, knowledge_review_projection


def review_page_shell(account, body, *, title='Review'):
    from src.operations_console_app import _page, _metis_mark, _session_warning
    links = ''.join(f'<a href="{url}"' + (' aria-current="page"' if label == 'Review' else '')
                    + f'>{label}</a>' for url, label in (
                        ('/ingest', 'Inleveren'), ('/source-selection', 'Vorming'),
                        ('/review', 'Review'), ('/publish', 'Publicatie'), ('/tree', 'Documenten')))
    person = escape(str(account.get('display_name') or account.get('username') or ''))
    roles = escape(' · '.join(account.get('roles') or []))
    nav = ('<header class="ko-topbar"><a class="ko-brand" href="/" aria-label="Metis, naar Mijn werk">'
           + _metis_mark() + '<span><strong>Metis</strong><small>V&amp;VN Data Services</small></span></a>'
           '<nav aria-label="Werkplekken">' + links + '</nav>'
           '<button class="theme-toggle" type="button" data-theme-toggle aria-label="Wissel tussen lichte en donkere modus">'
           '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/></svg></button>'
           '<details class="ko-account"><summary>' + person + '<small>' + roles + '</small></summary>'
           '<a href="/settings">Instellingen</a><form method="post" action="/logout"><button type="submit">Uitloggen</button></form></details></header>')
    return _page(nav + _session_warning() + '<main class="ko-page">' + body + '</main>',
                 title=title + ' · Metis', stylesheets=('ko-review.css',))


def source_breadcrumb(snapshot_id, obj, *, title=''):
    parts = [part.strip() for part in found_under_path(obj).split(' › ') if part.strip()]
    if title and (not parts or parts[0] != title):
        parts.insert(0, title)
    if not parts:
        parts = [title or 'Document']
    document = '/review?' + urlencode({'document': snapshot_id})
    source = '/review/bronpassage?' + urlencode({'document': snapshot_id, 'object': obj['object_id']})
    return '<nav class="ko-breadcrumb" aria-label="Bronpad">' + '<span aria-hidden="true">/</span>'.join(
        f'<a href="{escape(document if index == 0 else source, quote=True)}">{escape(part)}</a>'
        for index, part in enumerate(parts)) + '</nav>'


def _source_panel(console, inputs, obj, *, task=''):
    from src.review.ko_document_context_ui_v1 import read_document_context, render_document_context
    source = read_document_context(console, inputs, obj)
    panel = render_document_context(inputs.envelope['snapshot_id'], obj, inputs.objects, task=task, source=source)
    return panel


def summary_rows(obj, objects, descriptor=None, *, review_path='richtlijn'):
    from src.review.ko_receipt_ui_v1 import _scope_connections
    rows = {'Doelgroep': [], 'Voorwaarde': [], 'Uitzondering': [], 'Bij deze uitzondering': [], 'Onderbouwing': []}
    for item in _scope_connections(obj):
        if item.label in {'Doelgroep', 'Actor of doelgroep', 'Doelgroep en afbakening', 'Afbakening'}:
            rows['Doelgroep'].append((item.text, item.status, item.origin))
    for item in knowledge_review_projection(obj, objects)['essential_context']:
        label = {'condition': 'Voorwaarde', 'exception': 'Uitzondering', 'support': 'Onderbouwing',
                 'scope': 'Doelgroep', 'target_group': 'Doelgroep',
                 'exception_action': 'Bij deze uitzondering'}.get(item['role'])
        if label:
            rows[label].append((str(item.get('text') or ''),
                                '' if item.get('status') == 'bound' else 'Nog te controleren', ''))
    relations = descriptor.relations if descriptor is not None else ()
    for item in relations:
        label = {'applies_if': 'Voorwaarde', 'except_if': 'Uitzondering', 'supported_by': 'Onderbouwing'}.get(item.get('relation_type'))
        if not label:
            continue
        target = item.get('target') or {}
        rows[label].append((str(target.get('text') or item.get('text') or 'Gekoppelde tekst ontbreekt.'),
                            'Voorstel, nog niet bevestigd' if item.get('authority') == 'proposed' else '', ''))
    from src.review.review_context_v1 import review_context
    context = review_context(obj, objects=objects, review_path=review_path)
    for item in context['links']:
        if item.get('direction') == 'incoming' and item.get('relation_type') == 'explains':
            source = item['source']
            rows['Onderbouwing'].append((source.get('text') or 'Gekoppelde tekst ontbreekt.',
                'Voorstel, nog niet bevestigd' if item.get('authority') == 'proposed' else '', ''))
    return {label: list(dict.fromkeys(values)) for label, values in rows.items()}


def _summary_table(obj, objects, descriptor, review_path):
    rows = summary_rows(obj, objects, descriptor, review_path=review_path)
    missing = {'Doelgroep': 'Niet afzonderlijk vermeld.', 'Voorwaarde': 'Niet afzonderlijk vastgelegd.',
               'Uitzondering': 'Niet afzonderlijk vastgelegd.', 'Bij deze uitzondering': 'Niet afzonderlijk vastgelegd.',
               'Onderbouwing': 'Niet afzonderlijk gekoppeld.'}
    body = []
    for label, values in rows.items():
        content = ''.join('<p>' + escape(text) + (f'<small>{escape(status)}</small>' if status else '') + '</p>'
                          for text, status, _origin in values)
        body.append('<tr><th scope="row">' + label + '</th><td>'
                    + (content or '<span class="ko-muted">' + missing[label] + '</span>') + '</td></tr>')
    return '<table class="ko-meaning-table" data-essential-context><tbody>' + ''.join(body) + '</tbody></table>'


def _question(name, label, value, *, subline=''):
    options = ''.join(f'<label><input type="radio" name="{name}" value="{answer}" required'
                      + (' checked' if value == answer else '') + f'> {text}</label>'
                      for answer, text in (('yes', 'Ja'), ('adjust', 'Aanpassen')))
    return ('<fieldset class="ko-question"><legend>' + label + '</legend><div>' + options + '</div>'
            + ('<p class="ko-question-place">' + subline + '</p>' if subline else '') + '</fieldset>')


def _additional_relations(descriptor):
    from src.operations_console_app import RELATION_LABELS
    items = []
    for relation in descriptor.relations:
        kind = relation['relation_type']
        if kind in {'applies_if', 'except_if', 'supported_by'}:
            continue
        target = relation['target']
        items.append('<li><strong>' + escape(RELATION_LABELS.get(kind, kind)) + '</strong>: '
            + escape(target['text']) + ' <small>' + escape(target['origin'] + ' · versie ' + target['object_version'])
            + (' · Voorstel, nog niet bevestigd' if relation['authority'] == 'proposed' else '') + '</small></li>')
    return '<ul>' + ''.join(items) + '</ul>' if items else ''


def render_review_page(console, account, inputs, obj, *, task='', second=False, draft=None, error='', conflict=False):
    from src.operations_console_app import _object_type_label, _source_bound_fields_html, new_review_interaction_id
    from src.review.review_assessment_v1 import displayed_review_descriptor
    from src.review.knowledge_object_state_v1 import derive_ko_state
    from src.review.review_duty_v1 import reviewer_route_for
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    draft = draft or {}
    sid = inputs.envelope['snapshot_id']
    path = review_path_for_klasse(inputs.envelope['class'])
    descriptor = displayed_review_descriptor(obj, inputs.objects, path, bindings=inputs.bindings,
        fragments=inputs.fragments, stage='second_review' if second else None)
    route = reviewer_route_for(obj, review_path=path, reviewer_id=account['account_id'],
                              bindings=inputs.bindings, fragments=inputs.fragments)
    published = console.snapshot_is_published(sid)
    can_approve = bool(not published and inputs.source_available and route and route.get('actionable')
                       and descriptor.can_confirm and not conflict)
    state = derive_ko_state(obj, review_path=path, bindings=inputs.bindings, fragments=inputs.fragments)['state']
    repair = '/source-selection?' + urlencode({'document': sid, 'object': obj['object_id'], 'task': 'repair',
                                              'review_revision': inputs.revision})
    place = escape(found_under_path(obj)) + ' <span aria-hidden="true">·</span> <a href="' + escape(repair, quote=True) + '">Andere plek kiezen</a>'
    fields = {'snapshot_id': sid, 'object_id': obj['object_id'], 'snapshot_revision': inputs.revision,
              'interaction_id': new_review_interaction_id(), 'return_task': task,
              'review_ui': 'compact-v1'}
    if second:
        fields['review_stage'] = 'second_review'
    hidden = ''.join(f'<input type="hidden" name="{key}" value="{escape(str(value), quote=True)}">' for key, value in fields.items())
    semantics = ''
    if descriptor.direction or descriptor.strength_choice:
        direction = {'for': 'Aanraden', 'against': 'Afraden'}.get(descriptor.direction, 'Richting nog onbekend')
        strength = {'strong': 'Sterk', 'weak': 'Zwak', 'not_stated': 'Sterkte niet vermeld'}.get(descriptor.strength_choice, 'Sterkte nog onbekend')
        semantics = '<p class="ko-interpretation">' + escape(direction + ' · ' + strength) + '</p>'
    notice = ''
    if error:
        notice = '<p class="ko-notice" role="alert">' + escape(error) + '</p>'
        if conflict:
            reopen = '/review?' + urlencode({'document': sid, 'object': obj['object_id'], 'task': task})
            notice += '<p><a href="' + escape(reopen, quote=True) + '">Passage opnieuw beoordelen</a></p>'
    elif not can_approve:
        message = ('De passage kan nu niet worden goedgekeurd. Bekijk de bron of kies een gerichte correctie.'
                   if inputs.source_available else 'De oorspronkelijke bron kon niet worden bevestigd. Goedkeuren is geblokkeerd.')
        notice = '<p class="ko-notice" role="status">' + message + '</p>'
    heading = 'Onafhankelijke tweede review' if second else 'Review'
    rejection = ('' if second else
        '<details class="ko-reject"><summary>Afwijzen</summary><label>Toelichting bij afwijzing<textarea name="comment">'
        + escape(str(draft.get('comment') or '')) + '</textarea></label>'
        '<button class="ko-text-button" type="submit" name="review_action" value="reject" formnovalidate>Afwijzen met toelichting</button></details>')
    body = ('<header class="ko-page-heading"><h1>' + heading + '</h1>'
            + source_breadcrumb(sid, obj, title=inputs.envelope.get('title') or '')
            + '<p class="ko-progress">Te beoordelen passage <span aria-hidden="true">·</span> '
            '<strong data-ko-state>' + escape(state or 'Broncontext') + '</strong>'
            + (' <span aria-hidden="true">·</span> Onafhankelijk tweede akkoord' if second else '') + '</p></header>'
            + notice + '<div class="ko-review-layout">'
            + _source_panel(console, inputs, obj, task=task)
            + '<section class="ko-object-panel" aria-labelledby="ko-object-title"><h2 id="ko-object-title">Te beoordelen kennisobject</h2>'
            '<p class="ko-claim" data-full-knowledge-passage data-reviewed-version="' + escape(descriptor.object_version, quote=True) + '">'
            + escape(descriptor.text) + '</p><p class="ko-type">' + escape(_object_type_label(descriptor.object_type)) + '</p>'
            + semantics + _summary_table(obj, inputs.objects, descriptor, path)
            + '<details class="ko-evidence"><summary>Bekijk gekoppelde onderbouwing en bronbewijs</summary>'
            + _additional_relations(descriptor) + _source_bound_fields_html(obj) + '</details>'
            + '<form method="post" action="' + ('/review/second-review' if second else '/review')
            + '" class="ko-assessment-form" data-ko-assessment-form data-can-approve="' + str(can_approve).lower() + '">'
            + hidden
            + _question('applicable', 'Is dit toepasbaar?', draft.get('applicable'))
            + _question('complete', 'Is dit compleet?', draft.get('complete'))
            + _question('placed_correctly', 'Staat dit op de juiste plek?', draft.get('placed_correctly'), subline=place)
            + '<p class="ko-adjustment">Wil je iets aanpassen? <a href="' + escape(repair, quote=True) + '">Open de gerichte correctie</a>.</p>'
            '<div class="ko-actions"><button class="ko-primary" type="submit" name="review_action" value="approve"'
            + ('' if can_approve else ' disabled') + '>Goedkeuren en opslaan</button>'
            '<a href="' + escape(repair, quote=True) + '">Correctie nodig</a>'
            '<button class="ko-text-button" type="submit" name="review_action" value="later" formnovalidate>Later beoordelen</button></div>'
            + rejection + '</form></section></div>'
            + _assessment_script())
    return review_page_shell(account, body, title=heading)


def _assessment_script():
    return '''<script>
for (const form of document.querySelectorAll('[data-ko-assessment-form]')) {
  const approve = form.querySelector('[value="approve"]');
  const update = () => {
    const yes = ['applicable','complete','placed_correctly'].every(name => form.querySelector(`input[name="${name}"]:checked`)?.value === 'yes');
    approve.disabled = form.dataset.canApprove !== 'true' || !yes;
  };
  form.addEventListener('change', update);
  update();
}
</script>'''


def compact_review_error(console, account, snapshot_id, object_id, revision, task, draft, error, *, second=False):
    from dataclasses import replace
    from fastapi.responses import HTMLResponse
    from src.operations_console_app import ERROR_COPY, SNAPSHOT_OBJECT_WRITE_CONFLICT
    from src.review.review_passage_read_v1 import read_review_passage
    inputs = read_review_passage(console, account, snapshot_id, object_id)
    obj = next(row for row in inputs.objects if row['object_id'] == object_id)
    conflict = (getattr(error, 'code', '') == SNAPSHOT_OBJECT_WRITE_CONFLICT
                or bool(revision.strip()) and revision != inputs.revision)
    inputs = replace(inputs, revision=revision)
    messages = {
        'review_assessment_required': 'Beantwoord de drie vragen voordat je goedkeurt.',
        'review_assessment_answer_invalid': 'Kies bij iedere vraag Ja of Aanpassen.',
        'review_assessment_requires_three_yes': 'Voor goedkeuren moeten de drie antwoorden Ja zijn. Kies anders Correctie nodig.',
        'review_assessment_unresolved_proposal': 'De getoonde interpretatie kan nog niet volledig worden bevestigd. Kies Correctie nodig.',
    }
    code = SNAPSHOT_OBJECT_WRITE_CONFLICT if conflict else getattr(error, 'code', str(error))
    message = messages.get(code) or ERROR_COPY.get(code) or 'Deze beoordeling is niet opgeslagen. Controleer de passage en probeer opnieuw.'
    page = render_review_page(console, account, inputs, obj, task=task, second=second,
                              draft=draft, error=message, conflict=conflict or not revision.strip())
    return HTMLResponse(page, status_code=409 if conflict else 400, headers={'Cache-Control': 'no-store'})


def handle_compact_review(console, account, snapshot_id, object_id, revision, interaction_id, task,
                          action, values, comment='', *, second=False):
    from fastapi.responses import RedirectResponse
    from src.operations_console_v1 import ConsoleError
    from src.review.review_assessment_v1 import ReviewAssessment, displayed_review_descriptor, compact_approval_arguments
    from src.review.review_passage_read_v1 import read_review_passage, resolve_review_revision
    from src.review.review_interaction_v1 import build_review_interaction_evidence
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    from src.review.ko_receipt_ui_v1 import receipt_location
    draft = {**values, 'comment': comment}
    try:
        if not revision.strip():
            raise ConsoleError('snapshot_revision_required')
        if not interaction_id.strip():
            raise ConsoleError('review_assessment_required')
        try:
            assessment = ReviewAssessment.from_values(**values)
        except ValueError as exc:
            raise ConsoleError(str(exc)) from exc
        if action not in {'approve', 'reject', 'later'}:
            raise ConsoleError('invalid_review_decision')
        if second and action == 'reject':
            raise ConsoleError('invalid_review_decision')
        if action == 'approve' and not assessment.all_yes:
            raise ConsoleError('review_assessment_requires_three_yes')
        if action == 'reject' and not comment.strip():
            raise ConsoleError('review_comment_required')
        if action == 'later':
            if not second:
                console.review_object(actor_id=account['account_id'], snapshot_id=snapshot_id,
                    object_id=object_id, decision='later', suitability='ja', eindoordeel='later_beoordelen',
                    expected_revision=revision, **({'_compact_result': True} if getattr(console, '_metis_workflow_review_authority', False) else {}))
            return RedirectResponse('/review?' + urlencode({'document': snapshot_id, 'after': object_id, 'task': task}), status_code=303)
        bounded = getattr(console, '_metis_workflow_review_authority', False)
        if second or not bounded:
            inputs = read_review_passage(console, account, snapshot_id, object_id)
            obj = next(row for row in inputs.objects if row['object_id'] == object_id)
            path = review_path_for_klasse(inputs.envelope['class'])
            descriptor = displayed_review_descriptor(obj, inputs.objects, path, bindings=inputs.bindings,
                fragments=inputs.fragments, stage='second_review' if second else None)
            if action == 'approve' and not descriptor.can_confirm:
                raise ConsoleError('review_assessment_unresolved_proposal')
            evidence = build_review_interaction_evidence(interaction_id=interaction_id,
                interaction_kind='second_review' if second else 'contextual',
                reviewer_account_id=account['account_id'], snapshot_id=snapshot_id,
                review_stage='second_review' if second else 'first_review', focal=obj,
                objects=inputs.objects, review_path=path, assessment=assessment)
            if second:
                expected = resolve_review_revision(console, snapshot_id, revision)
                console.approve_second_review(actor_id=account['account_id'], snapshot_id=snapshot_id,
                    object_id=object_id, expected_revision=expected, interaction_evidence=evidence)
            else:
                kwargs = compact_approval_arguments(assessment, descriptor) if action == 'approve' else {
                    'suitability': 'geen_kenniseenheid', 'eindoordeel': 'afwijzen'}
                console.review_object(actor_id=account['account_id'], snapshot_id=snapshot_id,
                    object_id=object_id, decision=action, comment=comment,
                    expected_revision=resolve_review_revision(console, snapshot_id, revision),
                    interaction_evidence=evidence, **kwargs)
        else:
            console.review_object(actor_id=account['account_id'], snapshot_id=snapshot_id,
                object_id=object_id, decision=action, comment=comment,
                suitability='ja' if action == 'approve' else 'geen_kenniseenheid',
                eindoordeel='goedkeuren' if action == 'approve' else 'afwijzen',
                expected_revision=revision, _compact_result=True, _interaction_id=interaction_id,
                _review_assessment=assessment)
    except ConsoleError as error:
        return compact_review_error(console, account, snapshot_id, object_id, revision, task, draft, error, second=second)
    location = '/review?' + urlencode({'document': snapshot_id, 'after': object_id, 'task': task})
    return RedirectResponse(receipt_location(location, interaction_id, object_id), status_code=303)
