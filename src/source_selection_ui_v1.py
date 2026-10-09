"""Source selection room: presentation and dispatch over durable kernel commands."""
import asyncio
import uuid
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.operations_console_v1 import ConsoleError
from src.source_selection_v1 import projection


def _minutes(seconds):
    import math
    if seconds < 60:
        return "minder dan 1 min"
    return f"{max(1, math.ceil(seconds / 60))} min"


def _range(values):
    if values is None:
        return "Onvoldoende gegevens voor een schatting."
    return f"ongeveer {_minutes(values[0])}–{_minutes(values[1])} (onzeker)"


def install(app, console, require, page, nav, esc):
    from src.source_processing_dispatch_v1 import install_dispatcher
    dispatcher = install_dispatcher(app, console)

    @app.get('/source-selection', response_class=HTMLResponse)
    def selection_get(request: Request, document: str = ''):
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
        for envelope in visible:
            sid = envelope['snapshot_id']
            result = projection(console, actor_id=actor['account_id'], snapshot_id=sid, documents=documents)
            action = ''
            if result['state'] == 'bezig':
                action = f'<a class="btn-secondary" href="/source-selection?document={esc(sid)}">Voortgang bekijken</a>'
                running_selected = running_selected or sid == selected
            elif result['state'] == 'voltooid':
                action = f'<a class="btn-secondary" href="/review?document={esc(sid)}">Resultaat bekijken</a>'
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
            summary = ''
            if result['state'] in {'voltooid', 'onderbroken', 'mislukt'}:
                summary = (f'<p>{result["candidates"]} gevormde kandidaten · {result["source_passages"]} overige bronpassages · {result["blocked"]} geblokkeerde kandidaten · {result["formation_blockers"]} verwerkingsblokkades.</p>'
                           f'<p>Poging technisch geslaagd: {"ja" if result["attempt_succeeded"] else "nee"}. '
                           f'Volledige bronverwerking: {"ja" if result["formation_complete"] else "nog niet bevestigd"}.</p>')
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
                         f'{progress}{summary}{action}{review}</article>')
        notice = '<div class="banner ok">Document veilig ontvangen. Start bronselectie wanneer je wilt.</div>' if request.query_params.get('received') == 'yes' else ''
        # Only a selected running document is polled. Every refresh reads the
        # durable authority; no browser state can start another attempt.
        script = '<script>setTimeout(function(){ window.location.reload(); }, 5000);</script>' if running_selected else ''
        script += '<script>document.querySelectorAll("form[action=\\"/source-selection/start\\"]").forEach(function(form){form.addEventListener("submit",function(event){if(form.dataset.submitting){event.preventDefault();return;}form.dataset.submitting="yes";form.querySelector("button").disabled=true;});});</script>'
        return page(nav(actor, 'selection') + '<section class="room" id="source-selection"><h1>Bronselectie</h1>' + notice
                    + '<form method="get"><label>Document<select name="document">' + options + '</select></label><button>Document selecteren</button></form>'
                    + ''.join(sorted(cards, key=lambda card: 'data-selected="true"' not in card)) + '</section>' + script)

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
