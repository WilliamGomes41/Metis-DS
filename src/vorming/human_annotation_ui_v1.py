"""Source-first annotation workplace; every saved choice is server-confirmed."""
from html import escape
import json
from pathlib import Path
import re
from uuid import uuid4
import asyncio
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_v1 as domain

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
    'navigation':'Navigatie','document_structure':'Documentstructuur',
    'unformed_meaning':'Nog niet tot een uitspraak gevormd','uncertain_source_role':'Bronfunctie nog onzeker'}
ERRORS = {
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
    'source_bound_fields_invalid':'De onderdelen van de uitspraak zijn niet volledig aangeleverd. Open de annotatie opnieuw.',
    'source_bound_field_invalid':'Wijs voor dit onderdeel de exacte brontekst aan.',
    'recommendation_semantics_invalid':'Controleer de richting en sterkte bij deze aanbeveling en wijs het bijbehorende bronbewijs aan.',
    'annotation_required_relationship_missing':'Een essentieel verband ontbreekt. Wijs de bijbehorende tekst opnieuw aan of leg expliciet vast waarom de verplichting vervalt.',
    'annotation_relationship_withdrawal_required':'Licht toe waarom dit essentiële verband niet langer nodig is.',
    'annotation_context_proposal_open':'Metis stelt tekst voor die bij deze uitspraak hoort. Voeg het voorstel in de kaart toe met + of wijs het af met −.',
    'annotation_declined_context_invalid':'Een afgewezen voorstel past niet bij deze bron. Open de opgeslagen annotatie opnieuw.',
}
FINDINGS = {**ERRORS,
    'annotation_source_empty':'Er is geen leesbare brontekst beschikbaar. Controleer het vastgelegde origineel voordat je verdergaat.',
    'annotation_not_ready':'Deze annotatie is nog niet gereed.',
    'annotation_fields_required':'Wijs de noodzakelijke betekenisvelden van deze uitspraak aan.',
    'annotation_relation_target_missing':'Wijs expliciet aan bij welke uitspraak dit onderdeel hoort.',
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
        in_toc = bool(path and path[0].casefold() == 'inhoudsopgave')
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
        elif block.get('heading') and block['heading'] == text:
            if toc_row_open:
                parts.append('</p>')
                toc_row_open = False
            level = min(5, max(2, len(path) + 1))
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


def install(app, console, require, page, nav, esc, *, dispatcher):
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
            hidden = '<input type="hidden" name="document" value="'+esc(document)+'">'
            hidden += '<input type="hidden" name="command_id" value="'+uuid4().hex+'">'

            hidden += '<input type="hidden" name="expected_revision" value="'+esc(console.objects_revision(document))+'">'
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
                    body += '<p class="banner warn" role="alert">Het voorbereiden van de bron is gestopt. Je bronbestand en opgeslagen werk blijven bewaard.</p>'
                    body += '<form method="post" action="/annotations/source">'+hidden+'<button class="btn-primary" type="submit">Bronvoorbereiding opnieuw proberen</button></form>'
                body += '<p><a href="/tree">Terug naar Documenten</a></p></section>'
                return HTMLResponse(page(body,title='Bron voorbereiden'),headers={'Cache-Control':'no-store'})
            notice = '<div class="banner ok" role="status">Document veilig ontvangen. Open de bron om te annoteren.</div>' if request.query_params.get('received') == 'yes' else ''
            return HTMLResponse(page(nav(actor,'selection')+'<section class="room"><h1>Bron aanwijzen</h1><h2>'+esc(envelope['title'])+'</h2>'
                +notice+
                '<p>Open de vastgelegde bron om uitspraken, voorwaarden, uitzonderingen en onderbouwing aan te wijzen. Je kunt concepten opslaan en later hervatten.</p>'
                '<p>Annoteren geeft geen goedkeuring. De bij ontvangst gekozen beoordeling blijft gelden.</p>'
                '<form method="post" action="/annotations/source">'+hidden+'<button class="btn-primary" type="submit">Bron openen voor annotatie</button></form></section>',title='Bron aanwijzen'),headers={'Cache-Control':'no-store'})
        from src.vorming import human_annotation_build_v1 as build
        state = (build.overview if overview else domain.overview)(console, actor_id=actor['account_id'], snapshot_id=document)
        from src.vorming.source_bound_fields_v3 import FIELDS, TYPE_FIELDS, CONTEXT_FIELDS
        from src.vorming.human_annotation_contract_v1 import CONTEXT_BINDING_FIELDS, ROLE_MAP
        from src.vorming.human_annotation_v1 import TYPE_CORE_FIELDS
        from src.vorming.source_accountability_v1 import ROLES as SOURCE_ROLES
        state['field_contract']={'fields':list(FIELDS),'labels':FIELD_LABELS,'type_core_fields':TYPE_CORE_FIELDS,
            'type_fields':TYPE_FIELDS,
            'context_bindings':{role:field for role,field in CONTEXT_BINDING_FIELDS.items() if ROLE_MAP[role] in CONTEXT_FIELDS[field]},
            'source_roles':{role:[{'value':reason,'label':SOURCE_LABELS[reason]} for reason in reasons] for role,reasons in SOURCE_ROLES.items()}}
        version = esc(state['source_identity']['version'])
        back = '/annotations?' + urlencode({'document':document})
        intro = '<h1>'+('Documentoverzicht' if overview else 'Bron aanwijzen')+'</h1><h2>'+esc(state['title'])+'</h2><p data-working-revision="'+esc(state['working_revision_id'])+'">Bronversie '+version+'</p>'
        intro += '<p><a target="_blank" rel="noopener" href="/annotations/original?'+esc(urlencode({'document':document}))+'">Open het vastgelegde origineel</a></p>'
        if overview:
            items = []
            for entry in state['entries']:
                if entry['status']=='withdrawn':
                    continue
                spans = ''.join('<li><strong>'+escape(LABELS[a['role']])+ (' — verklaart' if a['evidence_function']=='explains' else ' — onderbouwt' if a['evidence_function']=='supported_by' else '')+('</strong> (essentieel)' if a['required_for_meaning'] else '</strong>')+
                    ': '+escape(a['quote'])+' <a href="'+escape(back+'#'+a['block_id'],quote=True)+'">Open in bron</a></li>' for a in entry['ranges'])
                missing = 'Selectie nog niet gereed.' if entry['status']!='ready' else ''
                if entry.get('pending_range'):
                    missing += ' Er staat nog een niet-gekoppelde aanwijzing klaar: '+entry['pending_range']['quote']
                duties = ''.join('<li>'+escape(LABELS[link['role']])+': '+
                    ('essentieel verband ontbreekt' if link['required_for_meaning'] else
                     'verplichting teruggenomen: '+escape(link['withdrawal_reason']))+'</li>'
                    for link in entry.get('required_links',[]))
                fields = []
                by_id = {b['block_id']:b for b in state['blocks']}
                for field,evidence in (entry.get('field_evidence') or {}).items():
                    if field not in FIELD_LABELS or not evidence.get('span'):
                        continue
                    span = evidence['span']
                    literal = by_id[span['block_id']]['text'][span['start']:span['end']]
                    fields.append('<li>'+escape(FIELD_LABELS[field])+': '+escape(literal)+'</li>')
                heading=('Brongebruik: '+SOURCE_LABELS.get(entry['disposition']['reason'],'Functie nog kiezen')) if entry.get('disposition') else TYPES.get(entry['object_type'],'Type nog kiezen')
                items.append('<article class="object"><h3>'+escape(heading)+'</h3><p>'+escape(missing)+'</p><ul>'+spans+'</ul>'+
                    ('<p>Relatieverplichtingen</p><ul>'+duties+'</ul>' if duties else '')+
                    ('<p>Aangewezen betekenisvelden</p><ul>'+''.join(fields)+'</ul>' if fields else '')+
                    ('<p>Onderbouwing: expliciet niet van toepassing.</p>' if entry['evidence_not_applicable'] else '')+
                    '<a href="'+escape(back+'&annotation='+entry['annotation_id'],quote=True)+'">Deze annotatie aanpassen</a></article>')
            body = intro + (''.join(items) or '<p>Er zijn nog geen selecties opgeslagen.</p>')
            inspection = state['inspection']
            if inspection['findings']:
                body += '<section aria-labelledby="annotation-findings"><h2 id="annotation-findings">Nog controleren vóór afsluiten</h2><ul>'
                for finding in inspection['findings']:
                    target = back + ('&annotation='+finding['annotation_id'] if finding['annotation_id'] else '')
                    body += '<li>'+esc(FINDINGS.get(finding['code'], 'Controleer de aangewezen betekenisvelden en hun bronbereiken.'))
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
                    body += '<li>'+esc(' '.join(dict.fromkeys(SIGNALS.get(code, 'Een onderdeel is niet vastgesteld.') for code in entry['signals'])))
                    body += ' <a href="'+esc(back+'&annotation='+entry['annotation_id'])+'">Annotatie bekijken</a></li>'
                body += '</ul></section>'
            if inspection['unaccounted_ranges']:
                body += '<section aria-labelledby="annotation-gaps"><h2 id="annotation-gaps">Nog niet verantwoord bronmateriaal</h2><ul>'
                for gap in inspection['unaccounted_ranges']:
                    body += '<li><q>'+esc(gap['quote'])+'</q> <a href="'+esc(back+'#'+gap['block_id'])+'">Dit bronblok aanwijzen</a></li>'
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
            return HTMLResponse(page(nav(actor,'selection')+'<section class="room"><div style="max-width:72ch">'+body+'</div></section>',title='Documentoverzicht'),headers={'Cache-Control':'no-store'})
        blocks = source_document_html(state['blocks'])
        pages = list(dict.fromkeys(loc['page'] for block in state['blocks']
            for loc in block.get('locations') or [] if loc.get('page')))
        page_options = ''.join('<option value="source-page-'+str(p)+'">Pagina '+str(p)+'</option>' for p in pages)
        role_options = ''.join('<option value="'+key+'">'+label+'</option>' for key,label in LABELS.items())
        from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES
        type_options = '<option value="">Laat Metis het type voorstellen</option>'+''.join('<option value="'+key+'">'+label+'</option>' for key,label in TYPES.items() if key in CLOSED_OBJECT_TYPES)+'<option value="source_disposition">Dit bronstuk verantwoorden</option>'
        data = json.dumps(state,ensure_ascii=False).replace('<','\\u003c')
        body = intro + '''<p>Selecteer een uitspraak in de bron. Voeg met + de tekst toe die erbij hoort en de onderbouwing.</p>
<nav class="annotation-mobile-nav" aria-label="Wisselen tussen bron en annotatie"><a id="annotation-to-controls" href="#annotation-controls">Naar huidige annotatie</a><a id="annotation-to-source" href="#'''+esc(state['blocks'][0]['block_id'] if state['blocks'] else '')+'''">Terug naar bron</a></nav>
<div class="annotation-workplace"><div class="annotation-document" aria-label="Document in leesvolgorde"><div class="annotation-document-tools"><strong>Documenttekst</strong><span id="annotation-keyboard-hint" class="sr-only">Selecteer rechtstreeks in de bron. Met toetsenbord: focus een passage en gebruik Shift met de pijltoetsen naar links of rechts. Home en End gaan naar begin en einde van de passage.</span>'''+('<label for="annotation-page-nav">Ga naar pagina</label><select id="annotation-page-nav">'+page_options+'</select>' if pages else '')+'''</div>'''+blocks+'''</div>
<aside id="annotation-controls" tabindex="-1" aria-label="Huidige annotatie"><h2>Kennisobject voorbereiden</h2>
<p id="annotation-initializing" role="status">De annotatiewerkplek wordt klaargezet.</p>
<fieldset id="annotation-editor-inputs" aria-label="Annotatie bewerken" disabled>
<nav class="annotation-steps" id="annotation-steps" aria-label="Annotatiestappen" hidden><ol>
<li><button type="button" id="annotation-step-1" aria-current="step">1. Uitspraak kiezen</button></li>
<li><button type="button" id="annotation-step-2">2. Aanvullen</button></li>
<li><button type="button" id="annotation-step-3">3. Afronden</button></li></ol></nav>
<p id="annotation-status" role="status" aria-live="polite"></p>
<div id="annotation-entry-box"><label for="annotation-entry" id="annotation-entry-label">Huidige annotatie</label><select id="annotation-entry"><option value="">Nieuwe annotatie</option></select></div>
<section id="annotation-current-object" hidden aria-labelledby="annotation-current-version"><h3 id="annotation-current-version"></h3><p id="annotation-current-text"></p><p id="annotation-current-state" role="status"></p><a id="annotation-current-review" target="_blank" rel="noopener">Open deze versie in Review</a></section>
<section id="annotation-simple" aria-labelledby="annotation-simple-heading"><h3 id="annotation-simple-heading" tabindex="-1">Selecteer de uitspraak in de bron</h3>
<dl id="annotation-simple-rows"></dl>
<div id="annotation-simple-type" hidden><label for="annotation-simple-type-select">Metis kon het type niet bepalen. Wat voor uitspraak is dit?</label><select id="annotation-simple-type-select"><option value="">Kies het type</option></select></div>
<p id="annotation-simple-status" role="status" aria-live="polite"></p><ul id="annotation-simple-notes"></ul></section>
<section id="annotation-task-1" aria-labelledby="annotation-heading-1" hidden><h3 id="annotation-heading-1" tabindex="-1">Welke uitspraak wil je vastleggen?</h3>
<label for="annotation-type">Type (optioneel vooraf kiezen)</label><select id="annotation-type">'''+type_options+'''</select>
<div id="annotation-source-disposition" hidden><label for="annotation-source-reason">Functie van dit bronstuk</label><select id="annotation-source-reason"></select><p>Dit bewaart een bronrolvoorstel, geen kennisobject of goedkeuring.</p></div>
<p id="annotation-core-summary"></p></section>
<p id="annotation-suggestion-note" role="status" aria-live="polite"></p>
<section id="annotation-task-2" aria-labelledby="annotation-heading-2" hidden><h3 id="annotation-heading-2" tabindex="-1">Betekenis aanpassen</h3>
<blockquote id="annotation-proposal-core"></blockquote>
<div id="annotation-full-intro"><p>Type: <strong id="annotation-type-summary"></strong> <button class="btn-secondary" type="button" id="annotation-change-type">Type aanpassen</button></p></div>
<div id="annotation-meaning"><label for="annotation-field" hidden>Onderdeel</label><select id="annotation-field" hidden></select><dl id="annotation-fields"></dl></div>
<details id="annotation-context-tools"><summary>Context of onderbouwing toevoegen</summary><p>Kies wat je wilt toevoegen en wijs de tekst in de bron aan.</p>
<label for="annotation-role">Wat wil je toevoegen?</label><select id="annotation-role">'''+role_options+'''</select>
<div id="annotation-evidence-function" hidden><label for="annotation-function">Hoe helpt deze onderbouwing?</label><select id="annotation-function"><option value="supported_by">Onderbouwt de uitspraak</option><option value="explains">Verklaart de uitspraak</option></select></div></details>
<fieldset id="annotation-essential-choice" hidden><legend>Verandert de betekenis als dit ontbreekt?</legend>
<label><input type="radio" name="annotation-essentiality" id="annotation-essential"> Ja, essentieel voor de betekenis</label>
<label><input type="radio" name="annotation-essentiality" id="annotation-additional"> Nee, aanvullende context</label></fieldset>
<div id="annotation-evidence"><p id="annotation-evidence-summary"></p><label><input type="checkbox" id="annotation-na">Onderbouwing is niet van toepassing</label></div>
<details id="annotation-recommendation"><summary>Richting en sterkte van de aanbeveling</summary>
<label for="annotation-direction">Richting</label><select id="annotation-direction"><option value="">Kiezen</option><option value="for">Toepassen of overwegen</option><option value="against">Afraden of vermijden</option></select>
<button class="btn-secondary" type="button" id="annotation-direction-evidence">Brontekst voor de richting aanwijzen</button><p id="annotation-direction-proof"></p>
<label for="annotation-strength-status">Is de sterkte vermeld?</label><select id="annotation-strength-status"><option value="">Kiezen</option><option value="not_stated">Niet vermeld</option><option value="explicit">Ja, expliciet vermeld</option><option value="unmapped">Vermeld, betekenis nog onzeker</option></select>
<label for="annotation-strength">Vermelde sterkte</label><select id="annotation-strength"><option value="">Kiezen</option><option value="strong">Sterk</option><option value="weak">Zwak</option></select>
<button class="btn-secondary" type="button" id="annotation-strength-evidence">Brontekst voor de sterkte aanwijzen</button><p id="annotation-strength-proof"></p></details>
</section>
<section id="annotation-task-3" aria-labelledby="annotation-heading-3" hidden><h3 id="annotation-heading-3" tabindex="-1">Klopt dit?</h3>
<div id="annotation-check" aria-live="polite"></div>
<dl id="annotation-review-summary"></dl>
<details id="annotation-empty" hidden><summary id="annotation-empty-summary"></summary><dl id="annotation-empty-fields"></dl></details>
<button class="btn-secondary" type="button" id="annotation-recheck" hidden>Opnieuw controleren</button></section>
<div id="annotation-required-links" aria-live="polite"></div>
<div id="annotation-selection-tools"><p id="annotation-target" role="status">Wijs de kernuitspraak aan in de bron.</p>
<div class="annotation-selection-actions"><button class="btn-secondary" type="button" id="annotation-select-block">Hele passage aanwijzen</button><button class="btn-secondary" type="button" id="annotation-discard">Selectie wissen</button></div>
<p id="annotation-selection" aria-live="polite"></p><p id="annotation-binding-note" aria-live="polite"></p></div>
<details id="annotation-linked"><summary>Gekoppelde brontekst bekijken of aanpassen</summary><ol id="annotation-ranges"></ol></details>
<p id="annotation-conflict" hidden><a id="annotation-conflict-link" target="_blank" rel="noopener">Bestaande annotatie openen in een nieuw venster</a></p>
<section id="annotation-save-conflict" hidden><h3>Je werk en de opgeslagen versie verschillen</h3><p>Je aanwijzingen blijven hier staan. Vergelijk ze met de opgeslagen versie voordat je kiest wat je behoudt.</p><details><summary>Mijn huidige werk</summary><pre id="annotation-local-work"></pre></details><a id="annotation-server-work" target="_blank" rel="noopener">Bekijk opgeslagen versie in een nieuw venster</a></section>
<button class="btn-secondary" type="button" id="annotation-retry" hidden>Opslaan opnieuw proberen</button>
<div class="annotation-task-actions"><button class="btn-secondary" type="button" id="annotation-back" hidden>Vorige stap</button><button class="btn-primary" type="button" id="annotation-suggest" disabled>Betekenis voorstellen</button><button class="btn-secondary" type="button" id="annotation-add" disabled>Gebruik als kernuitspraak</button><button class="btn-primary" type="button" id="annotation-ready" hidden disabled>Annotatie klaar voor documentcontrole</button><button class="btn-primary" type="button" id="annotation-new" hidden>Volgende annotatie</button><button class="btn-secondary" type="button" id="annotation-finish" hidden>Opslaan en bronselectie beëindigen</button></div>
<details id="annotation-more"><summary>Bewaren, document en meer acties</summary><p>Concepten worden automatisch bewaard. Alleen ‘opgeslagen’ bevestigt serveropslag.</p><div class="actions"><button class="btn-secondary" type="button" id="annotation-pause">Opslaan en later doorgaan</button><button class="btn-secondary" type="button" id="annotation-overview">Documentoverzicht controleren</button><button class="btn-secondary" type="button" id="annotation-withdraw">Hele annotatie terugnemen</button><button class="btn-secondary" type="button" id="annotation-simple-back" hidden>Terug naar de eenvoudige kaart</button></div></details>
<section id="annotation-confirm" hidden aria-labelledby="annotation-confirm-title"><h3 id="annotation-confirm-title" tabindex="-1">Wijziging bevestigen</h3><p id="annotation-confirm-message"></p><button type="button" class="btn-secondary" id="annotation-confirm-cancel">Behouden</button><button type="button" class="btn-secondary" id="annotation-confirm-accept">Wijziging uitvoeren</button></section>
</fieldset></aside></div>
<script type="application/json" id="annotation-data">'''+data+'''</script><script type="module" src="/annotations/editor.js"></script>'''
        css = '''<style>
.annotation-workplace{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(19rem,1fr);gap:1.5rem;align-items:start}
#annotation-editor-inputs{min-width:0;margin:0;padding:0;border:0}
.annotation-document{min-width:0;background:var(--wit);border:1px solid var(--line);border-radius:12px;max-height:calc(100vh - 8rem);overflow:auto}
.annotation-document-tools{position:sticky;top:0;z-index:1;display:flex;align-items:center;gap:.75rem;padding:.75rem 1.5rem;background:var(--wit);border-bottom:1px solid var(--line)}
.annotation-document-tools label{margin:0 0 0 auto!important}.annotation-document-tools select{width:auto;max-width:10rem}
.annotation-page{max-width:76ch;margin:0 auto;padding:2rem 2.25rem;border-bottom:1px solid var(--line)}
.annotation-page-label,.annotation-page-number{font-size:.84rem;color:var(--muted)}.annotation-page-label{margin:0 0 1.75rem}.annotation-page-number{text-align:right;margin:1rem 0 0}
.annotation-document-heading{color:var(--paars);line-height:1.35;margin:2rem 0 .65rem}.annotation-page>.annotation-document-heading:first-of-type{margin-top:0}
.annotation-paragraph,.annotation-list-item{font-size:1rem;line-height:1.75;margin:.25rem 0 1.15rem;overflow-wrap:anywhere}.annotation-list-item{padding-left:1.25rem;text-indent:-1rem;margin-bottom:.45rem}
.annotation-source-text{border-radius:2px;cursor:text;scroll-margin-top:5rem}.annotation-source-text:focus-visible{outline:2px solid var(--paars);outline-offset:3px}.annotation-source-text mark{color:inherit;background:var(--water-soft);border-radius:2px}.annotation-source-text mark[data-current]{background:color-mix(in srgb,var(--paars) 25%,var(--wit))}.annotation-source-text mark[data-annotation]{cursor:pointer}
.annotation-toc{padding:1rem 1.5rem;border-bottom:1px solid var(--line)}.annotation-toc>summary{font-weight:700;color:var(--paars);cursor:pointer}.annotation-toc .annotation-page{padding-inline:.75rem}.annotation-toc-row{line-height:1.6;margin:.35rem 0;overflow-wrap:anywhere}
.annotation-workplace aside{align-self:start;position:sticky;top:1rem;max-height:90vh;overflow:auto;min-width:0;background:var(--wit);border:1px solid var(--line);border-radius:12px;padding:1.25rem}.annotation-workplace aside h2{color:var(--paars)}.annotation-workplace label{display:block;margin-top:1rem}.annotation-workplace select{max-width:100%}.annotation-workplace .btn-secondary{min-height:2.75rem;white-space:normal}.annotation-workplace li{overflow-wrap:anywhere;margin-block:1rem}.annotation-workplace .actions{display:flex;flex-wrap:wrap;gap:.75rem}.annotation-workplace [hidden]{display:none!important}.annotation-workplace ::selection{background:var(--water-soft)}#annotation-controls{scroll-margin-top:6rem}.annotation-mobile-nav{display:none}
@media(max-width:800px){.annotation-mobile-nav{display:flex;flex-wrap:wrap;gap:.75rem;margin-block:1rem;background:var(--wit);padding:.75rem;border:1px solid var(--line);border-radius:12px}.annotation-workplace{grid-template-columns:1fr}.annotation-document{max-height:65vh}.annotation-page{padding:1.25rem}.annotation-workplace aside{position:static;max-height:none}}
.annotation-steps ol{display:flex;gap:.25rem;list-style:none;padding:0;margin:0 0 1rem}.annotation-steps li{flex:1;margin:0}.annotation-steps button{width:100%;min-height:3.5rem;padding:.5rem;border:0;border-bottom:2px solid var(--line);background:transparent;color:var(--muted);text-align:left;font:inherit;font-size:.85rem;line-height:1.35;cursor:pointer}.annotation-steps button[aria-current]{border-color:var(--paars);color:var(--paars);font-weight:700}
#annotation-controls h2{font-size:1.3rem;margin:0 0 1rem}#annotation-controls h3{font-size:1.1rem;line-height:1.4;margin:1.5rem 0 .5rem}#annotation-controls p{line-height:1.5;overflow-wrap:anywhere}#annotation-status{margin:.75rem 0;color:var(--muted);font-size:.9rem;min-height:1.5em}#annotation-core-summary{font-weight:600}#annotation-controls details{margin-block:1rem}#annotation-controls summary{cursor:pointer;min-height:2.75rem;display:list-item;align-content:center}#annotation-fields dt{font-weight:600;margin-top:1.25rem}#annotation-fields dd{margin:.35rem 0 1rem}#annotation-fields dd p{margin:.35rem 0}.annotation-field-actions{display:flex;gap:.5rem;flex-wrap:wrap}.annotation-field-actions select{font-size:1rem}#annotation-target{font-weight:600}#annotation-selection{max-height:10rem;overflow:auto;background:var(--water-soft);padding:.5rem}#annotation-selection:empty{display:none}.annotation-selection-actions{display:flex;gap:.5rem;flex-wrap:wrap}.annotation-task-actions{position:sticky;bottom:0;display:flex;flex-wrap:wrap;gap:.5rem;background:var(--wit);padding-block:1rem;border-top:1px solid var(--line);z-index:2}.annotation-task-actions .btn-primary{flex:1;min-height:2.75rem;white-space:normal}.annotation-task-actions .btn-secondary{flex:0 1 auto}#annotation-check li{margin-block:.5rem}#annotation-review-summary dd,#annotation-empty-fields dd{margin:.25rem 0 1rem;overflow-wrap:anywhere}#annotation-review-summary dt,#annotation-empty-fields dt{font-weight:600}.annotation-row-action{display:inline-block;padding:0 .25rem;border:0;background:none;color:var(--paars);font:inherit;text-decoration:underline;text-underline-offset:.2em;cursor:pointer}.annotation-row-action:focus-visible{outline:2px solid var(--paars);outline-offset:2px}.annotation-open{margin:.35rem 0 .5rem!important;font-weight:600}#annotation-simple-rows dt{font-weight:600;margin-top:1.25rem;display:flex;align-items:center;justify-content:space-between;gap:.75rem;min-height:2.25rem}#annotation-simple-rows dd{margin:.35rem 0 0;overflow-wrap:anywhere}#annotation-simple-rows dd p{margin:.35rem 0}.annotation-hint{color:var(--muted)}.annotation-line{display:flex;gap:.75rem;align-items:flex-start;justify-content:space-between;margin:.35rem 0}.annotation-line p{margin:0!important;min-width:0}.annotation-sign{flex:none;display:inline-grid;place-items:center;width:2.25rem;height:2.25rem;padding:0;border:1px solid var(--paars);border-radius:8px;background:var(--wit);color:var(--paars);font:inherit;font-weight:700;font-size:1.15rem;line-height:1;cursor:pointer}.annotation-sign[aria-pressed=true]{background:var(--paars);color:var(--wit)}.annotation-sign:focus-visible{outline:2px solid var(--paars);outline-offset:2px}@media(pointer:coarse){.annotation-sign{width:2.75rem;height:2.75rem}}#annotation-simple-rows dd>.btn-secondary{margin-top:.35rem}#annotation-finish{flex:1 1 100%}#annotation-simple-notes{padding-left:1.1rem;margin:.5rem 0}#annotation-simple-notes:empty,#annotation-simple-status:empty{display:none}#annotation-simple-type{margin-top:1.25rem}.annotation-signal,.annotation-signals{margin:.35rem 0 .5rem!important;color:var(--muted);font-size:.9rem}.annotation-signals{padding-left:1.1rem}@media(pointer:coarse){.annotation-row-action{min-height:2.75rem}}#annotation-controls dd[data-open]{padding:.75rem;background:var(--water-soft);border-radius:8px}#annotation-local-work{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}#annotation-controls button{touch-action:manipulation}#annotation-controls button:focus-visible,#annotation-controls summary:focus-visible{outline:2px solid var(--paars);outline-offset:3px}#annotation-controls button:active{opacity:.8}
@media(max-width:800px){.annotation-task-actions{padding-bottom:max(1rem,env(safe-area-inset-bottom))}.annotation-steps button{font-size:.8rem}#annotation-controls select{font-size:1rem}.annotation-document{max-height:60dvh}}
</style>'''
        return HTMLResponse(page(nav(actor,'selection')+'<section class="room">'+body+'</section>'+css,title='Bron aanwijzen'),headers={'Cache-Control':'no-store'})

    @app.get('/annotations/editor.js')
    def script(request: Request):
        require(request)
        return Response(Path(__file__).with_name('human_annotation_editor.js').read_text(),media_type='text/javascript',headers={'Cache-Control':'no-store'})

    @app.get('/annotations/binding.mjs')
    def binding_script(request: Request):
        require(request)
        return Response(Path(__file__).with_name('human_annotation_binding.mjs').read_text(),media_type='text/javascript',headers={'Cache-Control':'no-store'})

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
            body += '<p><a href="/annotations?'+esc(urlencode({'document':document,'overview':'true'}))+'">Documentoverzicht opnieuw controleren</a></p>'
            return HTMLResponse(page(nav(actor,'selection')+'<section class="room">'+body+'</section>', title='Document controleren'),
                                status_code=409, headers={'Cache-Control':'no-store'})
        from src.vorming.worker_handover_v1 import native_attempt
        attempt = native_attempt(console, document, receipt['attempt_id'])
        if attempt and attempt['state'] == 'running':
            dispatcher.notify(document, attempt)
        return RedirectResponse('/annotations/build?'+urlencode({'document':document,'attempt':receipt['attempt_id']}), status_code=303)

    def build_status(actor, document, attempt_id):
        envelope = console._envelope(document)
        domain.authorize(console, actor['account_id'], envelope)
        from src.vorming.worker_handover_v1 import native_attempt
        attempt = native_attempt(console, document, attempt_id)
        if not attempt or attempt.get('kind') != 'human_annotation_build':
            raise ConsoleError('annotation_build_unknown')
        state = attempt['state']
        message = ('De kennisobjecten zijn opgebouwd. De bij ontvangst gekozen beoordeling blijft gelden.' if state == 'succeeded'
            else 'De kennisobjecten worden opgebouwd. Je kunt deze pagina verlaten; de opdracht is opgeslagen.' if state == 'running'
            else 'De opbouw is gestopt. Je opgeslagen annotaties zijn bewaard. Controleer het documentoverzicht.')
        return {'state':state, 'message':message, 'title':envelope['title'],
                'detail':ERRORS.get(attempt.get('error_code'), '') if state != 'running' else ''}

    @app.get('/annotations/build/api')
    def get_build_status(request: Request, document: str, attempt: str):
        return JSONResponse(build_status(require(request), document, attempt), headers={'Cache-Control':'no-store'})

    @app.get('/annotations/build', response_class=HTMLResponse)
    def build_page(request: Request, document: str, attempt: str):
        actor = require(request)
        status = build_status(actor, document, attempt)
        body = '<h1>Opbouw van het document</h1><h2>'+esc(status['title'])+'</h2>'
        body += '<p id="annotation-build-status" role="status" aria-live="polite" data-build-state="'+esc(status['state'])+'">'+esc(status['message'])+'</p>'
        body += '<p id="annotation-build-detail">'+esc(status['detail'])+'</p>'
        body += '<p><a id="annotation-build-review"'+(' hidden' if status['state']!='succeeded' else '')+' href="/review?'+esc(urlencode({'document':document}))+'">Kennisobjecten en toepasselijke beoordeling openen</a></p>'
        body += '<p><a href="/annotations?'+esc(urlencode({'document':document,'overview':'true'}))+'">Terug naar documentoverzicht</a></p>'
        body += '<p><a href="'+esc(str(request.url))+'">Status opnieuw laden</a></p>'
        body += '<script src="/annotations/build.js" defer></script>'
        return HTMLResponse(page(nav(actor,'selection')+'<section class="room">'+body+'</section>', title='Opbouw van het document'), headers={'Cache-Control':'no-store'})

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
                command_id=str(form.get('command_id') or uuid4().hex),
                expected_revision=str(form.get('expected_revision') or ''))
        except ConsoleError as exc:
            messages = {
                'annotation_source_storage_not_ready':'De bronvoorbereiding is nog niet beschikbaar. Laat de beheerder de opslag bijwerken.',
                'annotation_processing_in_progress':'Er loopt al een andere verwerking voor dit document. Open Documenten om de voortgang te bekijken.',
                'annotation_objects_stale':'Het document is gewijzigd. Open de bronpagina opnieuw voordat je verdergaat.',
                'processing_admission_closed':'Nieuwe voorbereidingen zijn tijdelijk gepauzeerd. Probeer het later opnieuw.',
                'processing_attempt_limit_reached':'Er zijn meerdere voorbereidingen gestopt. Laat de beheerder de oorzaak controleren voordat je opnieuw probeert.',
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
    def get(request: Request, document: str):
        actor = require(request)
        return JSONResponse(domain.overview(console,actor_id=actor['account_id'],snapshot_id=document),headers={'Cache-Control':'no-store'})

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
            'Controleer de betekenisvelden en de bijbehorende bronselectie.')} for code in result.pop('codes')]
        result['signals'] = [{'code':code,'field':CHECK_FIELDS.get(code),'message':SIGNALS.get(code,
            'Metis kon een onderdeel van deze uitspraak niet vaststellen.')} for code in result.pop('signals')]
        return JSONResponse(result, headers={'Cache-Control':'no-store'})

    @app.post('/annotations/suggest')
    async def suggest(request: Request):
        from starlette.concurrency import run_in_threadpool
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
            status = 409 if code in {'annotation_write_conflict','annotation_command_conflict','annotation_representation_stale','annotation_client_contract_stale','annotation_objects_stale'} else 422
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
