"""Source-first annotation workplace; every saved choice is server-confirmed."""
from html import escape
import json
from pathlib import Path
import re
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
    'annotation_input_storage_not_ready':'Annotaties kunnen nog niet worden opgeslagen. De beheerder moet de annotatieopslag eerst bijwerken. Je aanwijzingen blijven hier zichtbaar.',
    'annotation_write_conflict':'Een andere wijziging is al opgeslagen. Open de opgeslagen versie opnieuw; je huidige aanwijzingen blijven hier zichtbaar.',
    'annotation_command_conflict':'Dit verzoek is al gebruikt met andere keuzes. Open de opgeslagen versie opnieuw.',
    'annotation_anchor_mismatch':'De geselecteerde tekst past niet bij deze bronpositie. Open de bron opnieuw en wijs het bereik opnieuw aan.',
    'annotation_grapheme_boundary_invalid':'De selectie knipt een samengesteld teken door. Selecteer het volledige teken.',
    'annotation_representation_stale':'De bronversie wijkt af. Hervat de oorspronkelijke werkversie; oude selecties worden niet verplaatst.',
    'annotation_evidence_required':'Wijs onderbouwing aan, of leg expliciet vast dat onderbouwing niet van toepassing is.',
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
}


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


def install(app, console, require, page, nav, esc):
    @app.get('/annotations', response_class=HTMLResponse)
    def editor(request: Request, document: str = '', overview: bool = False):
        actor = require(request)
        envelope = console._envelope(document)
        domain.authorize(console, actor['account_id'], envelope)
        if not domain.owns_source(console, document):
            hidden = '<input type="hidden" name="document" value="'+esc(document)+'">'
            hidden += '<input type="hidden" name="expected_revision" value="'+esc(console.objects_revision(document))+'">'
            return HTMLResponse(page(nav(actor,'selection')+'<section class="room"><h1>Bron aanwijzen</h1><h2>'+esc(envelope['title'])+'</h2>'
                '<p>Open de vastgelegde bron om uitspraken, voorwaarden, uitzonderingen en onderbouwing aan te wijzen. Je kunt concepten opslaan en later hervatten.</p>'
                '<p>Annoteren geeft geen goedkeuring. De bij ontvangst gekozen beoordeling blijft gelden.</p>'
                '<form method="post" action="/annotations/source">'+hidden+'<button class="btn-primary" type="submit">Bron openen voor annotatie</button></form></section>',title='Bron aanwijzen'),headers={'Cache-Control':'no-store'})
        state = domain.overview(console, actor_id=actor['account_id'], snapshot_id=document)
        from src.vorming.source_bound_fields_v3 import FIELDS, TYPE_FIELDS
        from src.vorming.human_annotation_v1 import TYPE_CORE_FIELDS
        from src.vorming.source_accountability_v1 import ROLES as SOURCE_ROLES
        state['field_contract']={'fields':list(FIELDS),'labels':FIELD_LABELS,'type_core_fields':TYPE_CORE_FIELDS,
            'type_fields':TYPE_FIELDS,
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
            body += '<p>Ongeselecteerde broninhoud is nog niet verantwoord. Dit overzicht sluit het document niet af en geeft geen publicatierecht.</p>'
            body += '<p><a class="btn-secondary" href="'+escape(back,quote=True)+'">Verder aanwijzen</a></p>'
            return HTMLResponse(page(nav(actor,'selection')+'<section class="room">'+body+'</section>',title='Documentoverzicht'),headers={'Cache-Control':'no-store'})
        blocks = ''.join('<section class="annotation-source-block" tabindex="-1" id="'+esc(b['block_id'])+'"><p class="muted">'+esc(' / '.join(b['section_path']))+'</p>'
            '<p class="muted">'+esc(location_label(b))+'</p>'
            '<p data-source-block="'+esc(b['block_id'])+'" tabindex="0">'+esc(b['text'])+'</p>'
            '<details><summary>Tekstselectie met toetsenbord of touch</summary><label>Brontekst om aan te wijzen<textarea readonly data-source-input="'+esc(b['block_id'])+'" rows="4">'+esc(b['text'])+'</textarea></label></details>'
            '<button class="btn-secondary" type="button" data-select-block="'+esc(b['block_id'])+'">Dit hele tekstblok aanwijzen</button>'
            '<a class="annotation-mobile-link" href="#annotation-controls">Naar huidige annotatie</a></section>' for b in state['blocks'])
        role_options = ''.join('<option value="'+key+'">'+label+'</option>' for key,label in LABELS.items())
        type_options = '<option value="">Type kiezen</option>'+''.join('<option value="'+key+'">'+label+'</option>' for key,label in TYPES.items())+'<option value="source_disposition">Dit bronstuk verantwoorden</option>'
        data = json.dumps(state,ensure_ascii=False).replace('<','\\u003c')
        body = intro + '''<p>Selecteer tekst met de muis of met Shift en de pijltjestoetsen binnen één tekstblok. Voeg een volgend bereik uit een andere alinea toe aan dezelfde annotatie.</p>
<nav class="annotation-mobile-nav" aria-label="Wisselen tussen bron en annotatie"><a id="annotation-to-controls" href="#annotation-controls">Naar huidige annotatie</a><a id="annotation-to-source" href="#'''+esc(state['blocks'][0]['block_id'] if state['blocks'] else '')+'''">Terug naar bron</a></nav>
<div class="annotation-workplace"><div aria-label="Bron in leesvolgorde">'''+blocks+'''</div>
<aside id="annotation-controls" tabindex="-1" aria-label="Huidige annotatie"><label for="annotation-entry">Opgeslagen annotatie</label><select id="annotation-entry"><option value="">Nieuwe annotatie</option></select>
<label for="annotation-type">Type uitspraak</label><select id="annotation-type">'''+type_options+'''</select>
<div id="annotation-source-disposition" hidden><label for="annotation-source-reason">Functie van dit bronstuk</label><select id="annotation-source-reason"></select><p>Dit bewaart een bronrolvoorstel, geen kennisobject of goedkeuring.</p></div>
<label for="annotation-role">Functie van het volgende bereik</label><select id="annotation-role">'''+role_options+'''</select>
<label for="annotation-function">Functie van onderbouwing</label><select id="annotation-function"><option value="supported_by">Onderbouwt de uitspraak</option><option value="explains">Verklaart de uitspraak</option></select>
<label><input type="checkbox" id="annotation-essential"> Dit bereik is essentieel voor de betekenis</label>
<button class="btn-secondary" type="button" id="annotation-add">Geselecteerde tekst toevoegen</button><button class="btn-secondary" type="button" id="annotation-discard">Aanwijzing terugnemen</button><p id="annotation-selection" aria-live="polite"></p>
<ol id="annotation-ranges"></ol><label><input type="checkbox" id="annotation-na">Onderbouwing is niet van toepassing</label>
<div id="annotation-required-links" aria-live="polite"></div>
<details><summary>Betekenis van de uitspraak aanwijzen</summary>
<p>Gebruik de aangewezen brontekst voor een onderdeel van de uitspraak. Je hoeft de tekst niet over te schrijven.</p>
<label for="annotation-field">Onderdeel</label><select id="annotation-field"></select>
<button class="btn-secondary" type="button" id="annotation-bind-field">Aangewezen tekst hiervoor gebruiken</button>
<button class="btn-secondary" type="button" id="annotation-field-absent">Niet in de bron genoemd</button>
<dl id="annotation-fields"></dl></details>
<details id="annotation-recommendation"><summary>Richting en sterkte van de aanbeveling</summary>
<label for="annotation-direction">Richting</label><select id="annotation-direction"><option value="">Kiezen</option><option value="for">Toepassen of overwegen</option><option value="against">Afraden of vermijden</option></select>
<button class="btn-secondary" type="button" id="annotation-direction-evidence">Aangewezen tekst voor de richting gebruiken</button>
<p id="annotation-direction-proof"></p>
<label for="annotation-strength-status">Is de sterkte vermeld?</label><select id="annotation-strength-status"><option value="">Kiezen</option><option value="not_stated">Niet vermeld</option><option value="explicit">Ja, expliciet vermeld</option><option value="unmapped">Vermeld, betekenis nog onzeker</option></select>
<label for="annotation-strength">Vermelde sterkte</label><select id="annotation-strength"><option value="">Kiezen</option><option value="strong">Sterk</option><option value="weak">Zwak</option></select>
<button class="btn-secondary" type="button" id="annotation-strength-evidence">Aangewezen tekst voor de sterkte gebruiken</button><p id="annotation-strength-proof"></p></details>
<p id="annotation-status" role="status" aria-live="polite">Opgeslagen werk geladen.</p>
<div class="actions"><button class="btn-secondary" type="button" id="annotation-ready">Selectie gereed</button><button class="btn-secondary" type="button" id="annotation-new">Volgende annotatie</button>
<button class="btn-secondary" type="button" id="annotation-pause">Opslaan en later doorgaan</button><button class="btn-secondary" type="button" id="annotation-overview">Ik ben klaar met dit document</button><button class="btn-secondary" type="button" id="annotation-withdraw">Annotatie terugnemen</button></div>
<p>Concepten worden automatisch bewaard na een korte pauze. Alleen de melding ‘opgeslagen’ bevestigt serveropslag.</p>
<button class="btn-secondary" type="button" id="annotation-retry" hidden>Opslaan opnieuw proberen</button></aside></div>
<script type="application/json" id="annotation-data">'''+data+'''</script><script src="/annotations/editor.js" defer></script>'''
        css = '<style>.annotation-workplace{display:grid;grid-template-columns:minmax(0,2fr) minmax(18rem,1fr);gap:2rem}.annotation-source-block{margin-block:2rem;max-width:72ch}.annotation-source-block p[data-source-block]{line-height:1.7;white-space:pre-wrap}.annotation-workplace aside{align-self:start;position:sticky;top:1rem;max-height:90vh;overflow:auto}.annotation-workplace label{display:block;margin-top:1rem}.annotation-workplace select{max-width:100%}.annotation-workplace textarea{width:100%;max-width:100%;box-sizing:border-box}.annotation-workplace .btn-secondary{min-height:2.75rem;white-space:normal}.annotation-workplace li{overflow-wrap:anywhere;margin-block:1rem}.annotation-workplace .actions{display:flex;flex-wrap:wrap;gap:.75rem}.annotation-workplace [hidden]{display:none!important}.annotation-workplace ::selection{background:var(--accent-soft,#dbeafe)}#annotation-controls,.annotation-source-block{scroll-margin-top:6rem}.annotation-mobile-nav,.annotation-mobile-link{display:none}@media(max-width:800px){body{padding-bottom:8rem}.annotation-mobile-nav{display:flex;flex-wrap:wrap;gap:.75rem;position:fixed;inset:auto .75rem .75rem;z-index:21;background:var(--surface,#fff);padding:.75rem 4.5rem .75rem .75rem;border:1px solid var(--border,#b7dbe4);border-radius:12px}.annotation-mobile-link{display:block;margin-block:.75rem}.annotation-workplace{grid-template-columns:1fr}.annotation-workplace aside{position:static;max-height:none}}</style>'
        return HTMLResponse(page(nav(actor,'selection')+'<section class="room">'+body+'</section>'+css,title='Bron aanwijzen'),headers={'Cache-Control':'no-store'})

    @app.get('/annotations/editor.js')
    def script(request: Request):
        require(request)
        return Response(Path(__file__).with_name('human_annotation_editor.js').read_text(),media_type='text/javascript',headers={'Cache-Control':'no-store'})

    @app.post('/annotations/source')
    async def prepare_source(request: Request):
        actor = require(request)
        form = await request.form()
        domain.prepare(console,actor_id=actor['account_id'],snapshot_id=str(form.get('document') or ''),expected_revision=str(form.get('expected_revision') or ''))
        return RedirectResponse('/annotations?'+urlencode({'document':str(form.get('document') or '')}),status_code=303)

    @app.get('/annotations/api')
    def get(request: Request, document: str):
        actor = require(request)
        return JSONResponse(domain.overview(console,actor_id=actor['account_id'],snapshot_id=document),headers={'Cache-Control':'no-store'})

    @app.post('/annotations/api')
    async def save(request: Request):
        actor = require(request)
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({'error':'annotation_command_invalid','message':'Open de annotatie opnieuw.'},status_code=422)
        if not isinstance(body,dict) or set(body) != {'snapshot_id','command_id','annotation_id','expected_revision','expected_generation','extraction_hash','normalization','selection'}:
            return JSONResponse({'error':'annotation_command_invalid','message':'Open de annotatie opnieuw.'},status_code=422)
        try:
            result = domain.save(console,actor_id=actor['account_id'],**body)
        except ConsoleError as exc:
            code = exc.code
            status = 409 if code in {'annotation_write_conflict','annotation_command_conflict','annotation_representation_stale','annotation_client_contract_stale'} else 422
            if code in {'not_authenticated','researcher_role_required','reviewer_not_named_on_snapshot'}:
                status = 403
            return JSONResponse({'error':code,'message':ERRORS.get(code,'Opslaan is niet gelukt. Controleer de bronselectie en probeer opnieuw.')},status_code=status)
        return JSONResponse(result,headers={'Cache-Control':'no-store'})

    @app.get('/annotations/original')
    def original(request: Request, document: str):
        actor = require(request)
        envelope = console._envelope(document)
        domain.authorize(console, actor['account_id'], envelope)
        _, data = console._verified_source_bytes(envelope)
        # Download rather than executing received HTML in the authenticated origin.
        return Response(data,media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="source"','Cache-Control':'no-store'})
