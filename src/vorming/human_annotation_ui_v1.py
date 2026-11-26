"""Source-first annotation workplace; every saved choice is server-confirmed."""
from html import escape
import json
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid4, uuid5
import asyncio
from urllib.parse import quote, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from src.operations_console_v1 import ConsoleError
from src.vorming import annotation_document_check_v1 as document_check
from src.vorming import annotation_section_coverage_v1 as section_coverage
from src.vorming import confirmed_document_structure_v1 as structure
from src.vorming import human_annotation_v1 as domain
from src.vorming.source_accountability_v1 import ROLES as SOURCE_ROLES

LABELS = {'core':'Kernuitspraak','population':'Doelgroep','context':'Context','condition':'Voorwaarde',
    'exception':'Uitzondering','explanation':'Toelichting','evidence':'Onderbouwing',
    'actor':'Uitvoerder','scope':'Toepassingssituatie','timing':'Tijdstip of periode',
    'list_introduction':'Inleiding bij een lijst','row_header':'Rijkop','column_header':'Kolomkop'}
TYPES = {'recommendation':'Aanbeveling','definition':'Definitie','explanation':'Toelichting','condition':'Voorwaarde','exception':'Uitzondering','factual_finding':'Feitelijke bevinding'}
FIELD_LABELS={'subject_span':'Over wie of wat gaat de uitspraak?','predicate_span':'Wat wordt daarover gezegd?',
    'recommended_action':'Welke handeling wordt aanbevolen?','action_object_or_goal':'Waarop is de handeling gericht?',
    'defined_term':'Welk begrip wordt gedefinieerd?','definiens_span':'Wat is de definitie?',
    'condition_target':'Waarvoor geldt deze voorwaarde?','exception_target':'Waarop is dit een uitzondering?',
    'supported_object':'Welke uitspraak wordt toegelicht?',
    'actor_span':'Wie voert de handeling uit?','target_group_span':'Voor welke doelgroep?',
    'scope_span':'In welke situatie geldt dit?','condition_span':'Welke voorwaarde hoort erbij?'}
SOURCE_LABELS={'document_metadata':'Documentgegevens','page_furniture':'Kop- of voettekst',
    'navigation':'Navigatie','document_structure':'Kop of documentstructuur',
    'unformed_meaning':'Nog niet tot een uitspraak gevormd','uncertain_source_role':'Bronfunctie nog onzeker'}
ERRORS = {
    domain.HISTORICAL_NEUTRAL:'Deze eerdere annotatieversie heeft een oud opslagformaat. Controleer de selectie en sla de annotatie opnieuw op.',
    domain.HISTORICAL_DECISION:'Deze annotatie is opgeslagen in een eerder formaat. Je kunt haar bekijken in het documentoverzicht. Omzetten is nodig voordat je haar kunt wijzigen of het document kunt afsluiten.',
    'annotation_core_duplicate':'Deze kernbereiken horen al bij een andere annotatie. Verwijder het dubbele kernbereik of wijs andere kernbereiken aan om dit concept te bewaren. De oorspronkelijke annotatie blijft bewaard.',
    'annotation_objects_stale':'De objectversie of beoordeling is gewijzigd. Open de opgeslagen annotatie opnieuw; je huidige aanwijzingen blijven hier zichtbaar.',
    'annotation_revision_storage_not_ready':'Broncorrecties kunnen nog niet worden opgeslagen. Laat de beheerder de annotatieopslag bijwerken; de huidige versie blijft bewaard.',
    'annotation_replacement_required':'Een opgebouwd kennisobject kan niet zo worden teruggenomen of vervangen. Behoud deze annotatie en gebruik de expliciete opvolgerroute.',
    'annotation_identity_conflict':'Deze selectie botst met de identiteit van een eerder opgebouwd kennisobject. Pas de oorspronkelijke annotatie aan; maak hiervoor geen nieuwe annotatie.',
    'annotation_overview_stale':'De opgeslagen keuzes of documentgegevens zijn gewijzigd. Controleer het vernieuwde documentoverzicht voordat je afsluit.',
    'annotation_document_incomplete':'Er ontbreken nog keuzes of er is nog bronmateriaal niet verantwoord. Controleer het documentoverzicht.',
    'annotation_build_storage_not_ready':'Het document kan nog niet worden afgesloten. De beheerder moet de annotatieopslag eerst bijwerken. Je opgeslagen annotaties blijven bewaard.',
    'annotation_seal_stale':'De bronkeuzes of documentgegevens zijn gewijzigd. Controleer het nieuwe documentoverzicht en sluit die versie af.',
    'processing_attempt_in_progress':'Er loopt al een bouwopdracht voor dit document. Open de opgeslagen bouwopdracht.',
    'annotation_input_storage_not_ready':'Annotaties kunnen nog niet worden opgeslagen. De beheerder moet de annotatieopslag eerst bijwerken. Je aanwijzingen blijven hier zichtbaar.',
    'annotation_write_conflict':'Een andere wijziging is al opgeslagen. Open de opgeslagen versie opnieuw; je huidige aanwijzingen blijven hier zichtbaar.',
    'annotation_command_conflict':'Dit verzoek is al gebruikt met andere keuzes. Open de opgeslagen versie opnieuw.',
    'annotation_anchor_mismatch':'De geselecteerde tekst past niet bij deze bronpositie. Open de bron opnieuw en wijs het bereik opnieuw aan.',
    'annotation_grapheme_boundary_invalid':'De selectie knipt een samengesteld teken door. Selecteer het volledige teken.',
    'annotation_representation_stale':'De bronversie wijkt af. Hervat de oorspronkelijke werkversie; oude selecties worden niet verplaatst.',
    'annotation_evidence_required':'Er is onderbouwing gekoppeld én vastgelegd dat die niet van toepassing is. Kies één van beide.',
    'annotation_core_required':'Wijs een kernuitspraak aan en kies het type voordat je deze selectie gereed meldt.',
    'annotation_pending_range':'Er staat nog een aanwijzing klaar. Voeg die toe aan de annotatie of neem haar terug.',
    'annotation_evidence_function_required':'Kies bij onderbouwing of deze de uitspraak onderbouwt of verklaart.',
    'annotation_source_owned':'Deze bron wordt door een researcher geannoteerd. Hervat de annotaties.',
    'annotation_client_contract_stale':'Dit formulier mist nieuw opgeslagen onderdelen. Open de opgeslagen annotatie opnieuw; er is niets overschreven.',
    'annotation_source_disposition_invalid':'Kies een bronfunctie voor dit bronstuk. Voor een uitspraak gebruik je een eigen annotatie met het passende type.',
    'annotation_source_disposition_unresolved':'Dit bronstuk is nog niet afgehandeld. Kies een vastgestelde bronfunctie en wijs de bijbehorende bronbereiken aan.',
    'annotation_source_role_stale':'De open brontekst of het voorstel is gewijzigd. Controleer de actuele tekst in het document.',
    'source_bound_fields_invalid':'De onderdelen van de uitspraak zijn niet volledig aangeleverd. Open de annotatie opnieuw.',
    'source_bound_field_invalid':'Wijs voor dit onderdeel de exacte brontekst aan.',
    'recommendation_strength_label_not_applicable':'Dit sterktelabel hoort niet bij deze uitspraak. Haal het label weg of wijs het bijbehorende label aan.',
    'recommendation_strength_evidence_conflict':'De bron geeft strijdige sterktelabels bij deze uitspraak. Controleer de selectie.',
    'recommendation_strength_label_cross_section':'Dit label staat in een ander brononderdeel. Kies het label bij deze uitspraak.',
    'recommendation_semantics_invalid':'Controleer de richting en sterkte bij deze aanbeveling en wijs het bijbehorende bronbewijs aan.',
    'annotation_context_proposal_open':'Metis stelt tekst voor die bij deze uitspraak hoort. Voeg het voorstel in de kaart toe met + of wijs het af met −.',
    'annotation_declined_context_invalid':'Een afgewezen voorstel past niet bij deze bron. Open de opgeslagen annotatie opnieuw.',
}
# A point without its own sentence still offers the one action that always works in the card.
UNKNOWN_FINDING = 'Metis kan deze uitspraak zo niet vastleggen. Haal haar weg met − en selecteer haar opnieuw in de bron.'
FINDINGS = {**ERRORS,
    # #1067: every point the card can still show says what is wrong and what to do, in the card.
    'context_necessary_unresolved':'Er is tekst als noodzakelijk voor de betekenis aangemerkt die niet meer gekoppeld is. Selecteer de tekst in de bron en kies Aanvullende context.',
    'recommendation_evidence_missing':'Sla de uitspraak opnieuw op; de aanbeveling moet zelf als uitspraak zijn vastgelegd.',
    'type_evidence_missing':'Sla de uitspraak opnieuw op; de uitspraak moet zelf als bewijs voor haar soort zijn vastgelegd.',
    'recommendation_core_omits_source':'De uitspraak laat woorden uit de bron weg. Haal haar weg met − en selecteer de hele zin opnieuw.',
    'recommendation_core_field_mismatch':'Een onderdeel van de aanbeveling past niet bij de geselecteerde tekst. Haal de uitspraak weg met − en selecteer haar opnieuw.',
    'source_fidelity_failure':'De vastgelegde tekst komt niet letterlijk overeen met de bron. Haal de uitspraak weg met − en selecteer haar opnieuw.',
    'span_not_in_source':'De vastgelegde tekst staat niet letterlijk in de bron. Haal de uitspraak weg met − en selecteer haar opnieuw.',
    'annotation_context_proposal_open':'Metis stelt tekst voor die bij deze uitspraak hoort. Voeg het voorstel toe met + of wijs het af met −.',
    'annotation_source_empty':'Er is geen leesbare brontekst beschikbaar. Controleer het vastgelegde origineel voordat je verdergaat.',
    'annotation_not_ready':'Deze annotatie is nog niet gereed.',
    'annotation_fields_required':'Wijs de noodzakelijke betekenisvelden van deze uitspraak aan.',
    'annotation_relation_target_missing':'Wijs expliciet aan bij welke uitspraak dit onderdeel hoort.',
    'annotation_structure_confirmation_required':'Bevestig eerst de inhoudsopgave op de annotatiewerkplek.',
    'annotation_document_round_required':'Rond eerst de annotatieronde af.',
    'annotation_document_coverage_required':'Kijk deze sectie na op gemiste uitspraken.',
    'annotation_knowledge_required':'Leg ten minste één gereedstaande kennisannotatie vast.',
    'annotation_source_unaccounted':'Er is nog bronmateriaal niet verantwoord. De betreffende tekst staat hieronder.',
    'source_assessment_overlap':'Een bronrolvoorstel overlapt een uitspraak of ander bronrolvoorstel. Controleer beide annotaties.',
    'predicate_missing':'Wijs aan wat over het onderwerp wordt gezegd.',
    'subject_missing':'Wijs aan over wie of wat de uitspraak gaat.',
    'type_contract_incomplete':'Er ontbreekt een noodzakelijk betekenisveld voor dit type uitspraak.',
    'recommendation_direction_missing':'Kies de richting van deze aanbeveling en wijs het bronbewijs aan.',
    'recommendation_strength_unmapped':'De vermelde sterkte is nog onzeker. Controleer de betekenis en het bronbewijs.',
    'incomplete_sentence':'De kern lijkt een onvolledige zin. Controleer of de hele uitspraak is geselecteerd.',
    'no_independent_claim':'Controleer of de kern een zelfstandige uitspraak bevat.',
    'recommendation_subject_missing':'Wijs het onderwerp van deze aanbeveling aan.',
    'recommendation_recommended_action_missing':'Wijs de aanbevolen handeling aan.',
    'recommendation_action_object_or_goal_missing':'Wijs aan waarop de handeling gericht is.',
    'supported_object_missing':'Wijs aan welke uitspraak wordt toegelicht.',
    'condition_target_missing':'Wijs aan waarvoor deze voorwaarde geldt.',
    'exception_target_missing':'Wijs aan waarop dit een uitzondering is.',
}


# #1060: what Metis could not derive. A question for a human, never a blocker.
SIGNALS = {
    'recommendation_semantics_open':'Richting en sterkte van deze aanbeveling stelt de reviewer vast.',
    'subject_missing':'Niet vastgesteld over wie of wat de uitspraak gaat.',
    'recommendation_subject_missing':'Niet vastgesteld over wie of wat de aanbeveling gaat.',
    'predicate_missing':'Niet vastgesteld wat erover gezegd wordt.',
    'type_contract_incomplete':'Een onderdeel dat bij dit type hoort is niet vastgesteld.',
    'recommendation_recommended_action_missing':'De aanbevolen handeling is niet vastgesteld.',
    'recommendation_action_object_or_goal_missing':'Niet vastgesteld waarop de handeling gericht is.',
    'supported_object_missing':'De uitspraak leunt mogelijk op andere tekst. Hoort er een zin bij?',
    'condition_target_missing':'Niet vastgesteld waarvoor deze voorwaarde geldt. Hoort er een zin bij?',
    'exception_target_missing':'Niet vastgesteld waarop dit een uitzondering is. Hoort er een zin bij?',
    'annotation_relation_target_missing':'Niet vastgesteld bij welke uitspraak dit hoort. Hoort er een zin bij?',
    'incomplete_sentence':'De uitspraak lijkt een afgebroken zin. Is de hele zin geselecteerd?',
    'no_independent_claim':'De uitspraak staat mogelijk niet op zichzelf. Hoort er een zin bij?',
    'recommendation_core_incomplete':'De aanbeveling lijkt afgebroken. Is de hele zin geselecteerd?',
}


CHECK_FIELDS = {'subject_missing':'subject_span','recommendation_subject_missing':'subject_span',
    'predicate_missing':'predicate_span','supported_object_missing':'supported_object',
    'condition_target_missing':'condition_target','exception_target_missing':'exception_target',
    'recommendation_recommended_action_missing':'recommended_action','recommendation_action_object_or_goal_missing':'action_object_or_goal'}


def location_label(block):
    labels = ['Bronblok '+str(block['position']+1)]
    for loc in block['locations']:
        if loc['page']:
            label = 'pagina '+str(loc['page'])
        else:
            value = str((loc['locator'] or {}).get('locator_value') or '')
            match = re.match(r'lines:(\d+)-(\d+)',value)
            label = ('regels '+match[1]+'–'+match[2]) if match else value
        if label and label not in labels:
            labels.append(label)
    return ' · '.join(labels)


def source_contents_html(entries, *, coverage=None, document='', editable=True):
    if not entries:
        return ''
    full = coverage is not None and coverage['scope'] == 'full'

    def coverage_form(fields, label, *, target=''):
        params = {'document': document, 'basis': coverage['basis'], **fields}
        hidden = ''.join(f'<input type="hidden" name="{key}" value="{escape(value, quote=True)}">'
                         for key, value in params.items())
        target_label = f' aria-label="{escape(label + ": " + target, quote=True)}"' if target else ''
        return ('<form method="post" action="/annotations/coverage" data-coverage-form>'
                + hidden + f'<button type="submit"{target_label}>{label}</button></form>')

    items = []
    for row in coverage['sections'] if full else entries:
        target = quote(row['block_id'], safe='')
        detail = ''
        if full:
            status = {'checked': 'Nagekeken', 'stale': 'Opnieuw nakijken', 'open': 'Nog te controleren'}[row['status']]
            detail = f'<span class="annotation-section-status" data-section-status="{row["status"]}">{status}</span>'
            if editable and row['status'] != 'checked':
                detail += coverage_form({'section': row['block_id'], 'fingerprint': row['fingerprint']},
                                        'Markeer als nagekeken', target=row['title'])
        items.append(
            f'<li style="--contents-indent:{row["level"] - 1}">'
            f'<a href="#{target}">{escape(row["title"])}</a>{detail}</li>'
        )
    scope = ''
    if coverage is not None and editable:
        scope = (coverage_form({'scope': 'selection'}, 'Alleen selectie vastleggen') if full else
                 coverage_form({'scope': 'full'}, 'Dekking hele richtlijn controleren'))
    return ('<nav class="annotation-contents" aria-label="Inhoudsopgave">'
            '<h2 tabindex="-1">Inhoudsopgave</h2>' + scope + '<ul>' + ''.join(items) + '</ul></nav>')


def confirm_contents_html(document, basis, entries):
    rows = []
    for index, row in enumerate(entries, 1):
        options = ''.join(
            f'<option value="{level}"{" selected" if level == row["level"] else ""}>Niveau {level}</option>'
            for level in range(1, 5)
        )
        rows.append(
            '<li><input type="hidden" name="anchor" value="' + escape(row['block_id'], quote=True) + '">'
            f'<label for="heading-{index}">Kop {index}</label>'
            f'<input id="heading-{index}" name="title" value="{escape(row["title"], quote=True)}" required maxlength="2000">'
            f'<select name="level" aria-label="Kopniveau voor kop {index}">{options}</select></li>'
        )
    if rows:
        body = '<h2>Klopt de inhoudsopgave?</h2><ol>' + ''.join(rows) + '</ol>'
    else:
        body = '<p>Deze bron bevat geen koppen. Je kunt het hele document als één sectie controleren.</p>'
    return (
        '<section class="annotation-confirm-contents">'
        '<form method="post" action="/annotations/structure">'
        f'<input type="hidden" name="document" value="{escape(document, quote=True)}">'
        f'<input type="hidden" name="basis" value="{escape(basis, quote=True)}">'
        + body +
        '<button class="btn-primary" type="submit">Bevestig en ga annoteren</button></form></section>'
        '<style>.annotation-confirm-contents{max-width:48rem;margin:1.5rem auto}'
        '.annotation-confirm-contents ol{padding:0;list-style:none;margin:0 0 1.25rem}'
        '.annotation-confirm-contents li{display:grid;grid-template-columns:minmax(0,1fr) auto;'
        'column-gap:.75rem;border-bottom:1px solid var(--line);padding:.5rem 0}'
        '.annotation-confirm-contents li label{grid-column:1/-1;margin:0 0 .25rem;font-size:.875rem}'
        '.annotation-confirm-contents li :is(input,select){width:100%;min-width:0;margin:0}'
        '.annotation-confirm-contents button{min-height:2.75rem}</style>'
    )


def source_document_html(blocks):
    """Read the pinned blocks as one document without changing their anchors."""
    parts = []
    page = None
    page_open = toc_open = toc_row_open = False

    def source_text(block):
        identity = escape(block['block_id'], quote=True)
        return ('<span class="annotation-source-text" data-source-block="' + identity +
                '" id="' + identity + '" tabindex="0" aria-describedby="annotation-keyboard-hint" title="' +
                escape(location_label(block), quote=True) + '">' + escape(block['text']) + '</span>')

    for index, block in enumerate(blocks):
        text = block['text']
        path = block.get('section_path') or []
        in_toc = structure.in_source_contents(path)
        level = structure.heading_level(block, path)
        current_page = next((loc['page'] for loc in block.get('locations') or [] if loc.get('page')), None)
        if in_toc != toc_open:
            if toc_row_open:
                parts.append('</p>')
                toc_row_open = False
            if page_open:
                parts.append('</section>')
                page_open = False
            if toc_open:
                parts.append('</details>')
            if in_toc:
                parts.append('<details class="annotation-toc"><summary>Inhoudsopgave</summary>')
            toc_open = in_toc
            page = None
        if not page_open or page != current_page:
            if toc_row_open:
                parts.append('</p>')
                toc_row_open = False
            if page_open:
                parts.append('</section>')
            page = current_page
            page_label = 'Pagina ' + str(page) if page else 'Brontekst'
            page_id = 'source-page-' + str(page) if page else 'source-page-unknown'
            parts.append('<section class="annotation-page" id="' + page_id + '" aria-label="' +
                         escape(page_label, quote=True) + '"><p class="annotation-page-label">' +
                         escape(page_label) + '</p>')
            page_open = True
        span = source_text(block)
        if in_toc and not block.get('heading'):
            continuation = text.lstrip().startswith('.') or text.strip().isdigit() or (
                text.strip().replace(' ', '').isdigit())
            if not toc_row_open or not continuation:
                if toc_row_open:
                    parts.append('</p>')
                parts.append('<p class="annotation-toc-row">')
                toc_row_open = True
            else:
                parts.append(' ')
            parts.append(span)
        elif level is not None:
            if toc_row_open:
                parts.append('</p>')
                toc_row_open = False
            parts.append(f'<h{level} class="annotation-document-heading">{span}</h{level}>')
        else:
            next_page = next((loc['page'] for loc in blocks[index + 1].get('locations') or []
                              if loc.get('page')), None) if index + 1 < len(blocks) else None
            page_number = bool(page and text.strip() == str(page) and next_page != page)
            style = ('annotation-page-number' if page_number else
                     'annotation-list-item' if text.lstrip().startswith(('·', '•')) else
                     'annotation-paragraph')
            parts.append('<p class="' + style + '">' + span + '</p>')
    if toc_row_open:
        parts.append('</p>')
    if page_open:
        parts.append('</section>')
    if toc_open:
        parts.append('</details>')
    return ''.join(parts)


def gap_id(gap):
    return f"bronrest-{gap['block_id']}-{gap['start']}-{gap['end']}"


def source_work_html(state, esc):
    work = state['source_work']
    ranges = {gap['key']: gap for gap in work['ranges']}
    options = '<option value="">Kies een categorie</option>' + ''.join(
        f'<option value="{role}:{reason}">{esc(SOURCE_LABELS[reason])}</option>'
        for role in ('structure', 'metadata') for reason in SOURCE_ROLES[role])

    def command_fields():
        values = {'document': state['snapshot_id'], 'command_id': str(uuid4()),
                  'expected_generation': str(state['generation']),
                  'expected_objects_revision': state['objects_revision'],
                  'extraction_hash': state['extraction_hash']}
        return ''.join(f'<input type="hidden" name="{key}" value="{esc(value)}">'
                       for key, value in values.items())

    def member(gap, group_id=None):
        target, key = gap_id(gap), esc(gap['key'])
        quote = esc(gap['quote'])
        label = f'<label><input type="checkbox" name="member" form="{group_id}" value="{key}" checked> {quote}</label>' if group_id else f'<q>{quote}</q>'
        return (f'<li id="{esc(target)}" tabindex="-1">{label} '
                f'<a href="#{esc(gap["block_id"])}" data-annotation-gap="{esc(target)}">Ga naar tekst</a>'
                '<form method="post" action="/annotations/source-role">'+command_fields()+
                f'<input type="hidden" name="member" value="{key}">'
                f'<label for="keuze-{esc(target)}">Bronfunctie</label> '
                f'<select id="keuze-{esc(target)}" name="reason" required>{options}</select> '
                '<button class="btn-secondary" type="submit">Vastleggen</button></form></li>')

    sections = []
    for group in work['groups']:
        form_id = 'bronrest-groep-'+group['key']
        category = esc(SOURCE_LABELS[group['proposal'].partition(':')[2]])
        section = esc(' › '.join(group['section']) or 'Zonder sectiekop')
        sections.append(f'<details><summary>{section} · Voorstel: {category} ({len(group["members"])})</summary>'
                        '<ul>'+''.join(member(ranges[key], form_id) for key in group['members'])+'</ul>'
                        f'<form id="{form_id}" method="post" action="/annotations/source-role">'+command_fields()+
                        f'<input type="hidden" name="group" value="{group["key"]}">'
                        f'<input type="hidden" name="reason" value="{group["proposal"]}">'
                        f'<button class="btn-secondary" type="submit">Bevestig geselecteerde tekst als {category.lower()}</button>'
                        '</form></details>')
    unproposed = [gap for gap in ranges.values() if not gap['proposal']]
    if unproposed:
        sections.append(f'<details><summary>Zonder voorstel ({len(unproposed)})</summary><ul>'+
                        ''.join(member(gap) for gap in unproposed)+'</ul></details>')
    if not sections:
        return ''
    return ('<details id="annotation-source-work"><summary>Nog te beoordelen ('+str(len(ranges))+')</summary>'
            '<p>Kies een bronfunctie of ga naar de tekst om haar als uitspraak aan te wijzen.</p>'+
            ''.join(sections)+'</details>')



def source_preparation_form(document, revision, label, esc):
    return ('<form method="post" action="/annotations/source">'
            f'<input type="hidden" name="document" value="{esc(document)}">'
            f'<input type="hidden" name="command_id" value="{uuid4().hex}">'
            f'<input type="hidden" name="expected_revision" value="{esc(revision)}">'
            f'<button class="btn-primary" type="submit">{esc(label)}</button></form>')

def install(app, console, require, page, nav, esc, *, dispatcher):
    def editor_state(actor, document, *, include_source_work=False):
        # Build state is read before and after the overview. A build read as running keeps the
        # editor polling; a build that changed in between means the overview may be older or
        # newer than the state shown, so the whole read is repeated.
        from src.vorming.human_annotation_build_v1 import latest_build

        def build_state():
            with console.workflow_document_store._connect() as con:
                con.read_only = True
                return latest_build(con, document), document_check.read(con, document)

        for _attempt in range(3):
            before = build_state()
            active, current_round = before
            new_flow = current_round is not None or (document_check.enabled() and active is None)
            view = domain.overview(console, actor_id=actor['account_id'], snapshot_id=document,
                                   include_source_work=include_source_work and not new_flow,
                                   include_coverage=include_source_work and new_flow)
            if build_state() == before:
                view['current_build'] = active
                view['document_round'] = current_round
                view['document_check_flow'] = new_flow
                if new_flow and include_source_work:
                    view['source_work'] = {'groups': [], 'ranges': []}
                for entry in view.get('entries', ()):
                    finding = domain.historical_finding(entry)
                    if finding:
                        entry['historical_finding'] = finding
                return view
        domain.fail('annotation_overview_stale')

    def confirmed_contents(state, document):
        definition = state[structure.KEY]
        coverage = state.get(section_coverage.KEY)
        if state.get('document_check_flow') and (state.get('document_round') or {}).get('phase') != 'checking':
            coverage = None
        editable = coverage is not None and not console.snapshot_is_published(document)
        active = state.get('current_build')
        if editable and state.get('document_check_flow') and active:
            from src.review.knowledge_route_v1 import build_is_current
            editable = active['state'] != 'running' and not (
                active['state'] == 'succeeded' and build_is_current(state['entries'], state['object_bindings']))
        entries = definition['entries']
        if not entries and state.get('document_check_flow') and state['blocks']:
            entries = [{'block_id': state['blocks'][0]['block_id'], 'title': 'Hele document', 'level': 1}]
        return source_contents_html(entries, coverage=coverage, document=document, editable=editable)

    def round_form(state, document, phase, label):
        fields = {'document': document, 'phase': phase, 'expected_generation': str(state['generation']),
                  'expected_round': str((state.get('document_round') or {}).get('revision', 0))}
        hidden = ''.join(f'<input type="hidden" name="{key}" value="{esc(value)}">' for key, value in fields.items())
        style = 'btn-primary' if phase == 'checking' else 'btn-secondary'
        return ('<form method="post" action="/annotations/round" data-annotation-round>'
                + hidden + f'<button type="submit" class="{style}">{label}</button></form>')

    def document_check_panel(state, actor, document):
        if not state.get('document_check_flow'):
            return ''
        if console.snapshot_is_published(document):
            return ''
        if (state.get('document_round') or {}).get('phase') != 'checking':
            return round_form(state, document, 'checking', 'Ik ben klaar met dit document')
        from src.vorming import human_annotation_build_v1 as build
        checked = build.overview(console, actor_id=actor['account_id'], snapshot_id=document)
        if (checked.get('document_round') or {}).get('phase') != 'checking':
            return ''
        findings = checked['inspection']['findings']
        body = '<section class="annotation-document-check" aria-labelledby="annotation-document-check-title">'
        body += '<h2 id="annotation-document-check-title">Documentcontrole</h2>'
        if findings:
            body += '<ul>'
            for finding in findings:
                message = FINDINGS.get(finding['code'], 'Controleer de opgeslagen annotatie en het bronbewijs.')
                action = ''
                if finding.get('section'):
                    action = f' <a href="#{quote(finding["section"], safe="")}">{esc(finding["title"])}</a>'
                elif finding.get('annotation_id'):
                    url = '/annotations?' + urlencode({'document': document, 'annotation': finding['annotation_id']})
                    action = f' <a href="{esc(url)}">Open annotatie</a>'
                body += f'<li>{esc(message)}{action}</li>'
            body += '</ul>'
        elif not checked['current_build']:
            body += '<p>De opgeslagen annotaties zijn klaar voor de bouw.</p>'
        signals = [entry for entry in checked['inspection']['entries'] if entry.get('signals')]
        if signals:
            body += '<details><summary>Signalen voor Review</summary><ul>'
            for entry in signals:
                url = '/annotations?' + urlencode({'document': document, 'annotation': entry['annotation_id']})
                messages = [SIGNALS.get(code, 'Een onderdeel is niet vastgesteld.') for code in entry['signals']]
                body += f'<li>{esc(" ".join(messages))} <a href="{esc(url)}">Open annotatie</a></li>'
            body += '</ul></details>'
        active = checked['current_build']
        if active:
            url = '/annotations/build?' + urlencode({'document': document, 'attempt': active['attempt_id']})
            body += f'<p><a href="{esc(url)}">Opgeslagen bouwopdracht bekijken</a></p>'
        if checked['can_finalize']:
            fields = {'document': document, 'command_id': str(uuid4()), 'overview_hash': checked['overview_hash'],
                      'expected_generation': str(checked['generation']), 'expected_revision': checked['objects_revision']}
            hidden = ''.join(f'<input type="hidden" name="{key}" value="{esc(value)}">' for key, value in fields.items())
            body += ('<form method="post" action="/annotations/finalize" data-confirmed-document-build>'
                     + hidden + '<button class="btn-primary" type="submit">Afronden en bouwen</button></form>')
        if not active or active['state'] != 'running':
            body += round_form(checked, document, 'annotating', 'Verder annoteren')
        return body + '</section>'

    @app.get('/annotations', response_class=HTMLResponse)
    def editor(request: Request, document: str = '', overview: bool = False):
        actor = require(request)
        envelope = console._envelope(document)
        domain.authorize(console, actor['account_id'], envelope)
        if not domain.owns_source(console, document):
            from src.vorming import human_annotation_source_v1 as source
            progress = source.progress(console, actor_id=actor['account_id'], snapshot_id=document)
            if progress and progress['ready']:
                return RedirectResponse('/annotations?'+urlencode({'document':document}), status_code=303)
            if progress:
                running = progress['state'] == 'running'
                phases = {'annotation_source_pending':'Wachten op beschikbare verwerkingsruimte.',
                          'annotation_source_extract':'De bron wordt uitgelezen. Bij PDF controleren we ook de pagina-indeling en tabellen.',
                          'annotation_source_check':'De brontekst en selectieposities worden gecontroleerd.'}
                elapsed = progress['elapsed_seconds']
                duration = str(elapsed//60)+' min '+str(elapsed%60)+' sec'
                body = nav(actor,'selection')+'<section class="room"><h1>'+('Bron wordt voorbereid' if running else 'Bronvoorbereiding gestopt')+'</h1><h2>'+esc(envelope['title'])+'</h2>'
                if running:
                    body += '<p role="status">'+esc(phases.get(progress['phase'],'De bron wordt voorbereid.'))+'</p>'
                    body += '<p>Verstreken: '+duration+'.</p><p>Bij een grote PDF kan dit enkele minuten duren. Je kunt deze pagina verlaten en later terugkomen; de voorbereiding loopt door.</p>'
                    body += '<p>Deze pagina vernieuwt elke 5 seconden. Zodra de bron gereed is, verschijnt het annotatiedocument.</p><meta http-equiv="refresh" content="5">'
                else:
                    reason = progress.get('retry_reason') or progress.get('error_code')
                    message = {
                        'processing_attempt_expired': 'De tijdslimiet voor bronvoorbereiding is bereikt.',
                        'processing_timeout': 'Het uitlezen van de bron duurde te lang.',
                        'docling_timeout': 'Het uitlezen van de PDF duurde te lang.',
                        'processing_attempt_limit_reached': 'Het maximum aantal pogingen is bereikt.',
                        'processing_retry_cooldown': 'Wacht tot opnieuw proberen mogelijk is.',
                        'processing_admission_closed': 'Nieuwe voorbereidingen zijn tijdelijk gepauzeerd.',
                        'source_extraction_integrity_failed': 'Metis kon de uitgelezen bron niet verifiëren.',
                    }.get(reason, 'Metis kon de voorbereiding van de bron niet voltooien.')
                    body += '<p class="banner warn" role="alert">'+esc(message)+'</p>'
                    if progress.get('retry_allowed'):
                        body += source_preparation_form(document, console.objects_revision(document),
                                                        'Bronvoorbereiding opnieuw proberen', esc)
                body += '<p><a href="/tree">Terug naar Documenten</a></p></section>'
                return HTMLResponse(page(body,title='Bron voorbereiden'),headers={'Cache-Control':'no-store'})
            notice = '<div class="banner ok" role="status">Document veilig ontvangen. Open de bron om te annoteren.</div>' if request.query_params.get('received') == 'yes' else ''
            return HTMLResponse(page(nav(actor,'selection')+'<section class="room"><h1>Bron aanwijzen</h1><h2>'+esc(envelope['title'])+'</h2>'
                +notice+
                '<p>Open de vastgelegde bron om uitspraken, voorwaarden, uitzonderingen en onderbouwing aan te wijzen. Je kunt concepten opslaan en later hervatten.</p>'
                '<p>Annoteren geeft geen goedkeuring. De bij ontvangst gekozen beoordeling blijft gelden.</p>'
                +source_preparation_form(document, console.objects_revision(document), 'Bron openen voor annotatie', esc)
                +'</section>',title='Bron aanwijzen'),headers={'Cache-Control':'no-store'})
        from src.vorming import human_annotation_build_v1 as build
        state = editor_state(actor, document, include_source_work=True)
        overview = overview and not state['document_check_flow']
        if overview:
            state = build.overview(console, actor_id=actor['account_id'], snapshot_id=document)
        checking_document = (state.get('document_round') or {}).get('phase') == 'checking'
        from src.vorming.source_bound_fields_v3 import FIELDS, TYPE_FIELDS, CONTEXT_FIELDS
        from src.vorming.human_annotation_contract_v1 import CONTEXT_BINDING_FIELDS, ROLE_MAP
        from src.vorming.human_annotation_v1 import TYPE_CORE_FIELDS
        state['field_contract']={'fields':list(FIELDS),'type_core_fields':TYPE_CORE_FIELDS,
            'type_fields':TYPE_FIELDS,
            'context_bindings':{role:field for role,field in CONTEXT_BINDING_FIELDS.items() if ROLE_MAP[role] in CONTEXT_FIELDS[field]},
            'source_roles':{role:[{'value':reason,'label':SOURCE_LABELS[reason]} for reason in reasons] for role,reasons in SOURCE_ROLES.items()}}
        version = esc(state['source_identity']['version'])
        back = '/annotations?' + urlencode({'document':document})
        intro = '<h1>'+('Documentoverzicht' if overview else 'Bron aanwijzen')+'</h1><h2>'+esc(state['title'])+'</h2><p data-working-revision="'+esc(state['working_revision_id'])+'">Bronversie '+version+'</p>'
        intro += '<p><a target="_blank" rel="noopener" href="/annotations/original?'+esc(urlencode({'document':document}))+'">Open het vastgelegde origineel</a></p>'
        # #1067: where the work is and what happens next, the same line as on the review card.
        from src.review.knowledge_route_v1 import annotation_route, build_is_current
        from src.review.four_eyes_v1 import document_requires_second_review
        second_review = document_requires_second_review(envelope, state['entries'])
        built = (state.get('current_build') or {}).get('state', '') if overview or checking_document else ''
        if built == 'succeeded' and not build_is_current(state['entries'], state.get('object_bindings') or {}):
            built = ''
        intro += annotation_route(overview=overview or checking_document, second_review=second_review,
                                  finalized=built if built in {'running', 'succeeded'} else '',
                                  document_check_flow=state['document_check_flow'])
        if overview:
            items = []
            for entry in state['entries']:
                historical = domain.historical_finding(entry)
                if entry['status']=='withdrawn' and not historical:
                    continue
                spans = ''.join('<li><strong>'+escape('Brontekst' if entry.get('disposition') else LABELS[a['role']])+ (' — verklaart' if a['evidence_function']=='explains' else ' — onderbouwt' if a['evidence_function']=='supported_by' else '')+'</strong>'+
                    ': '+escape(a['quote'])+' <a href="'+escape(back+'#'+a['block_id'],quote=True)+'">Open in bron</a></li>' for a in entry['ranges'])
                missing = 'Selectie nog niet gereed.' if entry['status']!='ready' else ''
                if entry.get('pending_range'):
                    missing += ' Er staat nog een niet-gekoppelde aanwijzing klaar: '+entry['pending_range']['quote']
                fields = []
                by_id = {b['block_id']:b for b in state['blocks']}
                for field,evidence in (entry.get('field_evidence') or {}).items():
                    if field not in FIELD_LABELS or not evidence.get('span'):
                        continue
                    span = evidence['span']
                    literal = by_id[span['block_id']]['text'][span['start']:span['end']]
                    fields.append('<li>'+escape(FIELD_LABELS[field])+': '+escape(literal)+'</li>')
                heading=('Brongebruik: '+SOURCE_LABELS.get(entry['disposition']['reason'],'Functie nog kiezen')) if entry.get('disposition') else TYPES.get(entry['object_type'],'Type nog kiezen')
                if historical:
                    details = ['Eerdere annotatieversie' + (' (teruggenomen)' if entry['status']=='withdrawn' else '')]
                    historical_ranges = [*entry['ranges'], *([entry['pending_range']] if entry.get('pending_range') else [])]
                    for anchor in historical_ranges:
                        if anchor.get('required_for_meaning') is True:
                            details.append('Als essentieel aangemerkt: '+anchor['quote'])
                    for link in entry.get('required_links', []):
                        _, role, block_id, start, end = json.loads(link['relationship_id'].removeprefix('link-v1:'))
                        block = by_id.get(block_id)
                        passage = block['text'][start:end] if block and end <= len(block['text']) else ''
                        label = LABELS[role] + (' — '+passage if passage else ' — oorspronkelijke passage niet beschikbaar')
                        if link['required_for_meaning']:
                            details.append('Eerder als essentieel vastgelegd: '+label)
                        else:
                            details.extend(['Teruggenomen verband: '+label, 'Reden voor terugname: '+link['withdrawal_reason']])
                    action = ''.join('<p>'+esc(detail)+'</p>' for detail in details)
                    if historical == domain.HISTORICAL_NEUTRAL:
                        action += '<a href="'+esc(back+'&annotation='+entry['annotation_id'])+'">Selectie controleren en opslaan</a>'
                    article_id = ' id="historisch-'+esc(entry['annotation_id'])+'"'
                else:
                    action = '<a href="'+escape(back+'&annotation='+entry['annotation_id'],quote=True)+'">Deze annotatie aanpassen</a>'
                    article_id = ''
                items.append('<article class="object"'+article_id+'><h3>'+escape(heading)+'</h3><p>'+escape(missing)+'</p><ul>'+spans+'</ul>'+
                    ('<p>Aangewezen betekenisvelden</p><ul>'+''.join(fields)+'</ul>' if fields else '')+
                    ('<p>Onderbouwing: expliciet niet van toepassing.</p>' if entry['evidence_not_applicable'] else '')+action+'</article>')
            inspection = state['inspection']
            historical_coverage = any(domain.historical_finding(entry) for entry in state['entries'])
            ready = sum(entry['status'] == 'ready' and not entry.get('disposition')
                        and not domain.historical_finding(entry) for entry in state['entries'])
            rest = len(inspection['source_assessments'])
            opened = len(inspection['unaccounted_ranges'])
            body = intro + f'<p>Gereedstaande kennisannotaties: {ready} · Verantwoorde restbereiken: {rest}'
            if not historical_coverage:
                body += f' · Open bronbereiken: {opened}'
            body += '</p>' + (''.join(items) or '<p>Er zijn nog geen selecties opgeslagen.</p>')
            if inspection['findings']:
                body += '<section aria-labelledby="annotation-findings"><h2 id="annotation-findings">Nog controleren vóór afsluiten</h2>'
                if any(f['code'] in {domain.HISTORICAL_NEUTRAL, domain.HISTORICAL_DECISION} for f in inspection['findings']):
                    body += '<p>Na omzetting van de eerdere annotaties kan Metis de dekking van het hele document controleren.</p>'
                body += '<ul>'
                for finding in inspection['findings']:
                    target = back + ('&annotation='+finding['annotation_id'] if finding['annotation_id'] else '')
                    body += '<li>'+esc(FINDINGS.get(finding['code'], 'Controleer de aangewezen betekenisvelden en hun bronbereiken.'))
                    if finding['code'] in {domain.HISTORICAL_NEUTRAL, domain.HISTORICAL_DECISION}:
                        body += ' <a href="#historisch-'+esc(finding['annotation_id'])+'">Bekijk de eerdere annotatie</a>'
                    else:
                        body += ' <a href="'+esc(target)+'">Aanpassen in de bron</a>'
                    for related in finding.get('related_annotation_ids', []):
                        body += ' · <a href="'+esc(back+'&annotation='+related)+'">Andere annotatie met dezelfde kern</a>'
                    body += '</li>'
                body += '</ul></section>'
            noted = [entry for entry in inspection['entries'] if entry.get('signals')]
            if noted:
                # #1060: information for worker and reviewer; never a reason to refuse sealing.
                body += '<section aria-labelledby="annotation-signals"><h2 id="annotation-signals">Niet vastgesteld door Metis</h2><p>Dit houdt afsluiten niet tegen.</p><ul>'
                for entry in noted:
                    # One point per line, so each can be read and checked on its own.
                    body += '<li><ul>'+''.join('<li>'+esc(text)+'</li>' for text in
                        dict.fromkeys(SIGNALS.get(code, 'Een onderdeel is niet vastgesteld.') for code in entry['signals']))
                    body += '</ul><a href="'+esc(back+'&annotation='+entry['annotation_id'])+'">Annotatie bekijken</a></li>'
                body += '</ul></section>'
            if inspection['unaccounted_ranges']:
                body += ('<section aria-labelledby="annotation-gaps"><h2 id="annotation-gaps">Nog niet verantwoord bronmateriaal</h2><ul>')
                for gap in inspection['unaccounted_ranges']:
                    body += '<li><q>'+esc(gap['quote'])+'</q> <a href="'+esc(back+'#'+gap_id(gap))+'">Beoordelen in document</a></li>'
                body += '</ul></section>'
            current = state['current_build']
            if current:
                body += '<p><a href="/annotations/build?'+esc(urlencode({'document':document,'attempt':current['attempt_id']}))+'">Opgeslagen bouwopdracht bekijken</a></p>'
            if state['can_finalize']:
                hidden = {'document':document,'command_id':str(uuid4()),'overview_hash':state['overview_hash'],
                          'expected_generation':str(state['generation']),'expected_revision':state['objects_revision']}
                body += '<p>Na afsluiten bouwen we de kennisobjecten uit precies deze opgeslagen bronkeuzes. Dit geeft geen goedkeuring of publicatierecht; de bij ontvangst gekozen beoordeling blijft gelden.</p>'
                body += '<form method="post" action="/annotations/finalize">'+''.join(
                    '<input type="hidden" name="'+key+'" value="'+esc(value)+'">' for key,value in hidden.items())
                body += '<button id="annotation-finalize" class="btn-primary" type="submit">Ik ben klaar met dit document</button></form>'
            else:
                if current and current['state'] == 'running':
                    body += '<p>Het document is afgesloten en de opbouw loopt. Bekijk de opgeslagen bouwopdracht hierboven.</p>'
                elif current and current['state'] == 'succeeded':
                    body += '<p>Het document is afgesloten en opgebouwd. Open de bouwopdracht voor de kennisobjecten en de toepasselijke beoordeling.</p>'
                else:
                    body += '<p>Afsluiten is pas mogelijk als alle annotaties en de bronafhandeling gereed zijn.'+(' De opgeslagen bouwopdracht blijft hierboven bereikbaar.' if current else '')+'</p>'
            body += '<p><a class="btn-secondary" href="'+escape(back,quote=True)+'">Verder aanwijzen</a></p>'
            return HTMLResponse(page(nav(actor,'selection')+'<section class="room"><div style="max-width:72ch">'+body+'</div></section><style>.room article.object{margin-block:0 1.5rem}.room article.object>a{display:inline-block;margin-top:.25rem}.room section[aria-labelledby]{margin-top:2rem}#annotation-signals+p+ul>li{margin-block:.5rem 1rem}#annotation-signals+p+ul ul{padding-left:1.1rem;margin:0 0 .25rem}</style>',title='Documentoverzicht'),headers={'Cache-Control':'no-store'})
        proposed_contents = structure.proposed(state['blocks'])
        confirmed = state.get(structure.KEY)
        needs_confirmation = False
        if structure.enabled() and (proposed_contents or state['document_check_flow']) and confirmed is None:
            with console.workflow_document_store._connect() as con:
                needs_confirmation = not structure.has_seal(con, document)
        if needs_confirmation:
            original = '/annotations/original?' + urlencode({'document': document})
            body = ('<h1>Inhoudsopgave bevestigen</h1><h2>' + esc(state['title']) + '</h2>'
                    f'<p><a target="_blank" rel="noopener" href="{esc(original)}">Open het vastgelegde origineel</a></p>'
                    + confirm_contents_html(document, state['extraction_hash'], proposed_contents))
            return HTMLResponse(page(nav(actor, 'selection') + '<section class="room">' + body + '</section>',
                                     title='Inhoudsopgave bevestigen'), headers={'Cache-Control': 'no-store'})
        contents = (confirmed_contents(state, document) if confirmed is not None else
                    source_contents_html(proposed_contents))
        blocks = source_document_html(state['blocks'])
        pages = list(dict.fromkeys(loc['page'] for block in state['blocks']
            for loc in block.get('locations') or [] if loc.get('page')))
        page_options = ''.join('<option value="source-page-'+str(p)+'">Pagina '+str(p)+'</option>' for p in pages)
        from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES
        # #1060 slice 5: the card offers the kinds of statement; Metis proposes one, the worker may correct it.
        state['kinds'] = [{'value':key,'label':label} for key,label in TYPES.items() if key in CLOSED_OBJECT_TYPES]
        data = json.dumps(state,ensure_ascii=False).replace('<','\\u003c')
        body = '<header class="annotation-workspace-intro">' + intro + '''</header><details class="annotation-instruction"><summary>Hulp bij annoteren</summary><p>Wijs een eigen uitspraak aan: iets wat de bron stelt, definieert, verklaart of aanbeveelt. Selecteer tekst in de bron en kies naast de selectie welke rol de tekst in het kennisobject heeft.</p></details>
<nav class="annotation-mobile-nav" aria-label="Wisselen tussen bron en annotatie"><a id="annotation-to-controls" href="#annotation-controls">Naar huidige annotatie</a><a id="annotation-to-source" href="#'''+esc(state['blocks'][0]['block_id'] if state['blocks'] else '')+'''">Terug naar bron</a></nav>
<p id="annotation-source-work-status" role="status"></p>
<p id="annotation-coverage-status" role="status"></p>
<div id="annotation-document-check-host">'''+document_check_panel(state, actor, document)+'''</div>
<div class="annotation-workplace">'''+contents+'''<div class="annotation-document" aria-label="Document in leesvolgorde"><div class="annotation-document-tools"><strong>Documenttekst</strong><span id="annotation-keyboard-hint" class="sr-only">Selecteer rechtstreeks in de bron. Met toetsenbord: focus een passage en gebruik Shift met de pijltoetsen naar links of rechts. Home en End gaan naar begin en einde van de passage.</span>'''+('<label for="annotation-page-nav">Ga naar pagina</label><select id="annotation-page-nav">'+page_options+'</select>' if pages else '')+'''</div><div id="annotation-source-work-host">'''+('' if state.get('document_check_flow') else source_work_html(state, esc))+'''</div>'''+blocks+'''</div>
<aside id="annotation-controls" tabindex="-1" aria-label="Huidige annotatie"><h2>Kennisobject voorbereiden</h2>
<p id="annotation-initializing" role="status">De annotatiewerkplek wordt klaargezet.</p>
<section id="annotation-offer" aria-label="Voorstel van Metis" hidden>
<p id="annotation-offer-message" role="status"></p><dl id="annotation-offer-ranges"></dl>
<button type="button" class="btn-primary" id="annotation-take-offer" hidden>Overnemen</button>
<button type="button" class="btn-secondary" id="annotation-skip-offer" hidden>Zelf selecteren</button></section>
<fieldset id="annotation-editor-inputs" aria-label="Annotatie bewerken" disabled>
<p id="annotation-status" role="status" aria-live="polite"></p>
<section id="annotation-simple" aria-labelledby="annotation-simple-heading"><h3 id="annotation-simple-heading" tabindex="-1">Selecteer de uitspraak in de bron</h3>
<dl id="annotation-simple-rows"></dl>
<p id="annotation-simple-status" role="status" aria-live="polite"></p><ul id="annotation-simple-notes"></ul></section>
<p id="annotation-suggestion-note" role="status" aria-live="polite"></p>
<p id="annotation-conflict" hidden><a id="annotation-conflict-link" target="_blank" rel="noopener">Bestaande annotatie openen in een nieuw venster</a></p>
<section id="annotation-save-conflict" hidden><h3>Je werk en de opgeslagen versie verschillen</h3><p>Je aanwijzingen blijven hier staan. Vergelijk ze met de opgeslagen versie voordat je kiest wat je behoudt.</p><details><summary>Mijn huidige werk</summary><pre id="annotation-local-work"></pre></details><a id="annotation-server-work" target="_blank" rel="noopener">Bekijk opgeslagen versie in een nieuw venster</a></section>
<button class="btn-secondary" type="button" id="annotation-save-current-format" hidden>Gecontroleerde selectie opnieuw opslaan</button>
<button class="btn-secondary" type="button" id="annotation-retry" hidden>Opslaan opnieuw proberen</button>
<div class="annotation-task-actions"><button class="btn-primary" type="button" id="annotation-ready" hidden disabled>Opslaan en naar volgend kennisobject</button><button class="btn-secondary" type="button" id="annotation-finish" hidden>Opslaan en bronselectie beëindigen</button><button class="btn-primary" type="button" id="annotation-rebuild" hidden>Kennisobject opnieuw bouwen</button></div>
</fieldset>
<section id="annotation-saved" aria-labelledby="annotation-saved-heading">
<h2 id="annotation-saved-heading">Opgeslagen annotaties</h2>
<p id="annotation-saved-summary" role="status" aria-live="polite">De opgeslagen annotaties worden geladen.</p>
<ol id="annotation-saved-list"></ol>
<p id="annotation-saved-notice" role="status" hidden></p>
<div class="annotation-saved-actions"><a id="annotation-saved-build" hidden>Opbouw bekijken</a>
<a id="annotation-saved-overview" class="btn-secondary" href="/annotations?'''+esc(urlencode({'document':document,'overview':'true'}))+'''" hidden>Bronselectie beëindigen en document controleren</a></div>
</section></aside></div>
<script type="application/json" id="annotation-data">'''+data+'''</script><script type="module" src="/annotations/editor.js"></script>'''
        css = '''<style>
.#annotation-source-work{margin:0 0 1rem;border-block-end:1px solid var(--line);padding:.5rem 0}
#annotation-source-work summary{cursor:pointer;padding:.5rem 0;font-weight:600}
#annotation-source-work details{padding-inline-start:.75rem}
#annotation-source-work ul{padding-inline-start:1.25rem}
#annotation-source-work li{padding:.4rem 0;overflow-wrap:anywhere}
#annotation-source-work li:focus{outline:2px solid var(--paars)}
#annotation-source-work form{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;margin-top:.5rem}
#annotation-source-work select{width:auto;max-width:100%}
.annotation-source-text mark[data-source-rest]{background:var(--surface-soft);color:inherit;box-shadow:inset 0 -1px var(--muted)}
.annotation-source-text mark[data-source-rest-focus]{outline:2px solid var(--paars);outline-offset:1px}
.annotation-source-rest-label{display:inline-block;margin-inline-start:.5rem;font-size:.8rem}
#annotation-source-work-status:empty{display:none}
.annotation-workspace-intro{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.25rem 1.5rem;align-items:center}
.annotation-workspace-intro h1{font-size:1.5rem;margin:0;grid-column:1;grid-row:1}
.annotation-workspace-intro h2{color:var(--text);font-size:1.125rem;margin:0;grid-column:1;grid-row:2;overflow-wrap:anywhere}
.annotation-workspace-intro>p{margin:0;color:var(--muted);font-size:.875rem;grid-column:2}
.annotation-workspace-intro>p[data-working-revision]{grid-row:1}
.annotation-workspace-intro>p:has(a){grid-row:2}
.annotation-workspace-intro .ko-route{grid-column:1/-1;margin:.75rem 0 0}
.annotation-workspace-intro .ko-route-next{font-size:.875rem;color:var(--muted)}
.annotation-instruction{margin:0 0 .75rem;color:var(--muted);font-size:.875rem;line-height:1.6}
.annotation-instruction summary{min-height:2.75rem;align-content:center;cursor:pointer;width:fit-content}
.annotation-instruction summary:focus-visible{outline:2px solid var(--paars);outline-offset:2px}
.annotation-instruction p{max-width:75ch;margin:.25rem 0 1rem}
@media(max-width:800px){.annotation-workspace-intro{display:block}.annotation-workspace-intro h2{margin:.5rem 0}.annotation-workspace-intro>p{display:inline-block;margin:0 .75rem .25rem 0}}
#annotation-saved{margin:1.25rem -1.25rem -1.25rem;padding:1rem 1.25rem 1.25rem;background:var(--surface-soft);border-top:1px solid var(--line);border-radius:0 0 12px 12px}
#annotation-controls #annotation-saved-heading{font-size:1rem;color:var(--text);margin:0}
#annotation-controls #annotation-saved-summary{margin:.25rem 0 .5rem;font-size:.8125rem;color:var(--muted)}
#annotation-saved-list{list-style:none;padding:0;margin:0;max-height:18rem;overflow:auto;scroll-padding:.25rem}
#annotation-saved-list li{margin:0;padding:.25rem 0 .75rem;border-bottom:1px solid var(--line);overflow-wrap:anywhere}
#annotation-saved-list li:last-child{border-bottom:0}
#annotation-saved-list a{display:block;min-height:2.75rem;align-content:center;line-height:1.45;font-size:.9375rem;text-decoration:none;text-underline-offset:.2em}
#annotation-saved-list a:hover{text-decoration:underline}
#annotation-saved-list a[aria-current]{font-weight:700;text-decoration:underline}
#annotation-saved-list a:focus-visible,#annotation-saved-overview:focus-visible{outline:2px solid var(--paars);outline-offset:2px}
#annotation-saved-list a[aria-disabled=true],#annotation-saved-overview[aria-disabled=true]{opacity:.65}
.annotation-saved-status,.annotation-saved-detail{display:block;font-size:.8125rem;line-height:1.5}
.annotation-saved-status{font-weight:600}.annotation-saved-detail{color:var(--muted)}
.annotation-saved-actions{display:flex;flex-direction:column;align-items:stretch;gap:.5rem;margin-top:.75rem}
#annotation-saved-overview,#annotation-saved-build{min-height:2.75rem;align-content:center;font-size:.875rem}
#annotation-saved-overview{display:block;text-align:left;padding:.625rem .75rem;line-height:1.5}
#annotation-controls:has(#annotation-saved-overview:not([hidden])) #annotation-finish{display:none}
#annotation-controls:has(#annotation-saved-overview:not([hidden])) .annotation-task-actions:not(:has(.btn-primary:not([hidden]))){display:none}
#annotation-controls>h2:first-child{font-size:1.125rem;color:var(--text);margin-bottom:.75rem}
#annotation-controls #annotation-simple-heading{margin:1rem 0 .5rem;font-size:1rem}
#annotation-status:empty{display:none}
#annotation-document-check-host:not(:empty){margin-block:1rem}
.annotation-document-check{border-block:1px solid var(--line);padding-block:.75rem}
.annotation-document-check h2{margin:0 0 .5rem}
.annotation-document-check form{display:inline-block;margin:.25rem .5rem .25rem 0}
.annotation-workplace{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(19rem,1fr);gap:1.5rem;align-items:start}
.annotation-contents{min-width:0;border:1px solid var(--line);border-radius:12px;background:var(--surface-soft);padding:.75rem}
.annotation-contents h2{font-size:1rem;color:var(--text);margin:0 0 .25rem}
.annotation-contents ul{list-style:none;margin:0;padding:.25rem;max-height:8.25rem;overflow:auto;scroll-padding:.25rem}
.annotation-workplace .annotation-contents li{margin:0;padding-inline-start:calc(var(--contents-indent) * .65rem)}
.annotation-contents a{display:block;align-content:center;min-height:2.75rem;padding:.25rem .375rem;line-height:1.35;text-decoration:none;color:var(--text)}
.annotation-contents a:hover{text-decoration:underline;text-underline-offset:.2em}
.annotation-contents a:focus-visible{outline:2px solid var(--paars);outline-offset:1px}
#annotation-coverage-status:empty{display:none}
.annotation-contents [data-coverage-form]{margin:.15rem 0 .5rem}
.annotation-contents [data-coverage-form] button{display:block;min-height:2.75rem;width:100%;padding:.25rem .375rem;
  background:var(--wit);border:1px solid var(--line);border-radius:6px;cursor:pointer;
  text-align:start;color:var(--paars);font:inherit;font-size:.8125rem;white-space:normal}
.annotation-contents [data-coverage-form] button:hover{background:var(--water-soft)}
.annotation-contents [data-coverage-form] button:focus-visible{outline:2px solid var(--paars);outline-offset:1px}
.annotation-contents li:has(.annotation-section-status){padding-block:.25rem;border-bottom:1px solid var(--line)}
.annotation-section-status{display:block;padding-inline:.375rem;color:var(--muted);font-size:.8125rem}
.annotation-section-status[data-section-status=checked]{color:var(--text);font-weight:600}

@media(min-width:1081px){
  .annotation-workplace:has(.annotation-contents){grid-template-columns:minmax(10rem, .65fr) minmax(0, 1.8fr) minmax(19rem, 1fr)}
  .annotation-contents{position:sticky;top:1rem}
  .annotation-contents ul{max-height:calc(100dvh - 5rem)}
}
@media(max-width:1080px){.annotation-contents{grid-column:1/-1}}
#annotation-editor-inputs{min-width:0;margin:0;padding:0;border:0}
.annotation-document{position:relative;min-width:0;background:var(--wit);border:1px solid var(--line);border-radius:12px;max-height:calc(100vh - 8rem);overflow:auto}
.annotation-document-tools{position:sticky;top:0;z-index:1;display:flex;align-items:center;gap:.75rem;padding:.75rem 1.5rem;background:var(--wit);border-bottom:1px solid var(--line)}
.annotation-document-tools label{margin:0 0 0 auto!important}.annotation-document-tools select{width:auto;max-width:10rem}
.annotation-page{max-width:76ch;margin:0 auto;padding:2rem 2.25rem;border-bottom:1px solid var(--line)}
.annotation-page-label,.annotation-page-number{font-size:.84rem;color:var(--muted)}.annotation-page-label{margin:0 0 1.75rem}.annotation-page-number{text-align:right;margin:1rem 0 0}
.annotation-document-heading{color:var(--paars);line-height:1.35;margin:2rem 0 .65rem}.annotation-page>.annotation-document-heading:first-of-type{margin-top:0}
.annotation-paragraph,.annotation-list-item{font-size:1rem;line-height:1.75;margin:.25rem 0 1.15rem;overflow-wrap:anywhere}.annotation-list-item{padding-left:1.25rem;text-indent:-1rem;margin-bottom:.45rem}
.annotation-source-text{border-radius:2px;cursor:text;scroll-margin-top:5rem}.annotation-source-text:focus-visible{outline:2px solid var(--paars);outline-offset:3px}.annotation-source-text mark{color:inherit;background:var(--water-soft);border-radius:2px}.annotation-source-text mark[data-current][data-role=core]{background:color-mix(in srgb,var(--paars) 25%,var(--wit))}.annotation-source-text mark[data-current]:not([data-role]){background:var(--surface-soft)}.annotation-source-text mark[data-annotation]{cursor:pointer}.annotation-source-text mark[data-proposal]{background:none;outline:2px dashed var(--paars);outline-offset:1px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
/* #1123: the open object's passages show their role; the card's row names carry the same mark. */
.annotation-source-text mark[data-current][data-role=belongs]{background:color-mix(in srgb,var(--water) 30%,var(--wit));text-decoration:underline dotted 2px var(--water);text-underline-offset:3px}.annotation-source-text mark[data-current][data-role=evidence]{background:none;text-decoration:underline solid 3px var(--paars);text-underline-offset:3px}
#annotation-simple-rows dt:is([data-row=core],[data-related],[data-row=evidence]) .annotation-row-name::before{content:'';display:inline-block;width:1.1em;height:.75em;margin-right:.4em;border-radius:2px;vertical-align:baseline}#annotation-simple-rows dt[data-row=core] .annotation-row-name::before{background:color-mix(in srgb,var(--paars) 25%,var(--wit))}#annotation-simple-rows dt[data-related] .annotation-row-name::before{background:color-mix(in srgb,var(--water) 30%,var(--wit));border-bottom:2px dotted var(--water)}#annotation-simple-rows dt[data-row=evidence] .annotation-row-name::before{background:none;border-bottom:3px solid var(--paars);border-radius:0}
.annotation-toc{padding:1rem 1.5rem;border-bottom:1px solid var(--line)}.annotation-toc>summary{font-weight:700;color:var(--paars);cursor:pointer}.annotation-toc .annotation-page{padding-inline:.75rem}.annotation-toc-row{line-height:1.6;margin:.35rem 0;overflow-wrap:anywhere}
.annotation-workplace aside{align-self:start;position:sticky;top:1rem;max-height:90vh;overflow:auto;min-width:0;background:var(--wit);border:1px solid var(--line);border-radius:12px;padding:1.25rem}.annotation-workplace aside h2{color:var(--paars)}.annotation-workplace label{display:block;margin-top:1rem}.annotation-workplace select{max-width:100%}.annotation-workplace .btn-secondary{min-height:2.75rem;white-space:normal}.annotation-workplace li{overflow-wrap:anywhere;margin-block:1rem}.annotation-workplace .actions{display:flex;flex-wrap:wrap;gap:.75rem}.annotation-workplace [hidden]{display:none!important}.annotation-workplace ::selection{background:var(--water-soft)}#annotation-controls{scroll-margin-top:6rem}.annotation-mobile-nav{display:none}
@media(max-width:800px){.annotation-mobile-nav{display:flex;flex-wrap:wrap;gap:.75rem;margin-block:1rem;background:var(--wit);padding:.75rem;border:1px solid var(--line);border-radius:12px}.annotation-workplace{grid-template-columns:1fr}.annotation-document{max-height:65vh}.annotation-page{padding:1.25rem}.annotation-workplace aside{position:static;max-height:none}}
#annotation-controls h2{font-size:1.3rem;margin:0 0 1rem}#annotation-controls h3{font-size:1.1rem;line-height:1.4;margin:1.5rem 0 .5rem}#annotation-controls p{line-height:1.5;overflow-wrap:anywhere}#annotation-status{margin:.75rem 0;color:var(--muted);font-size:.9rem;min-height:1.5em}#annotation-controls details{margin-block:1rem}#annotation-controls summary{cursor:pointer;min-height:2.75rem;display:list-item;align-content:center}.annotation-task-actions{position:sticky;bottom:0;display:flex;flex-wrap:wrap;gap:.5rem;background:var(--wit);padding-block:1rem;border-top:1px solid var(--line);z-index:2}.annotation-task-actions .btn-primary{flex:1;min-height:2.75rem;white-space:normal}.annotation-task-actions .btn-secondary{flex:0 1 auto}#annotation-finish{flex:1 1 100%}#annotation-simple-rows dt{font-weight:600;margin-top:1.25rem;display:flex;align-items:center;justify-content:space-between;gap:.75rem;min-height:2.25rem}#annotation-simple-rows dd{margin:.35rem 0 0;overflow-wrap:anywhere}#annotation-simple-rows dd p{margin:.35rem 0}#annotation-simple-rows dd>.btn-secondary{margin-top:.35rem}.annotation-hint{color:var(--muted)}.annotation-line{display:flex;gap:.75rem;align-items:flex-start;justify-content:space-between;margin:.35rem 0}.annotation-line p{margin:0!important;min-width:0}.annotation-line.annotation-proposal{padding:.5rem;margin-inline:calc(-.5rem - 1px);border:1px dashed var(--paars);border-radius:8px}.annotation-proposal-label{display:block;color:var(--muted);font-size:.9rem;margin-bottom:.15rem}.annotation-signs{flex:none;display:flex;gap:.5rem}.annotation-sign{flex:none;display:inline-grid;place-items:center;width:2.25rem;height:2.25rem;padding:0;border:1px solid var(--paars);border-radius:8px;background:var(--wit);color:var(--paars);font:inherit;font-weight:700;font-size:1.15rem;line-height:1;cursor:pointer}.annotation-sign:focus-visible{outline:2px solid var(--paars);outline-offset:2px}@media(pointer:coarse){.annotation-sign{width:2.75rem;height:2.75rem}}.annotation-selection-menu{position:absolute;pointer-events:none;display:flex;flex-wrap:wrap;align-items:center;gap:.375rem;max-width:calc(100% - 1rem);padding:.375rem .5rem;background:var(--wit);border-radius:10px;box-shadow:0 4px 14px rgb(0 0 0/.14),0 1px 3px rgb(0 0 0/.1);text-indent:0;line-height:1.2;font-size:.95rem}.annotation-selection-menu[hidden]{display:none}
.annotation-application-choices{display:flex;flex:1 0 100%;flex-wrap:wrap;gap:.375rem}
.annotation-selection-menu button[aria-expanded=true]{background:var(--water-soft)}
#annotation-simple-rows .annotation-row-group{min-height:0;color:var(--paars)}
#annotation-simple-rows dt:is([data-row=population],[data-row=scope],[data-row=condition]){margin-top:.5rem}
.annotation-selection-menu button{min-height:2.25rem;padding:0 .75rem;border:1px solid var(--paars);border-radius:8px;background:var(--wit);color:var(--paars);font:inherit;font-weight:600;cursor:pointer;max-width:100%;white-space:normal;touch-action:manipulation;pointer-events:auto}.annotation-selection-menu button:hover{background:color-mix(in srgb,var(--paars) 10%,var(--wit))}.annotation-selection-menu button:active{opacity:.8}.annotation-selection-menu button:focus-visible{outline:2px solid var(--paars);outline-offset:2px}@media(pointer:coarse){.annotation-selection-menu button{min-height:2.75rem}}#annotation-simple-notes{padding-left:1.1rem;margin:.5rem 0}#annotation-simple-notes:empty,#annotation-simple-status:empty,#annotation-suggestion-note:empty{display:none}#annotation-simple-type{margin-top:1.25rem}#annotation-local-work{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}#annotation-controls button{touch-action:manipulation}#annotation-controls button:focus-visible,#annotation-controls summary:focus-visible{outline:2px solid var(--paars);outline-offset:3px}#annotation-controls button:active{opacity:.8}
@media(max-width:800px){.annotation-task-actions{padding-bottom:max(1rem,env(safe-area-inset-bottom))}#annotation-controls select{font-size:1rem}.annotation-document{max-height:60dvh}}
</style>'''
        return HTMLResponse(page(nav(actor,'selection')+'<section class="room">'+body+'</section>'+css,title='Bron aanwijzen'),headers={'Cache-Control':'no-store'})

    @app.post('/annotations/structure')
    async def confirm_structure(request: Request):
        actor = require(request)
        if not structure.enabled():
            return Response(status_code=404)
        form = await request.form()
        document = str(form.get('document') or '')
        try:
            entries = [
                {'block_id': anchor, 'title': title, 'level': int(level)}
                for anchor, title, level in zip(form.getlist('anchor'), form.getlist('title'), form.getlist('level'),
                                                strict=True)
            ]
            if not entries and not document_check.enabled():
                domain.fail('annotation_structure_invalid')
            await asyncio.to_thread(structure.confirm, console, actor_id=actor['account_id'], snapshot_id=document,
                                    extraction_hash=str(form.get('basis') or ''), entries=entries)
        except ConsoleError as exc:
            if exc.code not in {'annotation_structure_invalid', 'annotation_structure_stale',
                                'annotation_structure_conflict', 'annotation_structure_already_built'}:
                raise
            back = '/annotations?' + urlencode({'document': document})
            return HTMLResponse(page(nav(actor, 'selection') + '<section class="room"><h1>Inhoudsopgave niet opgeslagen</h1>'
                                     '<p>Open de werkplek opnieuw om de actuele structuur te bekijken.</p>'
                                     f'<p><a href="{escape(back, quote=True)}">Terug naar het document</a></p></section>'),
                                status_code=400 if exc.code == 'annotation_structure_invalid' else 409,
                                headers={'Cache-Control': 'no-store'})
        except ValueError:
            return HTMLResponse('De inhoudsopgave is ongeldig. Open de werkplek opnieuw.', status_code=400)
        return RedirectResponse('/annotations?' + urlencode({'document': document}), status_code=303)


    @app.post('/annotations/round')
    async def change_document_round(request: Request):
        actor = require(request)
        form = await request.form()
        document = str(form.get('document') or '')
        location = '/annotations?' + urlencode({'document': document})
        try:
            generation = int(str(form.get('expected_generation', '')))
            revision = int(str(form.get('expected_round', '')))
        except ValueError:
            return JSONResponse({'message': 'Open de actuele werkplek en probeer opnieuw.'}, status_code=400)
        try:
            await asyncio.to_thread(document_check.transition, console, actor_id=actor['account_id'],
                                    snapshot_id=document, phase=form.get('phase'),
                                    expected_generation=generation, expected_round=revision)
        except ConsoleError as exc:
            if exc.code not in {'annotation_document_round_stale', 'annotation_document_round_unavailable',
                                'annotation_document_round_invalid', 'annotation_structure_confirmation_required',
                                'processing_attempt_in_progress'}:
                raise
            return JSONResponse({'message': 'De werkrevisie is gewijzigd. Open de actuele annotatiewerkplek.'},
                                status_code=409, headers={'Cache-Control': 'no-store'})
        if request.headers.get('accept') == 'application/json':
            return JSONResponse({'location': location}, headers={'Cache-Control': 'no-store'})
        return RedirectResponse(location, status_code=303)

    @app.post('/annotations/coverage')
    async def record_coverage(request: Request):
        actor = require(request)
        if not structure.enabled():
            return Response(status_code=404)
        form = await request.form()
        document = str(form.get('document') or '')
        basis = str(form.get('basis') or '')
        scope, section, fingerprint = (form.get(key) for key in ('scope', 'section', 'fingerprint'))
        error = None
        try:
            await asyncio.to_thread(section_coverage.write, console, actor_id=actor['account_id'],
                                    snapshot_id=document, basis=basis, scope=scope, section=section,
                                    fingerprint=fingerprint)
        except ConsoleError as exc:
            if exc.code not in {'annotation_coverage_invalid', 'annotation_coverage_stale',
                                'annotation_coverage_scope_closed', 'annotation_coverage_build_locked'}:
                raise
            error = exc.code
        location = '/annotations?' + urlencode({'document': document})
        if request.headers.get('accept') == 'application/json':
            state = await asyncio.to_thread(editor_state, actor, document, include_source_work=True)
            message = 'Sectie gemarkeerd als nagekeken.' if section else 'Reikwijdte opgeslagen.'
            if error == 'annotation_coverage_build_locked':
                message = 'De actieve bouw gebruikt deze reikwijdte en sectiecontroles.'
            elif error:
                message = 'De sectie is gewijzigd. Controleer de actuele inhoudsopgave.'
            return JSONResponse({'generation': state['generation'],
                                 'contents': confirmed_contents(state, document) if structure.KEY in state else '',
                                 'message': message},
                                status_code=409 if error else 200, headers={'Cache-Control': 'no-store'})
        if error:
            return HTMLResponse(page(nav(actor, 'selection') + '<section class="room"><h1>Dekking niet opgeslagen</h1>'
                                     f'<p><a href="{escape(location, quote=True)}">Open de actuele inhoudsopgave</a></p></section>'),
                                status_code=409, headers={'Cache-Control': 'no-store'})
        if isinstance(section, str):
            location += '#' + quote(section, safe='')
        return RedirectResponse(location, status_code=303)

    @app.get('/annotations/editor.js')
    def script(request: Request):
        require(request)
        return Response(Path(__file__).with_name('human_annotation_editor.js').read_text(),media_type='text/javascript',headers={'Cache-Control':'no-store'})

    @app.get('/annotations/binding.mjs')
    def binding_script(request: Request):
        require(request)
        return Response(Path(__file__).with_name('human_annotation_binding.mjs').read_text(),media_type='text/javascript',headers={'Cache-Control':'no-store'})

    @app.post('/annotations/source-role')
    async def source_role(request: Request):
        actor = require(request)
        form = await request.form()
        document = str(form.get('document') or '')
        document_url = '/annotations?'+urlencode({'document': document})
        wants_json = request.headers.get('accept') == 'application/json'
        try:
            role, _, reason = str(form.get('reason') or '').partition(':')
            generation = int(str(form.get('expected_generation') or ''))
            command_id = str(form.get('command_id') or '')
            group = str(form.get('group') or '')
            members = form.getlist('member')
            if not members and not group and form.get('block_id'):
                members = [json.dumps([str(form['block_id']), int(str(form['start'])), int(str(form['end']))])]
            from src.review.source_context_review_v1 import GROUP_MAX
            if not command_id or not 1 <= len(members) <= (GROUP_MAX if group else 1):
                raise ConsoleError('annotation_command_invalid')
            view = await asyncio.to_thread(domain.overview, console, actor_id=actor['account_id'], snapshot_id=document)
            by_id = {block['block_id']: block['text'] for block in view['blocks']}
            ranges = []
            for member_key in members:
                block_id, start, end = json.loads(member_key)
                if not isinstance(block_id, str) or type(start) is not int or type(end) is not int:
                    raise ConsoleError('annotation_command_invalid')
                text = by_id.get(block_id)
                if text is None or not 0 <= start < end <= len(text):
                    raise ConsoleError('annotation_source_role_stale')
                ranges.append({'block_id': block_id, 'start': start, 'end': end, 'quote': text[start:end],
                               'role': 'core', 'evidence_function': None})
            selection = {'status': 'ready', 'object_type': None, 'evidence_not_applicable': False,
                         'disposition': {'role': role, 'reason': reason}, 'ranges': ranges}
            result = await asyncio.to_thread(domain.save, console, actor_id=actor['account_id'], snapshot_id=document,
                command_id=command_id, annotation_id=str(uuid5(NAMESPACE_URL, 'metis-source-role:'+document+':'+command_id)),
                expected_revision=0, expected_generation=generation,
                extraction_hash=str(form.get('extraction_hash') or view['extraction_hash']),
                normalization=view['normalization'], selection=selection,
                expected_objects_revision=str(form.get('expected_objects_revision') or ''),
                source_role_group=group)
        except ConsoleError as exc:
            if exc.code in {'not_authenticated', 'researcher_role_required', 'reviewer_not_named_on_snapshot'}:
                raise
            error = exc
        except (ValueError, TypeError, KeyError):
            error = ConsoleError('annotation_command_invalid')
        else:
            if wants_json:
                return JSONResponse(result, headers={'Cache-Control': 'no-store'})
            return RedirectResponse(document_url+'#annotation-source-work', status_code=303)
        message = ERRORS.get(error.code, 'Vastleggen is niet gelukt. Controleer de tekst en probeer opnieuw.')
        if wants_json:
            return JSONResponse({'error': error.code, 'message': message}, status_code=409)
        body = '<h1>Niet vastgelegd</h1><p role="alert">'+esc(message)+'</p>'
        body += '<p><a href="'+esc(document_url)+'">Terug naar de bron</a></p>'
        return HTMLResponse(page(nav(actor,'selection')+'<section class="room">'+body+'</section>', title='Bron aanwijzen'),
                            status_code=409, headers={'Cache-Control':'no-store'})

    @app.post('/annotations/finalize')
    async def finalize_document(request: Request):
        actor = require(request)
        form = await request.form()
        document = str(form.get('document') or '')
        from src.vorming import human_annotation_build_v1 as build
        try:
            generation = int(str(form.get('expected_generation') or ''))
        except ValueError:
            raise ConsoleError('annotation_command_invalid')
        try:
            receipt = await asyncio.to_thread(build.finalize, console, actor_id=actor['account_id'],
                snapshot_id=document, command_id=str(form.get('command_id') or ''),
                overview_hash=str(form.get('overview_hash') or ''), expected_generation=generation,
                expected_revision=str(form.get('expected_revision') or ''))
        except ConsoleError as error:
            if error.code in {'not_authenticated', 'researcher_role_required', 'reviewer_not_named_on_snapshot'}:
                raise
            body = '<h1>Document nog niet afgesloten</h1><p role="alert">'+esc(ERRORS.get(error.code,
                'Afsluiten is niet gelukt. Je opgeslagen annotaties blijven bewaard. Controleer het documentoverzicht.'))+'</p>'
            body += '<p><a href="/annotations?'+esc(urlencode({'document':document,'overview':'true'}))+'">Terug naar documentcontrole</a></p>'
            return HTMLResponse(page(nav(actor,'selection')+'<section class="room">'+body+'</section>', title='Document controleren'),
                                status_code=409, headers={'Cache-Control':'no-store'})
        from src.vorming.worker_handover_v1 import native_attempt
        attempt = native_attempt(console, document, receipt['attempt_id'])
        if attempt and attempt['state'] == 'running':
            dispatcher.notify(document, attempt)
        return RedirectResponse('/annotations/build?'+urlencode({'document':document,'attempt':receipt['attempt_id']}), status_code=303)

    @app.post('/annotations/rebuild')
    async def rebuild(request: Request):
        # #1064: the card's 'Kennisobject opnieuw bouwen'. The existing build, then back to Review.
        actor = require(request)
        from src.vorming import human_annotation_build_v1 as build
        try:
            body = await request.json()
            document = str(body.get('document') or '')
            result = await asyncio.to_thread(build.rebuild, console, actor_id=actor['account_id'], snapshot_id=document,
                annotation_id=str(body.get('annotation') or ''), command_id=str(body.get('command_id') or ''),
                expected_generation=body.get('expected_generation'))
        except ConsoleError as error:
            if error.code in {'not_authenticated', 'researcher_role_required', 'reviewer_not_named_on_snapshot'}:
                raise
            return JSONResponse({'error':error.code,'message':ERRORS.get(error.code,
                'Opnieuw bouwen is niet gestart. Je aanpassing is bewaard.')}, status_code=409, headers={'Cache-Control':'no-store'})
        except (ValueError, AttributeError):
            return JSONResponse({'error':'annotation_command_invalid','message':'Opnieuw bouwen is niet gestart. Je aanpassing is bewaard.'},
                                status_code=400, headers={'Cache-Control':'no-store'})
        if result['started']:
            from src.vorming.worker_handover_v1 import native_attempt
            attempt = native_attempt(console, document, result['attempt_id'])
            if attempt and attempt['state'] == 'running':
                dispatcher.notify(document, attempt)
        return JSONResponse({'review_url':'/review?'+urlencode({'document':document,'object':result['object_id']})},
                            headers={'Cache-Control':'no-store'})

    def build_state_label(attempt):
        if attempt['state'] == 'running':
            return 'Wacht op verwerking' if attempt['dispatch_state'] == 'pending' else 'Bezig'
        return 'Geslaagd' if attempt['state'] == 'succeeded' else 'Gestopt'

    def build_status(actor, document, attempt, *, history=False):
        from src.vorming.human_annotation_build_read_v1 import status_overview
        return status_overview(console, actor, document, attempt, history=history)

    @app.get('/annotations/build/api')
    def get_build_status(request: Request, document: str, attempt: str = ''):
        envelope, selected, _ = build_status(require(request), document, attempt)
        result = {'title': envelope['title'], 'attempt_id': None}
        if selected:
            result.update(attempt_id=selected['attempt_id'], state=selected['state'],
                          message=build_state_label(selected), duration_seconds=selected['duration_seconds'],
                          current=selected['current'], started_at=selected['claimed_at'],
                          detail=ERRORS.get(selected['error_code'], ''))
        return JSONResponse(result, headers={'Cache-Control': 'no-store'})

    @app.get('/annotations/build', response_class=HTMLResponse)
    def build_page(request: Request, document: str, attempt: str = ''):
        from datetime import datetime, timezone

        def show_time(value):
            if not value:
                return 'Niet vastgelegd'
            timestamp = datetime.fromisoformat(value) if isinstance(value, str) else value
            return ('<time datetime="' + esc(timestamp.isoformat()) + '">' +
                    timestamp.astimezone(timezone.utc).strftime('%d-%m-%Y %H:%M UTC') + '</time>')

        actor = require(request)
        envelope, selected, attempts = build_status(actor, document, attempt, history=True)
        title = 'Bouwopdrachten'
        body = '<h1>' + title + '</h1><p class="lead">' + esc(envelope['title'])
        if envelope.get('version'):
            body += ' · Bronversie ' + esc(envelope['version'])
        body += '</p>'
        if not selected:
            body += '<p>Er is nog geen bouwopdracht voor dit document.</p>'
        else:
            params = {'document': document, 'attempt': selected['attempt_id']}
            poll_url = '/annotations/build/api?' + urlencode(params)
            label = 'Laatste bouwopdracht' if selected['latest'] else 'Geselecteerde bouwopdracht'
            body += f'<article class="doc-card"><h2>{label}</h2>'
            body += (f'<p id="annotation-build-status" class="banner" role="status" '
                     f'data-build-state="{esc(selected["state"])}" data-status-url="{esc(poll_url)}">'
                     f'{build_state_label(selected)}</p>')
            if not selected['current']:
                body += '<p class="banner warn">Deze opdracht hoort bij een eerdere bouw of annotatieversie.</p>'
            duration = selected['duration_seconds']
            built_count, review_count = selected['built_count'], selected['review_count']
            fields = (
                ('Annotatieversie', str(selected['generation']), ''),
                ('Opdracht ingediend', show_time(selected['started_at']), ''),
                ('Gestart', show_time(selected['claimed_at']), ' id="annotation-build-started"'),
                ('Duur sinds indienen', f'{duration} s' if duration is not None else 'Niet vastgelegd', ' id="annotation-build-duration"'),
                ('Kennisobjecten gebouwd', str(built_count) if built_count is not None else 'Onbekend', ''),
                ('Klaar voor Review', str(review_count) if review_count is not None else 'Onbekend', ''),
            )
            body += '<dl>' + ''.join(f'<div><dt>{key}</dt><dd{attr}>{value}</dd></div>'
                                     for key, value, attr in fields) + '</dl>'
            if selected['state'] not in {'running', 'succeeded'}:
                reason = ERRORS.get(selected['error_code'], '')
                if not reason:
                    reason = ('Meldcode: ' + selected['error_code'] if selected['error_code']
                              else 'De reden is niet vastgelegd.')
                body += '<p id="annotation-build-detail">' + esc(reason) + '</p>'
            outline = selected['outline']
            if outline and outline['entries']:
                body += '<details><summary>Bevestigde inhoudsopgave</summary><ul>' + ''.join(
                    f'<li>{esc(row["title"])}</li>' for row in outline['entries']) + '</ul></details>'
            if selected['current'] and review_count:
                review = '/review?' + urlencode({'document': document})
                body += f'<p><a id="annotation-build-review" class="btn-primary" href="{esc(review)}">Naar Review</a></p>'
            elif selected['can_recover']:
                recovery = '/annotations?' + urlencode({'document': document, 'overview': 'true'})
                body += f'<p><a class="btn-secondary" href="{esc(recovery)}">Naar Documentcontrole</a></p>'
            body += '<p id="annotation-build-feedback" class="muted" role="status" hidden></p></article>'
            other_attempts = [row for row in attempts if row['attempt_id'] != selected['attempt_id']]
            if other_attempts:
                items = []
                for row in other_attempts:
                    link = '/annotations/build?' + urlencode({'document': document, 'attempt': row['attempt_id']})
                    items.append(f'<li><a href="{esc(link)}">{build_state_label(row)} · '
                                 f'{show_time(row["started_at"])} · Annotatieversie {row["generation"]}</a></li>')
                body += '<details><summary>Andere bouwopdrachten</summary><ul>' + ''.join(items) + '</ul></details>'
            body += '<script src="/annotations/build.js" defer></script>'
        return HTMLResponse(page(nav(actor, 'selection') + '<section class="room annotation-build-room">' +
                            body + '</section>', title=title), headers={'Cache-Control': 'no-store'})

    @app.get('/annotations/build.js')
    def build_script(request: Request):
        require(request)
        return Response(Path(__file__).with_name('human_annotation_build_status.js').read_text(),
                        media_type='text/javascript', headers={'Cache-Control':'no-store'})

    @app.post('/annotations/source')
    async def prepare_source(request: Request):
        actor = require(request)
        form = await request.form()
        from src.vorming import human_annotation_source_v1 as source
        document = str(form.get('document') or '')
        try:
            attempt, fresh = await asyncio.to_thread(source.reserve, console,
                actor_id=actor['account_id'], snapshot_id=document,
                command_id=str(form.get('command_id') or ''),
                expected_revision=str(form.get('expected_revision') or ''))
        except ConsoleError as exc:
            messages = {
                'annotation_source_not_received':'Deze bron valt onder een andere vormingsroute.',
                'annotation_prose_required':'Open de beslisboom in Vorming.',
                'annotation_source_storage_not_ready':'De bronvoorbereiding is nog niet beschikbaar. Laat de beheerder de opslag bijwerken.',
                'annotation_processing_in_progress':'Er loopt al een andere verwerking voor dit document. Open Documenten om de voortgang te bekijken.',
                'annotation_objects_stale':'Het document is gewijzigd. Open de bronpagina opnieuw voordat je verdergaat.',
                'processing_admission_closed':'Nieuwe voorbereidingen zijn tijdelijk gepauzeerd. Probeer het later opnieuw.',
                'processing_attempt_limit_reached':'Er zijn meerdere voorbereidingen gestopt. Laat de beheerder de oorzaak controleren voordat je opnieuw probeert.',
                'published_working_revision_immutable':'Deze versie is gepubliceerd. Bereid een nieuwe werkversie voor.',
                'published_objects_must_not_be_rewritten':'Deze versie is gepubliceerd. Bereid een nieuwe werkversie voor.',
                'annotation_existing_work_requires_takeover':'Dit document bevat al gevormd werk. Open de bestaande werkversie.',
            }
            from src.request_diagnostics_v1 import note_handled_error
            note_handled_error(exc.code)
            status = 403 if exc.code in {'researcher_role_required','reviewer_not_named_on_snapshot','not_authenticated'} else 409
            body = nav(actor,'selection')+'<section class="room"><h1>Bron kon niet worden voorbereid</h1><p class="banner warn" role="alert">'+esc(messages.get(exc.code,'De voorbereiding kon niet worden gestart. Open de bronpagina opnieuw en controleer het document.'))+'</p><p><a href="/annotations?'+esc(urlencode({'document':document}))+'">Terug naar de bronpagina</a></p></section>'
            return HTMLResponse(page(body,title='Bron voorbereiden'),status_code=status,headers={'Cache-Control':'no-store'})
        if attempt is not None and attempt['state'] == 'running':
            dispatcher.notify(document, attempt)
        return RedirectResponse('/annotations?'+urlencode({'document':document}),status_code=303)

    @app.get('/annotations/api')
    def get(request: Request, document: str, source_work: bool = False):
        actor = require(request)
        state = editor_state(actor, document, include_source_work=source_work)
        if source_work:
            output = {'generation': state['generation'], 'work': state['source_work'],
                      'html': '' if state.get('document_check_flow') else source_work_html(state, esc)}
            if state.get('document_check_flow'):
                output['document_check_html'] = document_check_panel(state, actor, document)
            if section_coverage.KEY in state:
                output['contents'] = confirmed_contents(state, document)
            state = output
        return JSONResponse(state, headers={'Cache-Control': 'no-store'})

    @app.get('/annotations/check')
    def check(request: Request, document: str, annotation: str):
        actor = require(request)
        try:
            result = domain.check_current(console, actor_id=actor['account_id'],
                snapshot_id=document, annotation_id=annotation)
        except ConsoleError as exc:
            status = 403 if exc.code in {'not_authenticated','researcher_role_required','reviewer_not_named_on_snapshot'} else 409
            return JSONResponse({'error':exc.code,'message':ERRORS.get(exc.code,
                'De controle kon niet worden gelezen. Open de opgeslagen annotatie opnieuw.')},
                status_code=status, headers={'Cache-Control':'no-store'})
        result['findings'] = [{'code':code,'field':CHECK_FIELDS.get(code),'message':FINDINGS.get(code,
            UNKNOWN_FINDING)} for code in result.pop('codes')]
        result['signals'] = [{'code':code,'field':CHECK_FIELDS.get(code),'message':SIGNALS.get(code,
            'Metis kon een onderdeel van deze uitspraak niet vaststellen.')} for code in result.pop('signals')]
        return JSONResponse(result, headers={'Cache-Control':'no-store'})

    @app.post('/annotations/passage-offer')
    @app.post('/annotations/suggest')
    async def suggest(request: Request):
        from starlette.concurrency import run_in_threadpool
        if request.url.path.endswith('/passage-offer'):
            from src.vorming.human_annotation_passage_offer import suggest as propose
        else:
            from src.vorming.human_annotation_suggestion_v1 import suggest as propose
        actor = require(request)
        try:
            body = await request.json()
            result = await run_in_threadpool(propose, console, actor_id=actor['account_id'], request=body)
        except ConsoleError as exc:
            code = exc.code
            status = (403 if code in {'not_authenticated','researcher_role_required','reviewer_not_named_on_snapshot'}
                      else 409 if code == 'annotation_suggestion_stale'
                      else 422 if code in {'annotation_suggestion_invalid','annotation_suggestion_input_limit'} else 503)
            return JSONResponse({'error':code, 'message':
                'Het voorstel kon niet worden gemaakt. Je opgeslagen werk blijft bewaard. '
                'Probeer opnieuw of vul de betekenis zelf in.'}, status_code=status,
                headers={'Cache-Control':'no-store'})
        except ValueError:
            return JSONResponse({'error':'annotation_suggestion_invalid'}, status_code=422,
                headers={'Cache-Control':'no-store'})
        return JSONResponse(result, headers={'Cache-Control':'no-store'})

    @app.post('/annotations/api')
    async def save(request: Request):
        actor = require(request)
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({'error':'annotation_command_invalid','message':'Open de annotatie opnieuw.'},status_code=422)
        required = {'snapshot_id','command_id','annotation_id','expected_revision','expected_generation','extraction_hash','normalization','selection'}
        if not isinstance(body,dict) or not required <= set(body) or set(body) - required - {'expected_objects_revision'}:
            return JSONResponse({'error':'annotation_command_invalid','message':'Open de annotatie opnieuw.'},status_code=422)
        try:
            result = domain.save(console,actor_id=actor['account_id'],**body)
        except ConsoleError as exc:
            code = exc.code
            status = 409 if code in {'annotation_write_conflict','annotation_command_conflict','annotation_representation_stale','annotation_client_contract_stale','annotation_objects_stale','annotation_historical_read_only'} else 422
            if code in {'not_authenticated','researcher_role_required','reviewer_not_named_on_snapshot'}:
                status = 403
            detail = {'error':code,'message':ERRORS.get(code,'Opslaan is niet gelukt. Controleer de bronselectie en probeer opnieuw.')}
            if isinstance(exc, domain.AnnotationCoreConflict):
                detail['conflicting_annotation_id'] = exc.conflicting_annotation_id
            return JSONResponse(detail,status_code=status)
        return JSONResponse(result,headers={'Cache-Control':'no-store'})

    @app.get('/annotations/original')
    def original(request: Request, document: str):
        actor = require(request)
        envelope = console._envelope(document)
        domain.authorize(console, actor['account_id'], envelope)
        _, data = console._verified_source_bytes(envelope)
        # Download rather than executing received HTML in the authenticated origin.
        return Response(data,media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="source"','Cache-Control':'no-store'})
