"""Focused review and saved-result pages over existing authorised read inputs."""
from html import escape
from urllib.parse import quote, urlencode

from src.review.review_cockpit_v1 import found_under_path, knowledge_review_projection


def review_page_shell(account, body, *, title='Review'):
    from src.operations_console_app import _nav, _page
    return _page(
        _nav(account, 'review', include_care=False)
        + '<main class="ko-page" id="hoofdinhoud" tabindex="-1">' + body + '</main>',
        title=title + ' · Metis', stylesheets=('ko-review.css',), main_id='hoofdinhoud',
    )


def source_breadcrumb(snapshot_id, obj, *, title='', task='', overview_url=''):
    parts = [part.strip() for part in found_under_path(obj).split(' › ') if part.strip()]
    if title and (not parts or parts[0] != title):
        parts.insert(0, title)
    if not parts:
        parts = [title or 'Document']
    document = overview_url or '/review?' + urlencode({'document': snapshot_id, **({'task': task} if task else {})})
    source = '/review/bronpassage?' + urlencode({'document': snapshot_id, 'object': obj['object_id']})
    return '<nav class="ko-breadcrumb" aria-label="Bronpad">' + '<span aria-hidden="true">/</span>'.join(
        f'<a href="{escape(document if index == 0 else source, quote=True)}">{escape(part)}</a>'
        for index, part in enumerate(parts)) + '</nav>'


def _source_panel(console, inputs, obj, *, task=''):
    from src.review.ko_document_context_ui_v1 import read_document_context, render_document_context
    source = read_document_context(console, inputs, obj)
    assessment_path = '/source-selection' if inputs.envelope['class'] == 'beslisboom' else '/inzicht/document'
    assessment_url = (assessment_path + '?' + urlencode({'document': inputs.envelope['snapshot_id']})
        if inputs.envelope.get('_review_check_formation') else '')
    panel = render_document_context(inputs.envelope['snapshot_id'], obj, inputs.objects,
        task=task, source=source, document_assessment_url=assessment_url)
    return panel


def summary_rows(obj, objects, descriptor=None, *, review_path='richtlijn'):
    from src.review.ko_receipt_ui_v1 import _review_application
    rows = {'Doelgroep': [], 'Voorwaarde': [], 'Uitzondering': [], 'Bij deze uitzondering': [], 'Onderbouwing': []}
    human = (obj.get('metadata') or {}).get('human_annotation')
    application, scopes, essential = _review_application(obj, knowledge_review_projection(obj, objects)['essential_context'])
    if human:
        rows = {'Doelgroep': [], 'Situatie': [], **rows}
    for item in application:
        rows[item.label].append((item.text, item.status, item.origin))
    for item in scopes:
        if item.label in {'Doelgroep', 'Doelgroep en afbakening'} or (not human and item.label in {'Actor of doelgroep', 'Afbakening'}):
            rows['Doelgroep'].append((item.text, item.status, item.origin))
    for item in essential:
        label = {'condition': 'Voorwaarde', 'exception': 'Uitzondering', 'support': 'Onderbouwing',
                 'scope': 'Doelgroep', 'target_group': 'Doelgroep',
                 'exception_action': 'Bij deze uitzondering'}.get(item['role'])
        if label:
            rows[label].append((str(item.get('text') or ''),
                                '' if item.get('status') == 'bound' else 'Nog te controleren', ''))
    if human:
        for entry in ((obj.get('metadata') or {}).get('source_bound_context') or {}).get('entries', []):
            label = {'exception':'Uitzondering',
                'evidence':'Onderbouwing', 'explanation':'Toelichting', 'context':'Aanvullende context',
                'actor':'Uitvoerder', 'timing':'Tijdstip',
                'list_introduction':'Bronstructuur', 'row_header':'Bronstructuur', 'column_header':'Bronstructuur'}.get(entry.get('annotation_role'))
            text = str(entry.get('text') or '')
            if label and text and not any(value[0] == text for value in rows.get(label, [])):
                function = {'supported_by':'Onderbouwt de uitspraak', 'explains':'Verklaart de uitspraak'}.get(entry.get('evidence_function'), '')
                rows.setdefault(label, []).append((text, function, 'aangewezen bronpassage'))
    relations = descriptor.relations if descriptor is not None else ()
    for item in relations:
        label = {'applies_if': 'Voorwaarde', 'except_if': 'Uitzondering', 'supported_by': 'Onderbouwing', 'explains': 'Onderbouwing'}.get(item.get('relation_type'))
        if not label:
            continue
        target = item.get('target') or {}
        rows[label].append((str(target.get('text') or item.get('text') or 'Gekoppelde tekst ontbreekt.'),
                            'Voorstel, nog niet bevestigd' if item.get('authority') == 'proposed' else '', ''))
    return {label: list(dict.fromkeys(values)) for label, values in rows.items()}


def _summary_table(rows):
    missing = {'Doelgroep': 'Niet afzonderlijk vermeld.', 'Situatie': 'Niet afzonderlijk vastgelegd.', 'Voorwaarde': 'Niet afzonderlijk vastgelegd.',
               'Uitzondering': 'Niet afzonderlijk vastgelegd.', 'Bij deze uitzondering': 'Niet afzonderlijk vastgelegd.',
               'Onderbouwing': 'Niet afzonderlijk gekoppeld.'}
    body = []
    for label, values in rows.items():
        if label == 'Doelgroep' and 'Situatie' in rows:
            body.append('<tr><th colspan="2">Toepassing</th></tr>')
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


def _completeness_signals(obj):
    """#1060: what Metis could not establish, as text under the completeness question.

    Signals come from the admission owner's record of this exact object version.
    They inform the reviewer's own judgement and add no question, section or gate.
    """
    from src.vorming.admission_gate_v1 import admission_of
    # #1067: an open direction/strength proposal is answered by the choice in the type line, not here.
    codes = set(admission_of(obj).get('signals') or []) - {'recommendation_semantics_open'}
    if not codes:
        return ''
    linked = any(entry.get('annotation_role') != 'evidence' and entry.get('text')
                 for entry in ((obj.get('metadata') or {}).get('source_bound_context') or {}).get('entries', []))
    lines = []
    if codes & {'incomplete_sentence', 'recommendation_core_incomplete'}:
        lines.append('De uitspraak lijkt een afgebroken zin.')
    if codes & {'supported_object_missing', 'condition_target_missing', 'exception_target_missing',
                'annotation_relation_target_missing', 'no_independent_claim'}:
        lines.append('De uitspraak leunt mogelijk op andere tekst. ' + (
            'Controleer of de gekoppelde tekst volstaat.' if linked else 'Er is geen tekst bij gekoppeld.'))
    if codes & {'subject_missing', 'recommendation_subject_missing'}:
        lines.append('Niet vastgesteld over wie of wat de uitspraak gaat.')
    if 'predicate_missing' in codes:
        lines.append('Niet vastgesteld wat erover gezegd wordt.')
    if codes & {'recommendation_recommended_action_missing', 'recommendation_action_object_or_goal_missing'}:
        lines.append('De aanbevolen handeling of het doel ervan is niet vastgesteld.')
    if not lines:
        # Every recorded signal is represented; a code without its own sentence still warns.
        lines.append('Een onderdeel dat bij dit type uitspraak hoort is niet vastgesteld.')
    return '<span data-ko-signals>Let op: ' + escape(' '.join(lines)) + '</span>' if lines else ''


def _additional_relations(descriptor):
    from src.operations_console_app import RELATION_LABELS
    items = []
    for relation in descriptor.relations:
        kind = relation['relation_type']
        if kind in {'applies_if', 'except_if', 'supported_by', 'explains'}:
            continue
        target = relation['target']
        items.append('<li><strong>' + escape(RELATION_LABELS.get(kind, kind)) + '</strong>: '
            + escape(target['text']) + ' <small>' + escape(target['origin'] + ' · versie ' + target['object_version'])
            + (' · Voorstel, nog niet bevestigd' if relation['authority'] == 'proposed' else '') + '</small></li>')
    return '<ul>' + ''.join(items) + '</ul>' if items else ''


def _context_evidence(obj, objects, shown):
    from src.review.source_context_review_v1 import projection
    context = projection(obj, objects)
    by_id = {row['object_id']: row for row in objects}
    rows = []
    if context['issues']:
        rows.append('<p class="ko-notice" role="alert">Een koppeling verwijst naar gewijzigde of ontbrekende tekst. '
                    'Controleer de koppeling opnieuw; deze telt nu niet als geldig contextbewijs.</p>')
    if context['links']:
        rows.append('<section data-confirmed-source-context><h3>Context die bij deze passage is vastgelegd</h3>')
        for link in context['links']:
            text = str(link.get('text') or '')
            label = 'Bronlabel' if link.get('role') == 'label' else 'Contextfragment'
            rows.append('<p><strong>' + label + '</strong> · versie '
                + escape(str(link.get('source_object_version') or '')) + '</p>')
            if text not in shown:
                rows.append('<p class="context-literal">' + escape(text) + '</p>')
            rows.append('<p>' + escape(str(link.get('reason') or '')) + '</p>')
            if link.get('source_object_id') not in by_id:
                rows.append('<p>De contextbron ontbreekt. Laat de beheerder de bronverwijzing controleren.</p>')
        rows.append('</section>')
    unseen = any(str(link.get('text') or '') not in shown for link in context['links'])
    return ''.join(rows), bool(unseen or context['issues'])


def _rejection_event(console, obj):
    """The ledger event that rejected this exact version, if any."""
    if (obj.get('governance') or {}).get('validation_status') != 'rejected':
        return None
    from src.review.review_ledger import read_events
    version = str(obj.get('object_version') or '')
    return next((row for row in reversed(read_events(console._ledger_path))
                 if row.get('object_id') == obj.get('object_id') and str(row.get('object_version') or '') == version
                 and str(row.get('event_type') or '').endswith('_review_reject')), None)


def _rejected_in_second_review(console, obj):
    """#1067: the route keeps the milestone where the rejection was recorded."""
    return ((_rejection_event(console, obj) or {}).get('event_type')) == 'second_review_reject'


def _rejection_notice(console, obj):
    """#1064: who rejected this exact version, at which review, and why. Read from the review ledger."""
    event = _rejection_event(console, obj)
    if event is None:
        return '<p class="ko-notice" role="status" data-ko-rejected>Deze versie is afgewezen.</p>'
    stage = 'in de tweede review ' if event['event_type'] == 'second_review_reject' else ''
    comment = str((event.get('details') or {}).get('comment') or '').strip()
    return ('<p class="ko-notice" role="status" data-ko-rejected>Afgewezen ' + escape(stage) + 'door '
            + escape(str(event.get('actor') or 'een reviewer')) + (': ' + escape(comment) if comment else '.') + '</p>')


def render_review_page(console, account, inputs, obj, *, task='', draft=None, error='', conflict=False,
                       origin_revision='', overview_url=''):
    from src.operations_console_app import _object_type_label, _source_bound_fields_html, new_review_interaction_id
    from src.review.review_assessment_v1 import displayed_review_descriptor
    from src.review.knowledge_object_state_v1 import derive_ko_state
    from src.review.review_duty_v1 import reviewer_route_for, exact_current_approver_ids
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    draft = draft or {}
    origin_changed = bool(origin_revision and origin_revision != inputs.revision)
    if origin_changed:
        draft = {key: value for key, value in draft.items() if key not in {'applicable', 'complete', 'placed_correctly', 'evidence_not_applicable'}}
    sid = inputs.envelope['snapshot_id']
    path = review_path_for_klasse(inputs.envelope['class'])
    route = reviewer_route_for(obj, review_path=path, reviewer_id=account['account_id'],
                              bindings=inputs.bindings, fragments=inputs.fragments)
    annotation = (obj.get('metadata') or {}).get('human_annotation')
    from src.vorming.human_annotation_projection_v1 import has_literal_support
    literal_support = has_literal_support(obj, inputs.fragments)
    reading = task == 'inventory' or bool(annotation and
        account['account_id'] in exact_current_approver_ids(obj, inputs.bindings))
    canonical_task = str((route or {}).get('canonical_task') or '')
    second = canonical_task == 'second_review'
    if not reading and (second or task == 'second_review'):
        task = canonical_task
    published = console.snapshot_is_published(sid)
    descriptor = displayed_review_descriptor(obj, inputs.objects, path, bindings=inputs.bindings,
        fragments=inputs.fragments, stage='second_review' if second else None,
        confirmed_only=reading or published)
    # #1064 and #1169: a saved correction needs a successful build before this version can be approved.
    rebuilding = None
    if annotation and not published:
        from src.vorming.human_annotation_build_v1 import correction_state
        rebuilding = correction_state(console, sid, obj['object_id'])
    can_approve = bool(not published and inputs.source_available and route and route.get('actionable')
                       and descriptor.can_confirm and not conflict and not rebuilding)
    lineage = (obj.get('metadata') or {}).get('revision_lineage') or {}
    history = (' <span aria-hidden="true">·</span> <span data-ko-rebuilt>opnieuw gebouwd na correctie van versie '
               + escape(str(lineage['previous_object_version'])) + '</span>') if annotation and lineage.get('previous_object_version') else ''
    correction_link = ''
    if annotation:
        repair = '/annotations?' + urlencode({'document': sid, 'annotation': annotation['annotation_id']})
        repair += '#annotation-controls'
        correction_link = '<a href="' + escape(repair, quote=True) + '">Aanpassen in de kaart</a>'
    elif path == 'boom' and 'decision_graph' in inputs.envelope:
        graph = '/review/decision-graph?' + urlencode({'document': sid}) + '#passage-' + quote(obj['object_id'], safe='')
        correction_link = '<a href="' + escape(graph, quote=True) + '">Passagetype in de beslisboomreview bekijken</a>'
    parent = next((row for row in inputs.objects if row['object_id'] == descriptor.parent_id), None)
    if parent is not None:
        from src.vorming.heading_parent_list_v1 import heading_visible_text
        placement = '<span data-current-parent="' + escape(descriptor.parent_id, quote=True) + '">Actuele kop: <strong>' + escape(heading_visible_text(parent)) + '</strong></span>'
    else:
        placement = 'Geen bovenliggende kop vastgelegd.' if not descriptor.parent_id else 'De actuele kop kon niet worden bevestigd.'
    fields = {'snapshot_id': sid, 'object_id': obj['object_id'], 'snapshot_revision': inputs.revision,
              'interaction_id': new_review_interaction_id(), 'return_task': task,
              'review_ui': 'compact-v1'}
    if second:
        fields['review_stage'] = 'second_review'
    hidden = ''.join(f'<input type="hidden" name="{key}" value="{escape(str(value), quote=True)}">' for key, value in fields.items())
    semantics = ''
    choose_semantics = descriptor.optional_recommendation_review and not (reading or second or published)
    direction_labels = {'for': 'Aanraden', 'against': 'Afraden'}
    strength_labels = {'strong': 'Sterk', 'weak': 'Zwak', 'not_stated': 'Sterkte niet vermeld'}
    pair = ' · '.join(label for label in (
        direction_labels.get(descriptor.direction), strength_labels.get(descriptor.strength_choice)) if label)
    if choose_semantics:
        from src.vorming.recommendation_semantics_v1 import annotation_strength_label_text
        label_evidence = annotation_strength_label_text(obj)
        picked_action = draft.get('recommendation_review_action') or 'skip'
        token = descriptor.recommendation_proposal_token

        def options(choices, picked):
            return ''.join('<option value="' + value + '"' + (' selected' if value == picked else '')
                           + '>' + escape(label) + '</option>' for value, label in choices)

        actions = [('skip', 'Overslaan')]
        if token:
            actions.append(('accept', 'Voorstel accepteren'))
        actions.append(('decline', 'Voorstel weigeren' if token else 'Zelf richting en sterkte kiezen'))
        semantics = ('<fieldset class="ko-semantics-choice" data-ko-semantics-choice>'
            '<legend>Richting en sterkte (optioneel)</legend>'
            '<p class="ko-interpretation">' + (escape('Voorstel van Metis: ' + pair)
                if token else 'Geen volledig voorstel voor richting en sterkte.') + '</p>'
            + ('<p class="ko-interpretation" data-ko-strength-label>Sterktelabel uit de bron: '
               + escape(label_evidence) + '</p>' if label_evidence else '')
            + '<input type="hidden" name="recommendation_proposal_token" value="' + escape(token, quote=True) + '">'
            '<label>Keuze <select name="recommendation_review_action">'
            + options(actions, picked_action) + '</select></label>'
            '<div data-ko-review-own>'
            '<p class="ko-interpretation">Vul beide velden in om zelf een keuze te bevestigen.</p>'
            '<label>Richting <select name="recommendation_direction">'
            + options([('', 'Kiezen'), *direction_labels.items()], draft.get('recommendation_direction')) + '</select></label>'
            '<label>Sterkte <select name="recommendation_strength_level">'
            + options([('', 'Kiezen'), ('strong', 'Sterk'), ('weak', 'Zwak'), ('not_stated', 'Niet vermeld')],
                      draft.get('recommendation_strength_level')) + '</select></label></div></fieldset>')
    elif pair:
        semantics = '<p class="ko-interpretation">' + escape(pair) + '</p>'
    elif descriptor.optional_recommendation_review:
        semantics = '<p class="ko-interpretation">Richting en sterkte onbevestigd.</p>'
    if descriptor.legacy_recommendation_strength:
        from src.object_taxonomy_v1 import recommendation_strength_sentence
        semantics = '<p class="ko-interpretation">' + escape(recommendation_strength_sentence(
            descriptor.legacy_recommendation_strength)) + '</p>'
    if descriptor.object_type == 'outcome':
        from src.object_taxonomy_v1 import recommendation_strength_sentence
        meaning = recommendation_strength_sentence(descriptor.outcome_strength)
        if descriptor.outcome_no_action:
            meaning = 'Bronuitkomst: geen actie nodig. ' + meaning
        if meaning:
            semantics = '<p class="ko-interpretation">' + escape(meaning) + '</p>'
    notice = ''
    if error:
        notice = '<p class="ko-notice" role="alert">' + escape(error) + '</p>'
        if conflict:
            reopen = '/review?' + urlencode({'document': sid, 'object': obj['object_id'], 'task': task})
            notice += '<p><a href="' + escape(reopen, quote=True) + '">Passage opnieuw beoordelen</a></p>'
    elif (obj.get('governance') or {}).get('validation_status') == 'rejected':
        notice = _rejection_notice(console, obj)
    elif rebuilding:
        notice = ('<p class="ko-notice" role="status" data-ko-rebuilding="' + rebuilding + '">'
                  + ('De nieuwe versie wordt opgebouwd. Deze pagina ververst vanzelf.' if rebuilding == 'building' else
                     'De correctie is opgeslagen. Goedkeuren kan zodra de bouw is geslaagd.')
                  + '</p>' + ('<script>setTimeout(()=>location.reload(),4000)</script>' if rebuilding == 'building' else ''))
    elif not can_approve:
        message = ('De passage kan nu niet worden goedgekeurd. Bekijk de oorspronkelijke bron.'
                   if inputs.source_available else 'De oorspronkelijke bron kon niet worden bevestigd. Goedkeuren is geblokkeerd.')
        notice = '<p class="ko-notice" role="status">' + message + '</p>'
    if origin_changed:
        notice += '<p class="ko-notice" data-review-return-changed role="status">De revisie is gewijzigd sinds je naar Vorming ging. Controleer het huidige voorstel en beoordeel deze versie opnieuw.</p>'
    from src.review.four_eyes_v1 import requires_four_eyes
    from src.review.knowledge_route_v1 import review_route
    required_second = requires_four_eyes(obj, confirmed_type=descriptor.object_type)
    # The route also shows a second review the intake configuration requires; the publication gate applies it.
    from src.review.four_eyes_v1 import second_approval_required
    route_second = required_second or second_approval_required(inputs.envelope)
    # The second approval of a four-eyes review is still missing for this exact version.
    second_pending = route_second and len(exact_current_approver_ids(obj, inputs.bindings)) < 2
    rows = summary_rows(obj, inputs.objects, descriptor, review_path=path)
    shown = {text for values in rows.values() for text, _status, _origin in values}
    context_html, context_open = _context_evidence(obj, inputs.objects, shown)
    if reading:
        from src.review.ko_transitions_v1 import recorded_not_applicable
        from src.review.knowledge_object_state_v1 import object_release_status
        from src.integrity_kernel import compute_canonical_object_hash
        identity = (str(obj['object_id']), str(obj['object_version']), compute_canonical_object_hash(obj))
        membership = console.canonical_publication_store.object_publication_membership(sid, [identity])
        state = derive_ko_state(obj, review_path=path, bindings=inputs.bindings, fragments=inputs.fragments,
                               release_status=object_release_status(obj, membership.get(identity, {})))['state']
        evidence_note = ('<p data-recorded-evidence-applicability="not_applicable">'
            'Bij de beoordeling van deze versie is onderbouwing expliciet niet van toepassing verklaard.</p>'
            if recorded_not_applicable(obj, inputs.bindings) else '')
        inventory = '/review?' + urlencode({'document': sid, 'task': 'inventory'})
        review = '/review?' + urlencode({'document': sid, 'object': obj['object_id']})
        body = ('<div data-ko-object-view><header class="ko-page-heading"><h1>Kennisobject</h1>'
            + source_breadcrumb(sid, obj, title=inputs.envelope.get('title') or '', task='inventory')
            + '<p class="ko-progress">Huidige versie ' + escape(descriptor.object_version) + history
            + ' <span aria-hidden="true">·</span> <strong data-ko-state>'
            + escape(state or 'Broncontext') + '</strong></p></header>'
            + (review_route(state, stage_second=_rejected_in_second_review(console, obj), required_second=route_second,
                            second_pending=second_pending)
               if annotation else '')
            + '<div class="ko-review-layout">' + _source_panel(console, inputs, obj, task='inventory')
            + '<section class="ko-object-panel" aria-labelledby="ko-object-title">'
            '<h2 id="ko-object-title">Vastgelegd kennisobject</h2>'
            '<p class="ko-claim" data-full-knowledge-passage data-reviewed-version="'
            + escape(descriptor.object_version, quote=True) + '">' + escape(descriptor.text)
            + '</p><p class="ko-type">' + escape(_object_type_label(descriptor.object_type)) + '</p>'
            + semantics + _summary_table(rows) + evidence_note + '<p>' + placement + '</p>'
            + '<details class="ko-evidence"><summary>Bekijk gekoppelde onderbouwing, broncontext en bronbewijs</summary>'
            + context_html + _additional_relations(descriptor) + _source_bound_fields_html(obj)
            + '</details></section></div><div class="ko-result-actions">'
            + '<a href="' + escape(inventory, quote=True) + '">Alle passages en beoordelingen bekijken</a>'
            + (correction_link if not published else '')
            + ('<a href="' + escape(review, quote=True) + '">Dit kennisobject beoordelen</a>'
               if not published and route and route.get('actionable') else '') + '</div></div>')
        return review_page_shell(account, body, title='Kennisobject')
    state = derive_ko_state(obj, review_path=path, bindings=inputs.bindings, fragments=inputs.fragments)['state']
    heading = 'Onafhankelijke tweede review' if second else 'Review'
    # #1064: in the second review only the reviewer who may decide sees 'Afwijzen'.
    rejection = '' if second and not (route and route.get('actionable')) else (
        '<details class="ko-reject"><summary>Afwijzen</summary><label>Toelichting bij afwijzing<textarea name="comment">'
        + escape(str(draft.get('comment') or '')) + '</textarea></label>'
        '<button class="ko-text-button" type="submit" name="review_action" value="reject" formnovalidate>Afwijzen met toelichting</button></details>')
    body = ('<header class="ko-page-heading"><h1>' + heading + '</h1>'
            + source_breadcrumb(sid, obj, title=inputs.envelope.get('title') or '', task=task or canonical_task, overview_url=overview_url)
            + '<p class="ko-progress">Te beoordelen passage <span aria-hidden="true">·</span> '
            + ('Versie ' + escape(descriptor.object_version) + history + ' <span aria-hidden="true">·</span> ' if annotation else '')
            + '<strong data-ko-state>' + escape({'saved': 'Correctie opgeslagen, nog niet opnieuw gebouwd',
                                                'building': 'Nieuwe versie wordt opgebouwd'}.get(rebuilding) or state or 'Broncontext') + '</strong>'
            + (' <span aria-hidden="true">·</span> Onafhankelijk tweede akkoord' if second else '')
            + (' <span data-required-second-review>Er is een onafhankelijke tweede beoordeling nodig.</span>' if required_second and not second else '') + '</p></header>'
            # #1067: where this object is and what happens next; only for objects from annotation.
            + (review_route(state, stage_second=second or _rejected_in_second_review(console, obj),
                            required_second=route_second, rebuilding=rebuilding or '',
                            second_pending=second_pending)
               if annotation else '')
            + notice + '<div class="ko-review-layout" data-document-assessment="'
            + escape(inputs.document_assessment, quote=True) + '">'
            + _source_panel(console, inputs, obj, task=task)
            + '<section class="ko-object-panel" aria-labelledby="ko-object-title"><h2 id="ko-object-title">Te beoordelen kennisobject</h2>'
            '<p class="ko-claim" data-full-knowledge-passage data-reviewed-version="' + escape(descriptor.object_version, quote=True) + '">'
            + escape(descriptor.text) + '</p><p class="ko-type">' + escape(_object_type_label(descriptor.object_type))
            + (' · voorgesteld type' if annotation and not obj.get('confirmed_object_type') else '') + '</p>'
            + ('' if choose_semantics else semantics) + _summary_table(rows)
            + '<details class="ko-evidence"' + (' open' if context_open else '') + '><summary>Bekijk gekoppelde onderbouwing, broncontext en bronbewijs</summary>'
            + context_html + _additional_relations(descriptor) + _source_bound_fields_html(obj) + '</details>'
            + '<form method="post" action="' + ('/review/second-review' if second else '/review')
            + '" class="ko-assessment-form" data-ko-assessment-form data-can-approve="' + str(can_approve).lower() + '">'
            + hidden + (semantics if choose_semantics else '')
            + ('<p class="ko-evidence-choice"><label><input type="checkbox" name="evidence_not_applicable" value="yes"'
               + (' checked' if draft.get('evidence_not_applicable') else '')
               + '> Onderbouwing is voor dit kennisobject niet van toepassing.</label></p>'
               if not literal_support and not any(row.get('relation_type') in {'supported_by', 'explains'}
                          and row.get('resolution') == 'current' for row in descriptor.relations) else '')
            + _question('applicable', 'Is dit toepasbaar?', draft.get('applicable'))
            + _question('complete', 'Is dit compleet?', draft.get('complete'), subline=_completeness_signals(obj))
            + _question('placed_correctly', 'Staat dit op de juiste plek?', draft.get('placed_correctly'), subline=placement)
            + '<div class="ko-actions"><div class="ko-submit-feedback">'
            '<span data-ko-submit-label="save" aria-hidden="true">Review wordt opgeslagen…</span>'
            '<span data-ko-submit-label="later" aria-hidden="true">Volgende passage wordt geopend…</span>'
            '<p class="ko-submit-status" data-ko-submit-status role="status"></p></div>'
            + '<button class="ko-primary" type="submit" name="review_action" value="approve"'
            + ('' if can_approve else ' disabled') + '>Goedkeuren en opslaan</button>'
            + correction_link
            + '<button class="ko-text-button" type="submit" name="review_action" value="later" formnovalidate>Later beoordelen</button></div>'
            + rejection + '</form></section></div>'
            + _assessment_script())
    return review_page_shell(account, body, title=heading)


def _assessment_script():
    return '''<script>
for (const form of document.querySelectorAll('[data-ko-assessment-form]')) {
  const submitters = form.querySelectorAll('button[name="review_action"]');
  const approve = form.querySelector('button[value="approve"]');
  const status = form.querySelector('[data-ko-submit-status]');
  const semanticAction = form.querySelector('[name="recommendation_review_action"]');
  const ownChoice = form.querySelector('[data-ko-review-own]');
  let submitting = false;
  const update = () => {
    if (ownChoice) {
      ownChoice.hidden = semanticAction.value !== 'decline';
      ownChoice.querySelectorAll('select').forEach(select => { select.disabled = ownChoice.hidden; });
    }
    const yes = ['applicable','complete','placed_correctly'].every(name => form.querySelector(`input[name="${name}"]:checked`)?.value === 'yes');
    approve.disabled = form.dataset.canApprove !== 'true' || !yes;
  };
  form.addEventListener('change', update);
  form.addEventListener('submit', event => {
    if (submitting) {
      event.preventDefault();
      return;
    }
    if (event.defaultPrevented || !event.submitter) return;
    submitting = true;
    // Keep the pressed button enabled for the native POST's review_action value.
    submitters.forEach(button => button.setAttribute('aria-disabled', 'true'));
    const label = event.submitter.value === 'later' ? 'later' : 'save';
    status.textContent = form.querySelector(`[data-ko-submit-label="${label}"]`).textContent;
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted || !submitting) return;
    submitting = false;
    submitters.forEach(button => button.removeAttribute('aria-disabled'));
    status.textContent = '';
    update();
  });
  update();
}
</script>'''


def compact_review_error(console, account, snapshot_id, object_id, revision, task, draft, error):
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
        'knowledge_evidence_required': 'Dit kennisobject heeft nog geen onderbouwing. Controleer de onderbouwing of geef aan dat deze niet van toepassing is.',
        'supporting_evidence_choice_invalid': 'Kies expliciet of onderbouwing niet van toepassing is.',
        'supporting_evidence_choice_conflict': 'Er is onderbouwing gekoppeld. Beoordeel of corrigeer de koppeling voordat je goedkeurt.',
        'review_assessment_answer_invalid': 'Kies bij iedere vraag Ja of Aanpassen.',
        'review_assessment_requires_three_yes': 'Voor goedkeuren moeten de drie antwoorden Ja zijn.',
        'review_assessment_unresolved_proposal': 'De getoonde interpretatie kan nog niet volledig worden bevestigd.',
        'recommendation_semantics_required': 'Kies richting én sterkte of laat beide velden leeg.',
        'recommendation_review_choice_invalid': 'Kies accepteren, weigeren of overslaan.',
        'recommendation_review_choice_conflict': 'Kies weigeren om zelf richting en sterkte te bevestigen.',
        'recommendation_review_proposal_changed': 'Het voorstel komt niet meer overeen. Bekijk het actuele voorstel en kies opnieuw.',
    }
    code = SNAPSHOT_OBJECT_WRITE_CONFLICT if conflict else getattr(error, 'code', str(error))
    message = messages.get(code) or ERROR_COPY.get(code) or 'Deze beoordeling is niet opgeslagen. Controleer de passage en probeer opnieuw.'
    if code == 'recommendation_review_proposal_changed':
        draft = {key: value for key, value in draft.items() if key != 'recommendation_review_action'}
    page = render_review_page(console, account, inputs, obj, task=task,
                              draft=draft, error=message, conflict=conflict or not revision.strip())
    return HTMLResponse(page, status_code=409 if conflict else 400, headers={'Cache-Control': 'no-store'})


def handle_compact_review(console, account, snapshot_id, object_id, revision, interaction_id, task,
                          action, values, comment='', *, second=False, evidence_not_applicable=False,
                          recommendation_action='', proposal_token='', semantics_choice=('', '')):
    from fastapi.responses import RedirectResponse
    from src.operations_console_v1 import ConsoleError
    from src.review.review_assessment_v1 import ReviewAssessment, displayed_review_descriptor, compact_approval_arguments
    from src.review.review_passage_read_v1 import read_review_passage, resolve_review_revision
    from src.review.review_interaction_v1 import build_review_interaction_evidence, REVIEW_INTERACTION_PREFIX
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    from src.review.ko_receipt_ui_v1 import receipt_location
    semantic_command = {}
    if not second and action == 'approve':
        semantic_command = {'recommendation_review_action': recommendation_action or 'skip',
                            'recommendation_proposal_token': proposal_token,
                            'recommendation_direction': semantics_choice[0],
                            'recommendation_strength_level': semantics_choice[1]}
    draft = {**values, 'comment': comment, 'evidence_not_applicable': evidence_not_applicable,
             **semantic_command}
    try:
        if not revision.strip():
            raise ConsoleError('snapshot_revision_required')
        if not interaction_id.strip():
            raise ConsoleError('review_assessment_required')
        interaction_id = interaction_id.strip()
        if not interaction_id.startswith(REVIEW_INTERACTION_PREFIX):
            raise ConsoleError('review_interaction_id_invalid')
        try:
            assessment = ReviewAssessment.from_values(**values)
        except ValueError as exc:
            raise ConsoleError(str(exc)) from exc
        if action not in {'approve', 'reject', 'later'}:
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
            if second and action == 'reject':
                # #1064: the second reviewer's rejection is final, like the first reviewer's.
                console.reject_second_review(actor_id=account['account_id'], snapshot_id=snapshot_id,
                    object_id=object_id, comment=comment,
                    expected_revision=resolve_review_revision(console, snapshot_id, revision),
                    interaction_evidence=evidence)
            elif second:
                expected = resolve_review_revision(console, snapshot_id, revision)
                console.approve_second_review(actor_id=account['account_id'], snapshot_id=snapshot_id,
                    object_id=object_id, expected_revision=expected, interaction_evidence=evidence,
                    evidence_not_applicable=evidence_not_applicable)
            else:
                kwargs = compact_approval_arguments(assessment, descriptor) if action == 'approve' else {
                    'suitability': 'geen_kenniseenheid', 'eindoordeel': 'afwijzen'}
                if descriptor.optional_recommendation_review and action == 'approve':
                    kwargs.update(semantic_command)
                console.review_object(actor_id=account['account_id'], snapshot_id=snapshot_id,
                    object_id=object_id, decision=action, comment=comment,
                    expected_revision=resolve_review_revision(console, snapshot_id, revision),
                    interaction_evidence=evidence, evidence_not_applicable=evidence_not_applicable, **kwargs)
        else:
            console.review_object(actor_id=account['account_id'], snapshot_id=snapshot_id,
                object_id=object_id, decision=action, comment=comment,
                **semantic_command,
                suitability='ja' if action == 'approve' else 'geen_kenniseenheid',
                eindoordeel='goedkeuren' if action == 'approve' else 'afwijzen',
                expected_revision=revision, _compact_result=True, _interaction_id=interaction_id,
                _review_assessment=assessment, evidence_not_applicable=evidence_not_applicable)
    except ConsoleError as error:
        return compact_review_error(console, account, snapshot_id, object_id, revision, task, draft, error)
    location = '/review?' + urlencode({'document': snapshot_id, 'after': object_id, 'task': task})
    return RedirectResponse(receipt_location(location, interaction_id, object_id), status_code=303)
