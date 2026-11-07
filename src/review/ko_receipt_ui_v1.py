"""Read-only receipt of an existing durable review interaction."""
from dataclasses import dataclass, replace
from html import escape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.integrity_kernel import canonical_object_payload, compute_canonical_object_hash, stable_hash
from src.knowledge_relations_v1 import confirmed_knowledge_relations_of, proposed_knowledge_relations_of
from src.review.review_cockpit_v1 import knowledge_review_projection, found_under_path
from src.review.review_interaction_v1 import _is_decision_event
from src.operations_console_v1 import ConsoleError


@dataclass(frozen=True)
class SavedReviewReceipt:
    snapshot_id: str
    event: dict
    object: dict
    related: tuple[dict, ...]
    current_version: str
    current_review_state: str
    document_title: str = ""
    publication_state: str = ""


def receipt_location(location, interaction_id, object_id):
    """Carry an existing evidence reference, never submitted success values."""
    if not interaction_id:
        return location
    parsed = urlsplit(location)
    params = dict(parse_qsl(parsed.query))
    params.update(receipt_interaction=interaction_id, receipt_object=object_id)
    return urlunsplit(parsed._replace(query=urlencode(params)))


def read_saved_review(console, account, snapshot_id, object_id, interaction_id):
    from src.workflows.workflow_transaction_v1 import workflow_read_transaction
    with workflow_read_transaction(console.workflow_document_store):
        console._require_role(account['account_id'], 'reviewer')
        receipt = _read_saved_review(console, account, snapshot_id, object_id, interaction_id)
    if receipt is None:
        return None
    try:
        publication = console.document_release_serving_status(snapshot_id).get('release_status', '')
    except ConsoleError:
        publication = ''
    return replace(receipt, publication_state=publication)


def _read_saved_review(console, account, snapshot_id, object_id, interaction_id):
    envelope, _ = console.workflow_document_store.review_document_input(snapshot_id)
    if account['account_id'] not in envelope.get('named_reviewers', []):
        raise ConsoleError('reviewer_not_named_on_snapshot')
    events = console.workflow_review_store.read_review_command_events(
        snapshot_id, [], interaction_id=interaction_id, include_pending=False)
    own = []
    for event in events:
        details = event.get('details') or {}
        interaction = details.get('review_interaction') or {}
        body = {key: value for key, value in event.items() if key != 'event_hash'}
        if (event.get('event_hash') == stable_hash(body)
                and details.get('snapshot_id') == snapshot_id
                and (details.get('reviewer_id') or details.get('second_reviewer_id')) == account['account_id']
                and _is_decision_event(event) and event.get('object_id') == object_id
                and interaction.get('interaction_id') == interaction_id
                and interaction.get('snapshot_id') == snapshot_id
                and interaction.get('reviewer_account_id') == account['account_id']):
            own.append(event)
    if len(own) != 1:
        return None
    event = own[0]
    details = event.get('details') or {}
    digest = details.get('review_snapshot_hash') or details.get('canonical_object_hash')
    if not digest:
        return None
    manifest = (details.get('review_interaction') or {}).get('context_manifest') or {}
    expected = {(object_id, str(event.get('object_version') or ''), digest)}
    for link in manifest.get('links') or []:
        for endpoint in ('source', 'target'):
            row = link.get(endpoint) or {}
            if row.get('object_id') != object_id and row.get('current_canonical_object_hash'):
                expected.add((row['object_id'], row.get('current_version') or row.get('expected_version') or '',
                              row['current_canonical_object_hash']))
    histories = console.workflow_document_store.review_command_histories(
        snapshot_id, sorted({item[0] for item in expected}))
    from src.review.revision_workflow import current_revisions
    try:
        current_rows = current_revisions(histories, snapshot_id=snapshot_id)
    except ValueError:
        return None
    resolved = {}
    for row in histories:
        key = (str(row.get('object_id') or ''), str(row.get('object_version') or ''),
               compute_canonical_object_hash(row))
        if key in expected:
            resolved[key] = row
    focal = resolved.get((object_id, str(event.get('object_version') or ''), digest))
    if focal is None:
        return None
    related = tuple(canonical_object_payload(row) for key, row in resolved.items() if key[0] != object_id)
    from src.review.knowledge_object_state_v1 import derive_ko_state
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    current = next(row for row in current_rows if row['object_id'] == object_id)
    bindings = console.workflow_review_store.read_bindings([snapshot_id], object_ids=[object_id]).get(snapshot_id, [])
    state = derive_ko_state(current, review_path=review_path_for_klasse(envelope['class']),
                           bindings=bindings)['state'] or 'Broncontext of structuur'
    return SavedReviewReceipt(snapshot_id, event, canonical_object_payload(focal), related,
                              str(current.get('object_version') or ''), state,
                              str(envelope.get('title') or ''))


_RELATION_LABELS = {
    'applies_if': 'Geldt wanneer', 'except_if': 'Tenzij',
    'supported_by': 'Onderbouwd door', 'explains': 'Onderbouwd door',
    'defines': 'Definieert', 'supersedes': 'Vervangt',
}
_CONTEXT_LABELS = {'condition': 'Geldt wanneer', 'exception': 'Tenzij',
                   'scope': 'Doelgroep en afbakening', 'target_group': 'Doelgroep',
                   'support': 'Onderbouwd door', 'context': 'Broncontext'}


@dataclass(frozen=True)
class KnowledgeConnection:
    label: str
    text: str
    origin: str = ''
    status: str = ''


def _scope_connections(obj):
    from src.vorming.source_bound_fields_v2 import KEY, bound_values
    record = (obj.get('metadata') or {}).get(KEY)
    if not record:
        return []
    try:
        values = bound_values(record, text=str((obj.get('content') or {}).get('clean_text') or ''),
            proposed_type=str(obj.get('proposed_object_type') or 'unclassified'),
            context=((obj.get('metadata') or {}).get('source_bound_context') or {}).get('entries') or [])
    except ValueError:
        return [KnowledgeConnection('Doelgroep en afbakening',
            'Het veldbewijs past niet meer bij deze passage; opnieuw controleren is nodig.')]
    labels = {'actor_of_scope': 'Actor of doelgroep', 'actor_span': 'Uitvoerder',
              'target_group_span': 'Doelgroep', 'scope_span': 'Afbakening'}
    missing = {'not_stated': 'Niet expliciet vermeld', 'uncertain': 'Onzeker',
               'not_applicable': 'Niet van toepassing'}
    rows = []
    for field, label in labels.items():
        evidence = (record.get('evidence') or {}).get(field)
        if evidence is not None:
            text = values.get(field) or missing.get(evidence.get('missing_reason'), 'Ontbreekt')
            rows.append(KnowledgeConnection(label, str(text)))
    return rows


def _knowledge_connections(obj, objects, *, include_proposals=False):
    projected = knowledge_review_projection(obj, list(objects))
    rows = _scope_connections(obj)
    for item in projected['essential_context']:
        label = _CONTEXT_LABELS.get(item['role'], str(item['role']))
        status = 'Nog niet geldig verbonden' if item.get('status') != 'bound' else ''
        record = ((obj.get('metadata') or {}).get('source_bound_context') or {})
        entry = next((row for row in record.get('entries') or []
            if row.get('role') == item['role'] and row.get('text') == item.get('text')), {})
        locators = list(dict.fromkeys(str((ref.get('source_locator') or {}).get('locator_value') or '')
            for ref in entry.get('source_refs') or []))
        origin = ' · '.join(value for value in locators if value)
        source_id = item.get('source_object_id')
        linked = next((row for row in objects if row.get('object_id') == source_id), None)
        if linked is not None:
            origin = found_under_path(linked) + ' · versie ' + str(linked.get('object_version') or '')
        rows.append(KnowledgeConnection(label, str(item.get('text') or ''), origin, status))
    by_key = {(row.get('object_id'), row.get('object_version')): row for row in objects}
    for source in objects:
        confirmed = [(relation, '') for relation in confirmed_knowledge_relations_of(source)]
        proposals = ([(relation, 'Voorstel, nog niet bevestigd') for relation in proposed_knowledge_relations_of(source)]
                     if include_proposals else [])
        for relation, status in [*confirmed, *proposals]:
            kind = str(relation.get('relation_type') or '')
            if kind not in _RELATION_LABELS:
                continue
            own = source.get('object_id') == obj.get('object_id')
            targets_focal = (relation.get('target_object_id') == obj.get('object_id')
                             and relation.get('target_object_version') == obj.get('object_version'))
            if not own and not targets_focal:
                continue
            target = (by_key.get((relation.get('target_object_id'), relation.get('target_object_version')))
                      if own else source)
            label = _RELATION_LABELS[kind] if own else {
                'explains': 'Onderbouwt', 'supported_by': 'Onderbouwt',
                'defines': 'Gedefinieerd door', 'applies_if': 'Voorwaarde voor',
                'except_if': 'Uitzondering voor', 'supersedes': 'Vervangen door',
            }[kind]
            text = str((target.get('content') or {}).get('clean_text') or '') if target else ''
            if not text:
                text = 'De inhoud van deze gekoppelde versie kon niet worden bevestigd.'
            origin = (found_under_path(target) + ' · versie ' + str(target.get('object_version') or '')) if target else ''
            rows.append(KnowledgeConnection(label, text, origin, status))
    return list(dict.fromkeys(rows))


def knowledge_connections_html(obj, objects, *, include_proposals=False):
    """Readable branches from one claim; no inferred relationships or completeness."""
    rows = _knowledge_connections(obj, objects, include_proposals=include_proposals)
    return _connection_scope_html(rows) + _connection_branches_html(rows)


def _connection_scope_html(rows):
    primary = ('Geldt wanneer', 'Tenzij', 'Onderbouwd door')
    scopes = [row for row in rows if row.label not in primary]
    if not scopes:
        return ''
    return ('<dl class="ko-scope">' + ''.join(
        f'<dt>{escape(row.label)}</dt><dd>{escape(row.text)}'
        + (f' <span class="meta">{escape(row.origin)}</span>' if row.origin else '')
        + (f' <strong>{escape(row.status)}</strong>' if row.status else '') + '</dd>' for row in scopes) + '</dl>')


def _connection_branches_html(rows):
    primary = ('Geldt wanneer', 'Tenzij', 'Onderbouwd door')
    branches = []
    missing = {'Geldt wanneer': 'Geen afzonderlijke voorwaarde vastgelegd.',
               'Tenzij': 'Geen afzonderlijke uitzondering vastgelegd.',
               'Onderbouwd door': 'Geen afzonderlijke onderbouwing gekoppeld.'}
    for label in primary:
        items = [row for row in rows if row.label == label]
        text = ''.join(f'<p>{escape(row.text)}</p>'
            + (f'<p class="meta">{escape(row.origin)}</p>' if row.origin else '')
            + (f'<p><strong>{escape(row.status)}</strong></p>' if row.status else '') for row in items)
        if not items:
            text = f'<p class="field-help">{missing[label]} Dit betekent niet automatisch niet van toepassing.</p>'
        branches.append(f'<li><strong class="ko-connection-label">{label}</strong>{text}</li>')
    return ('<section data-essential-context aria-label="Context en samenhang van de claim">'
            + '<ul class="ko-connections" data-knowledge-connections>'
            + ''.join(branches) + '</ul></section>')


def render_ko_receipt(receipt):
    if receipt is None:
        return ('<aside class="banner warn" data-review-outcome-unconfirmed role="status">'
                'Het opgeslagen resultaat van deze handeling kon niet exact worden bevestigd. '
                'Controleer de actuele passage voordat je opnieuw een besluit neemt.</aside>')
    from src.operations_console_app import _object_type_label
    obj, event = receipt.object, receipt.event
    kind = str(event['event_type'])
    if kind == 'second_review_approve':
        action, title = 'Je onafhankelijke tweede akkoord is opgeslagen.', 'Dit heb je goedgekeurd'
    elif kind.endswith('_review_approve'):
        action, title = ('Je eigen eerste akkoord is opgeslagen. Dit rondt een eventueel vereiste onafhankelijke tweede beoordeling niet af. '
                         'De actuele vervolgbeoordelingen staan in het overzicht.'), 'Dit heb je goedgekeurd'
    elif kind.endswith('_review_reject'):
        action, title = 'Je afwijzing is opgeslagen.', 'Dit heb je afgewezen'
    else:
        action, title = 'Je verzoek om correctie is opgeslagen; dit is geen goedkeuring.', 'Dit heb je gedaan'
    source_url = '/review/brondocument?' + urlencode(dict(document=receipt.snapshot_id, object=obj['object_id'], download='true'))
    text = str((obj.get('content') or {}).get('clean_text') or '')
    details = event.get('details') or {}
    comment = str(details.get('comment') or '')
    connections = _knowledge_connections(obj, [obj, *receipt.related])
    return (f'<section class="ko-receipt" data-review-receipt aria-label="Bon van opgeslagen review">'
            f'<header><h2>Review opgeslagen</h2><p>{escape(action)}</p></header>'
            f'<p data-receipt-current-state><strong>Actuele reviewtoestand</strong> '
            f'{escape(receipt.current_review_state)} · versie {escape(receipt.current_version)}. '
            'De bon hieronder hoort bij de opgeslagen handeling en versie.</p>'
            f'<h3>{escape(title)}</h3><h3>Zo is het kennisobject vastgelegd</h3>'
            f'<div class="ko-receipt-claim"><p>{escape(text)}</p>'
            f'<span class="meta">{escape(_object_type_label(str(obj.get("confirmed_object_type") or obj.get("object_type") or "")))}'
            f' · versie {escape(str(event.get("object_version") or ""))}</span>'
            + _connection_scope_html(connections) + '</div>'
            + _connection_branches_html(connections)
            + f'<p class="ko-receipt-source"><strong>Herkomst</strong> · {escape(found_under_path(obj))} '
              f'<a href="{escape(source_url, quote=True)}">Download volledige oorspronkelijke bron</a></p>'
            + (f'<p><strong>Jouw toelichting</strong> {escape(comment)}</p>' if comment else '')
            + '<p class="field-help">Deze bon hoort bij de hierboven genoemde opgeslagen versie en handeling. '
              'Een reviewakkoord is geen publicatie. De actuele toestand staat bij de passage in het overzicht.</p>'
              '</section>')


def render_receipt_page(account, receipt, snapshot_id, continuation):
    from src.review.ko_review_page_v1 import review_page_shell, source_breadcrumb
    from src.review.review_assessment_v1 import ReviewAssessment
    from src.review.knowledge_object_state_v1 import GOEDGEKEURD
    from src.operations_console_app import _object_type_label
    overview = '/review?' + urlencode({'document': snapshot_id})
    if receipt is None:
        return review_page_shell(account, '<h1>Opslag niet bevestigd</h1>'
            + render_ko_receipt(None) + '<p><a href="' + escape(overview, quote=True)
            + '">Terug naar overzicht</a></p>', title='Opslag niet bevestigd')
    obj, event = receipt.object, receipt.event
    object_location = '/review?' + urlencode({'document': snapshot_id, 'object': obj['object_id'], 'task': 'inventory'})
    kind = str(event['event_type'])
    approved = kind.endswith('_review_approve') or kind == 'second_review_approve'
    rejected = kind.endswith('_review_reject')
    decision = 'goedgekeurd' if approved else 'afgewezen' if rejected else 'correctie gevraagd'
    comment = str((event.get('details') or {}).get('comment') or '')
    heading = 'Dit heb je goedgekeurd. Zo hangt het samen.' if approved else 'Dit heb je vastgelegd. Zo hangt het samen.'
    saved_version = str(event.get('object_version') or '')
    details = event.get('details') or {}
    assessment = ReviewAssessment.from_evidence(details.get('assessment') or (details.get('review_interaction') or {}).get('assessment'))
    evidence_not_applicable = (details.get('supporting_evidence') or {}).get('applicability') == 'not_applicable'
    check = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4 10-10"/></svg>'
    saved_answers = []
    for key, label in (('applicable', 'Toepasbaar'), ('complete', 'Compleet'), ('placed_correctly', 'Juiste plek')):
        value = getattr(assessment, key) if assessment is not None else None
        icon = '<span class="ko-answer-icon">' + check + '</span>' if value == 'yes' else ''
        state = '' if value == 'yes' else '<span class="ko-answer-unknown">' + ('Aanpassen' if value == 'adjust' else 'Niet afzonderlijk vastgelegd') + '</span>'
        saved_answers.append('<div class="ko-saved-answer" data-saved-answer="' + key + '" data-answer="'
            + (value or 'unrecorded') + '">' + icon + '<span>' + label + state + '</span></div>')
    connections = _knowledge_connections(obj, [obj, *receipt.related])
    branches = []
    for label, title in (('Geldt wanneer', 'Voorwaarde'), ('Tenzij', 'Uitzondering'), ('Onderbouwd door', 'Gekoppelde onderbouwing')):
        items = [row for row in connections if row.label == label]
        text = ''.join('<p>' + escape(row.text) + '</p>'
            + ('<small>' + escape(row.origin) + '</small>' if row.origin else '')
            + ('<p class="ko-connection-status">' + escape(row.status) + '</p>' if row.status else '') for row in items)
        if label == 'Onderbouwd door' and evidence_not_applicable:
            text = '<p data-saved-evidence-applicability="not_applicable">Bij deze beoordeling expliciet niet van toepassing verklaard.</p>'
        elif not text:
            text = '<p class="ko-muted">Niet afzonderlijk vastgelegd. Dit betekent niet automatisch niet van toepassing.</p>'
        branches.append('<li><span class="ko-branch-label">' + label.lower() + '</span>'
            '<div class="ko-branch-body"><h3>' + title + '</h3>' + text + '</div></li>')
    publication = {'none': 'Nog niet gepubliceerd', 'published': 'Gepubliceerd',
                   'withdrawn': 'Ingetrokken', 'superseded': 'Vervangen'}.get(receipt.publication_state, 'Niet vastgesteld')
    status_class = 'ko-status' + ('' if receipt.current_review_state == GOEDGEKEURD else ' ko-status-neutral')
    old_version = receipt.current_version != saved_version
    current_note = ('<p class="ko-notice">Er is inmiddels een nieuwere versie ' + escape(receipt.current_version)
        + '. Deze bon blijft horen bij de opgeslagen handeling op versie ' + escape(saved_version) + '.</p>') if old_version else ''
    source = '/review/brondocument?' + urlencode({'document': snapshot_id, 'object': obj['object_id'], 'download': 'true'})
    stage_note = ('<p class="ko-saved-version">Je eigen eerste akkoord bevestigt geen eventueel vereiste onafhankelijke tweede beoordeling.</p>'
                  if approved and kind != 'second_review_approve' else '')
    body = ('<div data-review-receipt><header class="ko-receipt-heading"><span class="ko-result-mark">' + check
        + '</span><div><h1>Review opgeslagen</h1><p>' + heading + '</p></div></header>'
        + source_breadcrumb(snapshot_id, obj, title=receipt.document_title) + current_note
        + '<div class="ko-result-layout"><section class="ko-result-main"><dl class="ko-result-metadata">'
        '<div><dt>Kennisobject</dt><dd><strong>' + escape((obj.get('structure') or {}).get('section_path', [''])[-1] if (obj.get('structure') or {}).get('section_path') else _object_type_label(str(obj.get('confirmed_object_type') or obj.get('object_type') or '')))
        + '</strong></dd></div><div><dt>Actuele reviewstatus</dt><dd><span class="' + status_class + '">' + escape(receipt.current_review_state)
        + '</span></dd></div><div><dt>Opgeslagen versie</dt><dd>Versie ' + escape(saved_version)
        + '</dd></div><div><dt>Publicatie document</dt><dd><span class="ko-status ko-status-neutral">' + escape(publication)
        + '</span></dd></div></dl><section class="ko-result-diagram" aria-label="Samenhang van het opgeslagen kennisobject"><h2>Zo is het kennisobject vastgelegd</h2>'
        '<div class="ko-result-claim"><span class="ko-type-badge">' + escape(_object_type_label(str(obj.get('confirmed_object_type') or obj.get('object_type') or '')))
        + '</span><p data-full-knowledge-passage>' + escape(str((obj.get('content') or {}).get('clean_text') or '')) + '</p>'
        + _connection_scope_html(connections) + '</div>'
        '<ul class="ko-result-branches" data-knowledge-connections>' + ''.join(branches) + '</ul>'
        '<div class="ko-source-band"><strong>Herkomst</strong><span>' + escape(found_under_path(obj))
        + '</span><a href="' + escape(source, quote=True) + '">Open oorspronkelijke bron</a></div></section></section>'
        '<aside class="ko-assessment-aside"><section class="ko-assessment-receipt"><h2>Jouw beoordeling</h2>' + ''.join(saved_answers)
        + '<p class="ko-saved-decision">Besluit: <strong>' + decision + '</strong></p>'
        + ('<p><strong>Jouw toelichting</strong> ' + escape(comment) + '</p>' if comment else '') + '</section>'
        '<p class="ko-saved-version">Dit overzicht hoort bij de opgeslagen versie ' + escape(saved_version) + '.</p>' + stage_note
        + '</aside></div><div class="ko-result-actions"><a class="ko-primary" data-ko-next-passage href="'
        + escape(continuation, quote=True) + '">Volgende passage</a><a data-ko-view-object href="'
        + escape(object_location, quote=True) + '">Bekijk het huidige kennisobject</a><a data-ko-back-overview href="'
        + escape(overview, quote=True) + '">Terug naar overzicht</a></div></div>')
    return review_page_shell(account, body, title='Review opgeslagen')
