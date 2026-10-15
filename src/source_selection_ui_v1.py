"""Source selection room: presentation and dispatch over durable kernel commands."""
from src.request_diagnostics_v1 import diagnostic_phase

import asyncio
import uuid
from urllib.parse import urlencode

from fastapi import Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from src.operations_console_v1 import ConsoleError
from src.source_selection_v1 import UNCHECKED, comparable_observations, projection


def _minutes(seconds):
    import math
    if seconds < 60:
        return "minder dan 1 min"
    return f"{max(1, math.ceil(seconds / 60))} min"


def _range(values):
    if values is None:
        return "Onvoldoende gegevens voor een schatting."
    return f"ongeveer {_minutes(values[0])}–{_minutes(values[1])} (onzeker)"


def _blockage_html(report, esc):
    stages = {'source_formation':'Bronverwerking', 'publication_conditions':'Publicatievoorwaarden',
              'identity_verification':'Eerst controleren of het bewijs bij hetzelfde document hoort',
              'not_established':'Nog niet vastgesteld'}
    counts = report['finding_counts']
    body = '<h1>Blokkade en bewijs</h1><p>Hier zie je wat is vastgelegd, wat nog openstaat en welk bewijs ontbreekt.</p>'
    body += '<h2>Eerst te onderzoeken</h2><p>' + esc(stages[report['next_blocking_stage']]) + '</p>'
    pending = report['formation_progress']['pending_task_count']
    body += f'<p>Open verwerkingstaken: {esc(pending) if pending is not None else "niet vastgelegd"}. '
    body += f'Actuele afwijzingen: {counts.get("pending", 0)}. Historische afwijzingen: {counts.get("historical", 0)}.</p>'
    selected = report['selected_attempt_result']
    if selected:
        states = {'succeeded':'technisch geslaagd', 'failed':'mislukt', 'interrupted':'onderbroken', 'running':'als actief opgeslagen'}
        body += '<h2>Gekozen poging</h2><p>Status: ' + esc(states.get(selected['stored_state'], 'onbekend')) + '.</p>'
        if selected['error']:
            body += '<p>' + esc(selected['error']['title']) + ' · controlecode: ' + esc(selected['error']['code'] or 'onbekend') + '.</p>'
        body += '<p>Deze poging is apart weergegeven; het huidige document kan inmiddels verder zijn verwerkt.</p>'
    for item in report['blockers']:
        body += '<h3>' + esc(item['title']) + '</h3><p>' + esc(item['expected_condition'] or 'De controlevoorwaarde is nog niet verklaard.') + '</p>'
    body += '<h2>Vervolgvoorwaarden</h2><p>Dit betreft de getoonde controles. Bij uitvoering controleert Metis alle opdrachtvoorwaarden en bevoegdheden opnieuw.</p><ul>'
    for action in report['follow_up']:
        value = action['observed_conditions_met']
        label = {'resume':'Hervatten', 'retry':'Opnieuw proberen', 'review_obligations':'Openstaande reviewverplichtingen bekijken'}[action['action']]
        status = 'vervolgstap voor de toegewezen reviewer' if action['action'] == 'review_obligations' else 'gecontroleerde voorwaarden voldaan' if value is True else 'gecontroleerde voorwaarden niet voldaan' if value is False else 'nog niet gecontroleerd of inmiddels verouderd'
        body += '<li>' + label + ': ' + status + '</li>'
    body += '</ul><h2>Bewijs en onzekerheid</h2><p>Een technisch geslaagde poging bevestigt op zichzelf geen volledige bronverwerking of publicatiegereedheid.</p>'
    for problem in report['identity_conflicts']:
        body += '<p role="alert">Bewijs hoort mogelijk niet bij dezelfde toestand: ' + esc(problem) + '</p>'
    body += '<details><summary>Vastgelegde bevindingen en bewijsverwijzingen</summary><ol>'
    states = {'pending':'nog open', 'historical':'historisch', 'unknown':'actualiteit onbekend',
              'stored_candidate_admission':'opgeslagen kandidaatcontrole; geen publicatiebesluit'}
    for item in report['findings']:
        refs = ', '.join(str(ref.get('dataset')) + ' · gegevensrij ' + str(ref.get('row')) for ref in item['evidence_refs'])
        body += '<li>' + esc(item['title']) + ' — ' + esc(states[item['scope']])
        body += '<p>' + esc(item['expected_condition'] or 'Voor deze code is nog geen verklaring vastgelegd.') + '</p>'
        body += '<p>Controlecode: ' + esc(item['code'] or 'onbekend') + '. Bewijs: ' + esc(refs) + '.</p></li>'
    body += '</ol></details><details><summary>Ontbrekende gegevens en controle-uitkomsten</summary><ul>'
    body += ''.join('<li>' + esc(value) + '</li>' for value in report['missing_evidence'])
    for key, value in report['current_checks']['errors'].items():
        body += '<li>' + esc(key) + ': ' + esc(value) + '</li>'
    return body + '</ul></details>'


def install(app, console, require, page, nav, esc):
    from src.source_processing_dispatch_v1 import install_dispatcher
    dispatcher = install_dispatcher(app, console)

    @app.get('/source-selection', response_class=HTMLResponse)
    @console.source_selection_read_scope()
    def selection_get(request: Request, document: str = ''):
        with diagnostic_phase("authorization"):
            actor = require(request)
        receipts = console.list_envelopes()
        documents = [console._envelope(row['snapshot_id']) for row in receipts]
        visible = [row for row in documents if "researcher" in actor['roles'] or actor['account_id'] in row.get('named_reviewers', [])]
        if document and document not in {row['snapshot_id'] for row in visible}:
            raise ConsoleError('reviewer_not_named_on_snapshot')
        selected = document or (visible[-1]['snapshot_id'] if visible else '')
        options = ''.join(f'<option value="{esc(row["snapshot_id"])}" {"selected" if row["snapshot_id"] == selected else ""}>{esc(row["title"])} — {esc(row["version"])}</option>' for row in visible)
        cards = []
        running_selected = False
        # Eén keer per verzoek (PR-b): vergelijkbare metingen over alle documenten.
        observations = comparable_observations(documents)
        for envelope in visible:
            sid = envelope['snapshot_id']
            # Volledige controle alleen voor het expliciet gekozen document (D-PERF-2).
            result = projection(console, actor_id=actor['account_id'], snapshot_id=sid, documents=documents,
                                deep=bool(document) and sid == document, observations=observations)
            action = ''
            if result['state'] in {'bezig', 'wacht op uitvoering'}:
                action = f'<a class="btn-secondary" href="/source-selection?document={esc(sid)}">Voortgang bekijken</a>'
                running_selected = running_selected or sid == selected
            elif result['state'] == 'voltooid':
                action = f'<a class="btn-secondary" href="/review?document={esc(sid)}">Resultaat bekijken</a>'
            elif result['state'] == UNCHECKED:
                action = f'<a class="btn-secondary" href="/source-selection?document={esc(sid)}">Volledigheid controleren</a>'
            elif result['can_start']:
                label = 'Starten' if result['state'] == 'nog niet gestart' else 'Hervatten'
                action = (f'<form method="post" action="/source-selection/start">'
                          f'<input type="hidden" name="document" value="{esc(sid)}">'
                          f'<input type="hidden" name="expected_revision" value="{esc(result["revision"])}">'
                          f'<input type="hidden" name="command_id" value="{uuid.uuid4().hex}">'
                          f'<button class="btn-primary">{label}</button></form>')
            else:
                action = '<p>Hervatten is nu niet beschikbaar. Controleer de bron- en reviewvoorwaarden bij technisch beheer.</p>'
            progress = ''
            if result['state'] == 'bezig':
                elapsed = result['elapsed_seconds']
                phase = {'source_and_validation': 'Bron lezen en controleren', 'reserved': 'Gereserveerd',
                         'extraction_started': 'Brontekst uitlezen', 'extraction_finished': 'Brontekst beschikbaar',
                         'model_request': 'Bronpassages selecteren', 'model_response': 'Selectie controleren',
                         'proposal_received': 'Kandidaten controleren', 'activated': 'Resultaat opgeslagen',
                         'validation_started': 'Brongetrouwheid voorbereiden',
                         'source_reconstructed': 'Bronpassages reconstrueren', 'response_received': 'Modelantwoord ontvangen',
                         'proposal_parsed': 'Voorstel controleren', 'evidence_resolved': 'Bronvelden en relaties controleren',
                         'formation_accounted': 'Brondekking controleren', 'stopped': 'Verwerking gestopt'}.get(result['phase'], 'Bronselectie en controle')
                progress = (f'<p>Fase: {esc(phase)} · Verstreken: {esc(_minutes(elapsed)) if elapsed is not None else "onbekend"}'
                            f' · Geschat resterend: {esc(_range(result["remaining_seconds"]))}</p>')
            if result['state'] == 'wacht op uitvoering':
                elapsed = result['elapsed_seconds']
                deadline = result['deadline_seconds']
                progress = (f'<p>Wacht op een uitvoeringsplek of conversiecapaciteit. '
                            f'Verstreken sinds aanvraag: {esc(_minutes(elapsed)) if elapsed is not None else "onbekend"}. '
                            f'Resterende totale tijdslimiet: {esc(_minutes(deadline)) if deadline is not None else "onbekend"}.</p>'
                            '<p>De tijdslimiet loopt vanaf de aanvraag. Verloopt deze tijdens wachten, '
                            'dan telt deze poging mee voor de herstelgrens. De geschatte verwerkingstijd bevat ook wachttijd.</p>')
            summary = ''
            if result['state'] in {'voltooid', 'onderbroken', 'mislukt', UNCHECKED}:
                summary = (f'<p>{result["candidates"]} gevormde kandidaten · {result["source_passages"]} overige bronpassages · {result["blocked"]} geblokkeerde kandidaten · {result["formation_blockers"]} verwerkingsblokkades.</p>'
                           f'<p>Poging technisch geslaagd: {"ja" if result["attempt_succeeded"] else "nee"}. '
                           f'Volledige bronverwerking: {"ja" if result["formation_complete"] else "nog niet bevestigd"}.</p>')
            trace_link = f'<a class="btn-secondary" href="/source-selection/processing-trace?document={esc(sid)}">Verwerkingsspoor downloaden</a>'
            trace_link += f'<a class="btn-secondary" href="/source-selection/blockage?document={esc(sid)}">Blokkade en bewijs bekijken</a>'
            review = f'<a class="btn-primary" href="/review?document={esc(sid)}">Naar Review</a>' if result['review_available'] else ''
            extent = f'{result["bytes"]:,} bytes' if result['bytes'] is not None else 'Bestandsgrootte onbekend'
            records = (envelope.get('quality_processing_runs') or [])
            if records:
                extent += f' · {len(records[-1].get("source_fragments", []))} opgeslagen bronfragmenten'
            cards.append(f'<article class="doc-card" id="source-{esc(sid)}" data-source-document="{esc(sid)}" data-selected="{str(sid == selected).lower()}">'
                         f'<h2>{esc(result["title"])}</h2><p>{esc(result["filename"])} · Bronversie {esc(result["version"])} · {esc(extent)}</p>'
                         f'<p role="status">Status: {esc(result["state"])}</p>'
                         f'<p>Geschatte verwerkingstijd: {esc(_range(result["estimate"]["range_seconds"]))} '
                         f'{esc(result["estimate"]["basis"])} ({result["estimate"]["sample_count"]} metingen)</p>'
                         f'{progress}{summary}{action}{review}{trace_link}</article>')
        notice = '<div class="banner ok">Document veilig ontvangen. Start bronselectie wanneer je wilt.</div>' if request.query_params.get('received') == 'yes' else ''
        # Only a selected running document is polled. Every refresh reads the
        # durable authority; no browser state can start another attempt.
        script = '<script>setTimeout(function(){ window.location.reload(); }, 5000);</script>' if running_selected else ''
        script += '<script>document.querySelectorAll("form[action=\\"/source-selection/start\\"]").forEach(function(form){form.addEventListener("submit",function(event){if(form.dataset.submitting){event.preventDefault();return;}form.dataset.submitting="yes";form.querySelector("button").disabled=true;});});</script>'
        return page(nav(actor, 'selection') + '<section class="room" id="source-selection"><h1>Bronselectie</h1>' + notice
                    + '<form method="get"><label>Document<select name="document">' + options + '</select></label><button>Document selecteren</button></form>'
                    + ''.join(sorted(cards, key=lambda card: 'data-selected="true"' not in card)) + '</section>' + script)

    @app.get('/source-selection/processing-trace')
    def processing_trace_export(request: Request, document: str = ''):
        from src.source_selection_v1 import authorize
        from src.processing_trace_v1 import processing_trace
        actor = require(request)
        envelope = console._envelope(document)
        authorize(console, actor['account_id'], envelope)
        return JSONResponse(processing_trace(envelope), headers={'Cache-Control': 'no-store',
            'Content-Disposition': 'attachment; filename=processing-trace.json'})

    @app.get('/source-selection/publication-evidence')
    def publication_evidence_get(request: Request, document: str = ''):
        from src.publication_evidence_v1 import collect_publication
        actor = require(request)
        return JSONResponse(collect_publication(console, actor_id=actor['account_id'], snapshot_id=document),
            headers={'Cache-Control':'no-store',
                     'Content-Disposition':'attachment; filename=publication-evidence.json'})

    @app.get('/source-selection/blockage')
    def blockage_get(request: Request, document: str = '', checks: bool = False,
                     download: bool = False, attempt: str = Query('', pattern=r'^(?:pa_[0-9a-f]{32})?$')):
        from src.blockage_diagnostics_v1 import collect_blockage
        actor = require(request)
        report = collect_blockage(console, actor_id=actor['account_id'], snapshot_id=document,
                                 current_checks=checks, selected_attempt=attempt or None)
        if download:
            return JSONResponse(report, headers={'Cache-Control':'no-store',
                'Content-Disposition':'attachment; filename=blockage-report.json'})
        query = {'document':document, **({'attempt':attempt} if attempt else {})}
        selector = '<form method="get"><input type="hidden" name="document" value="' + esc(document) + '"><label>Verwerkingspoging<select name="attempt"><option value="">Documentgegevens zonder een poging te kiezen</option>'
        for row in report['attempts']:
            if row['attempt_id']:
                selected = ' selected' if row['attempt_id'] == report['selected_attempt_id'] else ''
                selector += '<option value="' + esc(row['attempt_id']) + '"' + selected + '>' + esc((row['started_at'] or 'Tijd niet vastgelegd') + ' · ' + (row['stored_state'] or 'onbekend') + ' · ' + row['attempt_id'][-8:]) + '</option>'
        selector += '</select></label><button>Bewijs van deze poging bekijken</button></form>'
        links = '<p><a href="?' + esc(urlencode({**query, 'checks':1})) + '">Actuele voorwaarden controleren</a></p>'
        links += '<p><a href="?' + esc(urlencode({**query, 'download':1})) + '">Opgeslagen bewijs downloaden</a></p>'
        links += '<p><a href="?' + esc(urlencode({**query, 'checks':1, 'download':1})) + '">Opnieuw controleren en rapport downloaden</a></p>'
        return HTMLResponse(page(nav(actor, 'selection') + '<section class="room" id="blockage-report" style="overflow-wrap:anywhere">' +
            _blockage_html(report, esc) + selector + links + '</section>'), headers={'Cache-Control':'no-store'})

    @app.post('/source-selection/start')
    async def selection_start(request: Request):
        actor = require(request)
        form = await request.form()
        sid = str(form.get('document') or '')
        try:
            attempt, fresh = await asyncio.to_thread(console.reserve_source_selection,
                actor_id=actor['account_id'], snapshot_id=sid, command_id=str(form.get('command_id') or ''),
                expected_revision=str(form.get('expected_revision') or ''))
        except ConsoleError as exc:
            if exc.code != 'processing_attempt_in_progress':
                raise
            return RedirectResponse('/source-selection?' + urlencode({'document': sid}), status_code=303)
        # A wake is only a hint. The kernel recovers durable pending attempts
        # at startup and on its bounded poll, even if this request disappears.
        if attempt["state"] == "running":
            dispatcher.notify(sid, attempt)
        return RedirectResponse('/source-selection?' + urlencode({'document': sid}), status_code=303)
