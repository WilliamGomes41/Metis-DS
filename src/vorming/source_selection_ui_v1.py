"""Source selection room: presentation and dispatch over durable kernel commands."""
from src.request_diagnostics_v1 import diagnostic_phase

import asyncio
import json
from html import escape
import uuid
from urllib.parse import urlencode

from fastapi import HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from src.operations_console_v1 import ConsoleError
from src.vorming.source_selection_v1 import (
    UNCHECKED, comparable_observations, progress_attempt_key, projection, summary_projection,
)
from src.vorming.knowledge_materialisation_v1 import source_reconstruction_scope


def _source_pages_html(envelope: dict, diagnostic: dict, document: str, *, editable=False, draft=None) -> str:
    """Existing page evidence; only Vorming explicitly enables the accounting form."""
    draft = draft or {}
    from src.vorming.docling_contract_v1 import DoclingError, set_aside_pages
    from src.operations_console_app import PAGE_FINDING_COPY
    from src.operations_console_v1 import ConsoleError, SOURCE_PAGE_ACCOUNTING_CATEGORIES
    parts = []
    findings = diagnostic.get("page_findings") or []
    if findings:
        options = "".join(f'<option value="{escape(key)}">{escape(label)}</option>'
                          for key, label in SOURCE_PAGE_ACCOUNTING_CATEGORIES.items())
        rows = []
        for row in findings:
            copy = [PAGE_FINDING_COPY.get(code, (code, "Meld dit bij de beheerder.")) for code in row.get("reasons") or []]
            problem = " ".join(problem for problem, _ in copy)
            action = " ".join(dict.fromkeys(action for _, action in copy))
            accounted = any(done["page"] == row["page"] and done["reasons"] == row.get("reasons")
                            and done["source_sha256"] == envelope.get("sha256")
                            for done in envelope.get("source_page_accountings") or [])
            if accounted:
                rows.append(f'<tr id="source-page-{int(row["page"])}"><td>Pagina {int(row["page"])}</td><td>{escape(problem)}</td><td>{escape(action)}</td>'
                            '<td>Verantwoord; start de verwerking opnieuw.</td></tr>')
                continue
            if editable:
                selected = str(draft.get('category') or '') if str(draft.get('page')) == str(row['page']) else ''
                page_options = options.replace('value="' + escape(selected) + '"', 'value="' + escape(selected) + '" selected') if selected else options
                rows.append(f'''<tr id="source-page-{int(row["page"])}"><td>Pagina {int(row["page"])}</td><td>{escape(problem)}</td><td>{escape(action)}</td>
              <td><form method="post" action="/inzicht/document/pagina-verantwoorden">
                <input type="hidden" name="snapshot_id" value="{escape(document, quote=True)}">
                <input type="hidden" name="page" value="{int(row["page"])}">
                <label>Reden<select name="category" required>{page_options}</select></label>
                <label>Toelichting<input name="note" value="{escape(str(draft.get("note") or ""), quote=True) if str(draft.get("page")) == str(row["page"]) else ""}" required minlength="10" maxlength="500"></label>
                <button type="submit">Pagina verantwoorden</button></form></td></tr>''')
            elif envelope['class'] == 'beslisboom':
                owner = '/source-selection?' + urlencode({'document': document}) + '#source-page-' + str(int(row['page']))
                rows.append(f'<tr><td>Pagina {int(row["page"])}</td><td>{escape(problem)}</td><td>{escape(action)}</td>'
                            f'<td><a href="{escape(owner, quote=True)}">Pagina verantwoorden in Vorming</a></td></tr>')
            else:
                rows.append(f'<tr><td>Pagina {int(row["page"])}</td><td>{escape(problem)}</td><td>{escape(action)}</td><td>Open</td></tr>')
        parts.append('<section id="paginas"><h3>Onopgeloste pagina’s</h3>'
                     + ('<p>Verantwoord alleen een pagina zonder kennisinhoud in Vorming. Start daarna de verwerking opnieuw.</p>'
                        if envelope['class'] == 'beslisboom' else '')
                     + '<table><thead><tr><th>Pagina</th><th>Probleem</th><th>Herstelactie</th><th>Verantwoorden</th></tr></thead>'
                     f'<tbody>{"".join(rows)}</tbody></table></section>')
    # Accepted-extraction evidence belongs to Inzicht. Vorming only needs
    # current findings/accountings; reading it here would repeat collect's read.
    left_out = []
    if not editable:
        try:
            left_out = set_aside_pages(envelope)
        except (DoclingError, ConsoleError):
            left_out = []
    if left_out:
        labels = {"pdf_page_without_content": "leeg volgens de PDF", "recorded_accounting": "verantwoord"}
        listed = "; ".join(f'pagina {int(row["page"])} ({labels.get(row.get("basis"), "onbekend")})' for row in left_out)
        parts.append(f'<p>Buiten de bron gelaten pagina’s: {escape(listed)}.</p>')
    accountings = envelope.get("source_page_accountings") or []
    if accountings:
        items = "".join(f'<li>Pagina {int(row["page"])}: {escape(SOURCE_PAGE_ACCOUNTING_CATEGORIES.get(row["category"], row["category"]))}'
                        f' — {escape(row["note"])} ({escape(row["recorded_at"][:10])})</li>' for row in accountings)
        parts.append(f'<details><summary>Vastgelegde verantwoordingen ({len(accountings)})</summary><ul>{items}</ul></details>')
    return "".join(parts)


def source_recovery_controls(envelope, processing, account, *, draft=None, error=''):
    """Pure form composition over already-read source/processing inputs; no authority."""
    draft = draft or {}
    sid = envelope['snapshot_id']
    roles = set(account.get('roles') or [])
    code = ('source_formation_incomplete' if processing.get('formation_incomplete') else
            processing.get('error_code') or processing.get('reason_code') or '')
    blocking_code = ('' if processing.get('state') == 'succeeded' and not processing.get('formation_incomplete')
                     and not processing.get('error_code') else code)
    from src.settings.insight_v1 import _DIAGNOSIS_UNFINISHED_STATES
    blocked = bool(blocking_code) or processing.get('state') in _DIAGNOSIS_UNFINISHED_STATES
    controls = ''
    if ('publisher' in roles and (account['account_id'] in envelope.get('named_reviewers', [])
            or account['account_id'] == envelope.get('uploader_account_id'))
            and processing.get('reason_code') == 'processing_attempt_limit_reached'
            and blocked and not envelope.get('processing_recovery')):
        controls += ('<h3>Eenmalig herstel autoriseren</h3><p>Autoriseren start geen verwerking. Starten of Hervatten blijft een afzonderlijke handeling.</p>'
            '<form method="post" action="/tree/processing-recovery">'
            '<input type="hidden" name="snapshot_id" value="' + escape(sid, quote=True) + '">'
            '<label>Reden voor eenmalig herstel<input name="reason" value="' + escape(str(draft.get('reason') or ''), quote=True) + '" required maxlength="1000"></label>'
            '<button type="submit">Een herstelpoging autoriseren</button></form>')
    if envelope.get('processing_recovery'):
        controls += '<p>Een herstelpoging is geautoriseerd. Alleen expliciet Starten of Hervatten kan deze autorisatie gebruiken.</p>'
    attempts = envelope.get('processing_attempts') or []
    diagnostic = (attempts[-1].get('diagnostic') or {}) if attempts else {}
    pages = _source_pages_html(envelope, diagnostic, sid, editable=True, draft=draft)
    if not (controls or pages or error):
        return ''
    failure = ''
    if error:
        from src.operations_console_app import ERROR_COPY
        failure = '<div class="banner warn" role="alert">Niet opgeslagen: ' + escape(ERROR_COPY.get(error, error)) + '</div>'
        pending = ''.join('<dt>' + label + '</dt><dd>' + escape(str(draft[key])) + '</dd>'
                          for key, label in (('page', 'Ingediende pagina'), ('category', 'Categorie'),
                                             ('note', 'Toelichting'), ('reason', 'Reden')) if draft.get(key))
        if pending:
            failure += '<aside data-unsaved-source-draft><h3>Niet opgeslagen invoer</h3><dl>' + pending + '</dl></aside>'
    mobile = """<style>@media(max-width:640px){
      #processing-recovery table,#processing-recovery tbody,#processing-recovery tr,#processing-recovery td{
        display:block;width:100%;box-sizing:border-box}
      #processing-recovery thead{display:none}
      #processing-recovery td{border:0;padding:.35rem 0}
      #processing-recovery tr{margin:1rem 0;padding:.5rem;border:1px solid var(--border,#ccc)}
      #processing-recovery td:first-child{font-weight:bold}
      #processing-recovery input,#processing-recovery select,#processing-recovery button{
        width:100%;max-width:100%;min-width:0;box-sizing:border-box}
    }</style>""" if pages else ''
    return mobile + '<section id="processing-recovery" data-source-recovery>' + failure + controls + pages + '</section>'

def _minutes(seconds):
    import math
    if seconds < 60:
        return "minder dan 1 min"
    return f"{max(1, math.ceil(seconds / 60))} min"


def _range(values):
    if values is None:
        return "Onvoldoende gegevens voor een schatting."
    return f"ongeveer {_minutes(values[0])}–{_minutes(values[1])} (onzeker)"


def _size(count):
    """File size in Dutch notation: bytes below 1 kB, then kB or MB with one decimal."""
    if count < 1000:
        return f"{count}\u00a0bytes"
    value, unit = (count / 1_000_000, "MB") if count >= 1_000_000 else (count / 1000, "kB")
    return f"{value:.1f}\u00a0{unit}".replace(".", ",")


def _formation_groups(rows):
    """Group only known identical source ranges; never infer unknown scope."""
    grouped = {}
    for row in rows:
        key = (tuple((s['block_id'], s['start'], s['end']) for s in row['spans'])
               if row.get('source_excerpt') else row['problem_id'])
        grouped.setdefault(key, []).append(row)
    return sorted(grouped.values(), key=lambda group: (
        (group[0].get('source_excerpt') or {}).get('order', [10**9, 0]), group[0]['problem_id']))


def _formation_problem_html(group, esc):
    first = group[0]
    excerpt = first.get('source_excerpt')
    title = (excerpt.get('location') or 'Bronfragment') if excerpt else (
        'Pagina ' + str(first['page']) if first.get('page') is not None else 'Bronstuk nog niet vastgesteld')
    body = '<article class="formation-item" id="problem-' + first['problem_id'] + '">'
    body += ''.join('<span id="problem-' + row['problem_id'] + '"></span>' for row in group[1:])
    body += '<h3>' + esc(title) + '</h3>'
    if excerpt:
        for quote in excerpt['quotes']:
            body += '<blockquote class="formation-quote"><p>' + esc(quote['text']) + '</p></blockquote>'
            if quote['truncated']:
                body += '<p class="muted">Dit is een fragment. Open het bronstuk om de volledige tekst te lezen.</p>'
    else:
        body += '<p class="formation-unlocated">Er is nog geen exact bronfragment beschikbaar bij deze melding.</p>'

    def reason(row):
        copy = {
            'semantic_evidence_literal_not_found': 'Metis kon het bewijs bij het voorstel niet terugvinden in dit bronstuk.',
            'uncertain_source_role': 'Voor deze tekst moet nog worden bepaald hoe hij wordt gebruikt.',
        }.get(row['code'], row['expected_condition'] or 'Bekijk de herstelvoorwaarden om te bepalen wat er nodig is.')
        return '<p class="formation-reason"><strong>' + esc(row['title']) + '</strong><br>' + esc(copy) + '</p>'

    body += reason(first)
    if len(group) > 1:
        n = len(group) - 1
        body += '<details class="formation-related"><summary>' + str(n) + (
            ' andere melding bij dit bronstuk' if n == 1 else ' andere meldingen bij dit bronstuk') + '</summary>'
        body += ''.join(reason(row) for row in group[1:]) + '</details>'
    actions = {}
    for row in group:
        for action in row['actions']:
            actions.setdefault(action['url'], action)
    direct = [a for a in actions.values() if not a['url'].startswith('/inzicht/')]
    labels = {'Bronbereik bekijken en behandelen': 'Bekijk en behandel dit bronstuk',
              'Brongebruik bepalen of herstellen': 'Bekijk en behandel dit bronstuk',
              'Diagnose en herstelvoorwaarden': 'Bekijk de herstelvoorwaarden'}
    primary = direct[0] if direct else None
    if primary:
        body += '<p class="formation-next"><a href="' + esc(primary['url']) + '">' + esc(
            labels.get(primary['label'], primary['label'])) + '</a></p>'
    if len(direct) > 1:
        body += '<details class="formation-related"><summary>Andere handelingen</summary><ul>'
        body += ''.join('<li><a href="' + esc(a['url']) + '">' + esc(labels.get(a['label'], a['label'])) +
                        '</a></li>' for a in direct[1:]) + '</ul></details>'
    body += '<details class="formation-technical"><summary>Technische details</summary>'
    for row in group:
        spans = ', '.join(str(s['block_id']) + ' [' + str(s['start']) + '–' + str(s['end']) + ')' for s in row['spans'])
        body += '<p><strong>' + esc(row['title']) + '</strong><br>Controlecode: <code>' + esc(
            row['code'] or 'onbekend') + '</code><br>Bronbereik: ' + esc(spans or 'nog niet exact vastgesteld') + '</p>'
    return body + '</details></article>'


def _formation_problems_html(report, *, offset, esc, work_revision_url=None):
    sid = report['snapshot_id']
    status = report['processing']
    query = {'document': sid}
    rows = report['problems']
    groups = _formation_groups(rows)
    body = '<header class="formation-header"><h2>Vormingsproblemen</h2>'
    body += '<p class="muted">Bronversie ' + esc(report['version']) + '</p></header>'
    body += '<p class="formation-intro">Bekijk de bronstukken die nog aandacht nodig hebben.</p>'
    if status.get('resume_allowed') or status.get('retry_allowed'):
        hint = ('Metis kan het open werk opnieuw proberen. Geldige voorstellen blijven bewaard.'
                if status.get('resume_allowed') else 'Start de bronverwerking om te bepalen welke tekst naar Review kan.')
        body += '<p class="formation-recovery">' + hint + '</p>'
    elif status.get('state') == 'running':
        body += '<section class="formation-recovery"><h3>Metis verwerkt de bron</h3><p>Je kunt andere kamers openen. De verwerking loopt door.</p></section>'
    elif status.get('formation_incomplete'):
        body += '<p class="formation-recovery">Opnieuw verwerken is nu niet beschikbaar. Gebruik de handelingen bij de bronstukken hieronder. Menselijke beoordelingen blijven beschermd.</p>'
        if work_revision_url:
            body += '<p><a href="' + esc(work_revision_url) + '">Nieuwe werkrevisie voorbereiden</a></p>'
    if rows:
        located = sum(bool(group[0].get('source_excerpt')) for group in groups)
        unknown = len(groups) - located
        body += '<section class="formation-findings" aria-labelledby="formation-findings-title"><h2 id="formation-findings-title">Te behandelen</h2>'
        count = str(located) + (' bronstuk' if located == 1 else ' bronstukken') if located else ''
        if unknown:
            count += (' · ' if count else '') + str(unknown) + (' melding zonder exact bronfragment' if unknown == 1 else ' meldingen zonder exact bronfragment')
        if located:
            count += ' · ' + str(len(rows)) + (' melding' if len(rows) == 1 else ' meldingen')
        body += '<p class="muted">' + count + '</p>'
        body += ''.join(_formation_problem_html(group, esc) for group in groups[offset:offset + 100])
        body += '<p class="formation-publication">Geldige voorstellen kun je alvast beoordelen in Review. Open bronproblemen blijven publicatie blokkeren.</p></section>'
        for label, position in [('Vorige bronstukken', max(0, offset - 100)), ('Volgende bronstukken', offset + 100)]:
            if label.startswith('Vorige') and offset or label.startswith('Volgende') and offset + 100 < len(groups):
                body += '<p><a href="?' + esc(urlencode({**query, 'offset': position})) + '">' + label + '</a></p>'
    elif status.get('state') == 'running':
        body += '<section class="formation-empty"><h2>Nog geen meldingen</h2><p>Bronstukken die aandacht nodig hebben verschijnen hier zodra ze zijn vastgesteld.</p></section>'
    elif status.get('state') == 'not_recorded':
        body += '<section class="formation-empty"><h2>Nog geen verwerkingsresultaat</h2><p>Na bronverwerking zie je hier welke bronstukken aandacht nodig hebben.</p></section>'
    else:
        body += '<section class="formation-empty"><h2>Geen open vormingsproblemen</h2><p>Je kunt verder in Review. Voor publicatie blijven de overige review- en publicatievoorwaarden gelden.</p></section>'
    return body


def _estimate(estimate):
    """One short paragraph: the range, or that there is none yet, then its basis and sample count."""
    if estimate["range_seconds"] is None:
        return (f'Geschatte verwerkingstijd: nog geen schatting. '
                f'{estimate["basis"].rstrip(".")} ({estimate["sample_count"]}).')
    return (f'Geschatte verwerkingstijd: {_range(estimate["range_seconds"])}. '
            f'{estimate["basis"]} Op basis van {estimate["sample_count"]} metingen.')


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
        states = {'succeeded':'technisch geslaagd', 'failed':'mislukt', 'interrupted':'onderbroken', 'incomplete_budget':'gestopt op taakbudget', 'running':'als actief opgeslagen'}
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



@source_reconstruction_scope(reuse_existing=True)
def render_source_accountability(console, account, document):
    """Move the existing document inventory and exclusion form as one view."""
    from src import operations_console_app as ui
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    console._require_role(account['account_id'], 'reviewer')
    envelope = console._envelope(document)
    if account['account_id'] not in envelope.get('named_reviewers', []):
        raise ConsoleError('reviewer_not_named_on_snapshot')
    if getattr(console, 'workflow_document_store', None) is not None:
        from src.review.review_passage_read_v1 import read_review_document
        inputs = read_review_document(console, account, document, current_only=True)
        envelope, objects, revision, bindings = inputs.envelope, inputs.objects, inputs.revision, inputs.bindings
        fragments = inputs.fragments
    else:
        objects, revision = console.snapshot_objects_and_revision(document)
        bindings = ui._review_bindings(console, document, objects=objects)
        fragments = console.review_source_fragments(document)
    panel = ui._review_inventory(document, objects,
        review_path=review_path_for_klasse(envelope['class']), bindings=bindings,
        reviewer_id=account['account_id'], task='inventory', snapshot_revision=revision,
        fragments=fragments, source_only=True,
        edit_exclusions=not console.snapshot_is_published(document))
    overview = '/source-selection?' + urlencode({'document': document})
    review = '/review?' + urlencode({'document': document})
    return ui._page(ui._nav(account, 'selection') +
        '<section class="room review-room" data-formation-accountability><h1>Vorming</h1>'
        '<h2>Brongebruik verantwoorden</h2>'
        '<p><a href="' + ui._esc(overview) + '">Voortgang en vormingsproblemen</a> · '
        '<a href="' + ui._esc(review) + '">Kennisvoorstellen beoordelen in Review</a></p>' + panel + '</section>')


ACTIVE_PROGRESS = {"bezig", "wacht op uitvoering"}


def _phase_label(phase):
    return {'source_and_validation': 'Bron lezen en controleren', 'reserved': 'Gereserveerd',
                 'extraction_started': 'Brontekst uitlezen', 'extraction_finished': 'Brontekst beschikbaar',
                 'model_request': 'Bronpassages selecteren', 'model_response': 'Selectie controleren',
                 'proposal_received': 'Kandidaten controleren', 'activated': 'Resultaat opgeslagen',
                 'validation_started': 'Brongetrouwheid voorbereiden',
                 'source_reconstructed': 'Bronpassages reconstrueren', 'response_received': 'Modelantwoord ontvangen',
                 'proposal_parsed': 'Voorstel controleren', 'evidence_resolved': 'Bronvelden en relaties controleren',
                 'formation_accounted': 'Brondekking controleren', 'stopped': 'Verwerking gestopt'}.get(phase, 'Bronselectie en controle')


def _progress_html(result, esc):
    progress = ''
    if result['state'] == 'bezig':
        elapsed = result['elapsed_seconds']
        phase = _phase_label(result['phase'])
        remaining = result['remaining_seconds']
        progress = (f'<p>Fase: {esc(phase)} · Verstreken: {esc(_minutes(elapsed)) if elapsed is not None else "onbekend"}'
                    f'<span data-source-remaining{"" if remaining else " hidden"}>'
                    f' · Geschat resterend: {esc(_range(remaining))}</span></p>')
    if result.get('blocked_reason'):
        reason = {'processing_attempt_expired':'De totale tijdslimiet is bereikt',
                  'source_task_budget_exhausted':'Het verwerkingsbudget is uitgeput',
                  'processing_document_call_budget_exhausted':'Het maximum aantal modelaanroepen is bereikt',
                  'processing_configuration_changed':'De verwerkingsconfiguratie is gewijzigd',
                  'researcher_role_required':'De uitvoeringsbevoegdheid is ingetrokken',
                  'not_authenticated':'Het verantwoordelijke account is niet meer actief'}.get(result['blocked_reason'], 'Een verwerkingsvoorwaarde blokkeert de uitvoering')
        progress = (f'<p>Verwerking vastgelopen: {esc(reason)}. '
                    f'{esc(result.get("required_action") or "Los de blokkade op voordat u opnieuw start.")}</p>')
    if result.get('budget_stopped') and not result.get('blocked_reason'):
        counts = result.get('progress') or {}
        done, open_ = counts.get('terminal_task_count'), counts.get('pending_task_count')
        progress = (f'<p>Gestopt op taakbudget: {esc(done) if done is not None else "onbekend"} taken klaar, '
                    f'{esc(open_) if open_ is not None else "onbekend"} taken open.</p>')
    if result['state'] == 'wacht op uitvoering':
        elapsed = result['elapsed_seconds']
        deadline = result['deadline_seconds']
        progress = (f'<p>Wacht op een uitvoeringsplek of conversiecapaciteit. '
                    f'Verstreken sinds aanvraag: {esc(_minutes(elapsed)) if elapsed is not None else "onbekend"}. '
                    f'Resterende totale tijdslimiet: {esc(_minutes(deadline)) if deadline is not None else "onbekend"}.</p>'
                    '<p>De tijdslimiet loopt vanaf de aanvraag. Verloopt deze tijdens wachten, '
                    'dan telt deze poging mee voor de herstelgrens. De geschatte verwerkingstijd bevat ook wachttijd.</p>')
    return progress


def _progress_script():
    return """<script>
(() => {
  const controls = document.querySelector('[data-source-poll]');
  const cards = new Map(Array.from(document.querySelectorAll('[data-source-attempt]'),
    card => [card.dataset.sourceDocument, card]));
  const feedback = controls.querySelector('[data-source-feedback]');
  const pause = controls.querySelector('[data-source-pause]');
  const refreshLink = controls.querySelector('a');
  const picker = document.querySelector('#source-document');
  const timeFormat = new Intl.DateTimeFormat('nl-NL', {timeStyle:'short'});
  let lastRead = new Date();
  let timer;
  let paused = false;
  let pending = false;
  controls.hidden = false;

  function schedule() {
    clearTimeout(timer);
    if (!document.hidden && !paused && !pending && cards.size) timer = setTimeout(refresh, 5000);
  }

  function setStatus(card, message) {
    const status = card.querySelector('[data-source-status]');
    if (status.textContent !== message) status.textContent = message;
  }

  function readProgress(params) {
    return fetch('/source-selection/progress?' + params, {
      redirect:'error', signal:AbortSignal.timeout(10000),
    });
  }

  async function finish(card, row, manual) {
    const id = card.dataset.sourceDocument;
    cards.delete(id);
    const detail = card.querySelector('[data-source-detail-link]') || document.createElement('a');
    detail.className = 'btn-secondary';
    detail.href = '/source-selection?' + new URLSearchParams({document:id});
    detail.textContent = row?.state === 'volledigheid nog niet gecontroleerd'
      ? 'Volledigheid controleren' : 'Actuele voortgang bekijken';
    if (!detail.isConnected) card.querySelector('.source-actions').prepend(detail);
    if (!row || id !== controls.dataset.sourceDetail || id !== picker.value ||
        (!manual && (document.hidden || paused))) return;
    const response = await readProgress(new URLSearchParams({
      snapshot:id, detail:id, attempt:row.attempt, offset:controls.dataset.sourceOffset,
    }));
    if (response.status === 401 || response.status === 403) {
      hideCard(id, card);
      return false;
    }
    if (!response.ok) throw Error('Detail unavailable');
    const {rows} = await response.json();
    const current = rows.find(item => item.snapshot === id);
    if (!current) {
      hideCard(id, card);
      return false;
    }
    if (current.attempt !== row.attempt || !current.detail || id !== picker.value) return;
    replaceCard(card, current.detail);
  }

  function replaceCard(card, html) {
    const template = document.createElement('template');
    template.innerHTML = html;
    const replacement = template.content.firstElementChild;
    if (replacement?.dataset.sourceDocument !== card.dataset.sourceDocument) return;
    replacement.dataset.selected = card.dataset.selected;
    const estimate = replacement.querySelector('.source-estimate');
    if (estimate) estimate.textContent = card.querySelector('.source-estimate').textContent;
    const replace = () => {
      if (card.isConnected && !card.contains(document.activeElement)) card.replaceWith(replacement);
    };
    if (card.contains(document.activeElement)) card.addEventListener('focusout', () => setTimeout(replace, 0));
    else replace();
  }

  function apply(card, row, manual) {
    const progress = card.querySelector('[data-source-progress]');
    if (row.attempt !== card.dataset.sourceAttempt) {
      setStatus(card, 'De verwerking is overgegaan naar een andere poging.');
      progress.replaceChildren();
      return finish(card);
    }
    if (row.state !== card.dataset.sourceState || row.phase !== card.dataset.sourcePhase) {
      setStatus(card, 'Status: ' + row.state);
      if (row.running && row.state === 'bezig') {
        const announcement = document.createElement('span');
        announcement.className = 'sr-only';
        announcement.textContent = ' · Fase: ' + row.phase_label;
        card.querySelector('[data-source-status]').append(announcement);
      }
      card.dataset.sourceState = row.state;
      card.dataset.sourcePhase = row.phase;
    }
    progress.innerHTML = row.progress;
    const range = JSON.parse(card.dataset.sourceRange);
    const remaining = progress.querySelector('[data-source-remaining]');
    if (remaining && range && row.elapsed !== null && row.elapsed < range[1]) {
      const minutes = seconds => seconds < 60 ? 'minder dan 1 min' : Math.ceil(seconds / 60) + ' min';
      remaining.hidden = false;
      remaining.textContent = ' · Geschat resterend: ongeveer ' +
        minutes(range[0] - row.elapsed) + '–' + minutes(range[1] - row.elapsed) + ' (onzeker)';
    }
    if (!row.running) return finish(card, row, manual);
  }

  function hideCard(id, card) {
    cards.delete(id);
    card.remove();
    Array.from(picker.options).find(option => option.value === id)?.remove();
  }

  async function refresh(manual = false) {
    if (pending || !cards.size || (!manual && (document.hidden || paused))) return;
    pending = true;
    clearTimeout(timer);
    try {
      const active = Array.from(cards);
      let lostAccess = false;
      for (let start = 0; start < active.length; start += 50) {
        if (!manual && (document.hidden || paused)) break;
        const group = active.slice(start, start + 50);
        const params = new URLSearchParams(group.map(([id]) => ['snapshot', id]));
        const response = await readProgress(params);
        if (response.status === 401 || response.status === 403) {
          cards.forEach((card, id) => hideCard(id, card));
          feedback.textContent = 'Toegang tot de voortgang is vervallen. Open Vorming opnieuw.';
          return;
        }
        if (!response.ok) throw Error('Progress unavailable');
        const {rows} = await response.json();
        const current = new Map(rows.map(row => [row.snapshot, row]));
        for (const [id, card] of group) {
          const row = current.get(id);
          if (row) lostAccess = (await apply(card, row, manual) === false) || lostAccess;
          else {
            hideCard(id, card);
            lostAccess = true;
          }
        }
      }
      lastRead = new Date();
      feedback.textContent = lostAccess ? 'Voor een document is de voortgang niet meer beschikbaar.'
        : paused ? 'Automatisch bijwerken is gepauzeerd.' : '';
    } catch {
      feedback.textContent = 'Bijwerken niet gelukt. Laatst gelezen om ' + timeFormat.format(lastRead) +
        '. Kies Ververs status om opnieuw te proberen.';
    } finally {
      pending = false;
      schedule();
    }
  }

  pause.addEventListener('click', () => {
    paused = !paused;
    pause.textContent = paused ? 'Updates hervatten' : 'Updates pauzeren';
    feedback.textContent = paused ? 'Automatisch bijwerken is gepauzeerd.' : '';
    schedule();
  });
  refreshLink.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || !cards.size) return;
    event.preventDefault();
    refresh(true);
  });
  document.addEventListener('visibilitychange', schedule);
  schedule();
})();
</script>"""


def require_decision_tree(envelope):
    if envelope['class'] != 'beslisboom':
        raise HTTPException(status_code=404)


def install(app, console, require, page, nav, esc):
    from src.vorming.source_processing_dispatch_v1 import install_dispatcher
    dispatcher = install_dispatcher(app, console)

    def render_card(envelope, actor, observations, *, selected, detail, offset):
        sid = envelope['snapshot_id']
        if (envelope['class'] != 'beslisboom' or envelope.get('annotation_source_prepared')
                or (envelope.get('received_source') and not envelope.get('annotation_has_formed_work')
                    and not envelope.get('processing_attempts'))):
            query = esc(urlencode({'document': sid}))
            latest = next(reversed(envelope.get('processing_attempts') or []), {})
            if envelope['annotation_source_prepared'] or envelope.get('annotation_source_started'):
                annotate = f'<a class="btn-primary" href="/annotations?{query}">Annoteren</a>'
            elif not envelope.get('received_source') or envelope['annotation_has_formed_work']:
                annotate = '<p>Lever een nieuwe bronversie in om deze tekst te annoteren.</p>'
                if 'researcher' in actor['roles']:
                    annotate += '<a class="btn-primary" href="/ingest">Nieuwe bronversie inleveren</a>'
            elif latest.get('state') == 'running':
                annotate = '<p>Bronvoorbereiding voor annotatie is beschikbaar zodra de lopende verwerking is beëindigd.</p>'
            else:
                from src.vorming.human_annotation_ui_v1 import source_preparation_form

                # This card was captured without formed objects. The POST compares
                # the empty-frontier token against the locked current document.
                revision = console.workflow_document_store.revision_for_rows([])
                annotate = source_preparation_form(sid, revision, 'Annoteren', esc)
            return (f'<article class="doc-card" id="source-{esc(sid)}" data-source-document="{esc(sid)}" data-document-class="{esc(envelope["class"])}"'
                    f' data-selected="{str(sid == selected).lower()}"><h2>{esc(envelope["title"])}</h2>'
                    f'<p class="source-meta">Bronversie {esc(envelope["version"])}</p>'
                    f'<div class="source-actions">{annotate}<a class="btn-secondary" href="/annotations/build?{query}">'
                    'Bekijk status bouwopdrachten</a></div></article>'), None
        # Volledige controle alleen voor het expliciet gekozen document (D-PERF-2).
        report = None
        if detail:
            from src.vorming.formation_problems_v1 import collect
            report = collect(console, actor_id=actor['account_id'], snapshot_id=sid)
        result = (projection(console, actor_id=actor['account_id'], snapshot_id=sid, documents=[],
                             observations=observations, processing=report['processing']) if detail
                  else summary_projection(console, envelope=envelope, observations=observations))
        action = ''
        active = result['state'] in ACTIVE_PROGRESS
        if not detail:
            label = 'Voortgang bekijken' if active else 'Document openen'
            marker = ' data-source-detail-link' if active else ''
            action = f'<a class="btn-secondary" href="/source-selection?document={esc(sid)}"{marker}>{label}</a>'
        elif active or result['state'] == 'voltooid':
            pass  # Active details already show progress; completion owns Naar Review below.
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
            action = '<p>Hervatten is nu niet beschikbaar. Bekijk de vormingsproblemen hieronder voor de vervolgstap.</p>'
        summary = ''
        if result['state'] in {'voltooid', 'onderbroken', 'mislukt', UNCHECKED}:
            summary = (f'<p>{result["candidates"]} gevormde kandidaten · {result["source_passages"]} overige bronpassages · {result["blocked"]} geblokkeerde kandidaten · {result["formation_blockers"]} verwerkingsblokkades.</p>'
                       f'<p>Poging technisch geslaagd: {"ja" if result["attempt_succeeded"] else "nee"}. '
                       f'Volledige bronverwerking: {"ja" if result["formation_complete"] else "nog niet bevestigd"}.</p>')
        if result['candidates'] is None:
            summary = '<p>Aantallen kandidaten en bronpassages zijn nog niet gecontroleerd. Open het document voor de actuele controles en vervolgacties.</p>'
        diagnosis_link = ('' if detail else f'<a class="btn-secondary" href="/source-selection?{esc(urlencode({"document": sid}))}#formation-problems">Vormingsproblemen</a>')
        diagnosis_link += f'<a class="btn-secondary" href="/inzicht/document?{esc(urlencode({"document": sid}))}">Bekijk diagnose in Inzicht</a>'
        review = f'<a class="btn-primary" href="/review?document={esc(sid)}">Naar Review</a>' if result['review_available'] else ''
        extent = _size(result["bytes"]) if result['bytes'] is not None else 'Bestandsgrootte onbekend'
        fragment_count = envelope.get('source_fragment_count')
        if fragment_count is not None:
            extent += f' · {fragment_count} opgeslagen bronfragmenten'
        problems = ''
        if report is not None:
            status = report['processing']
            work_revision_url = None
            if (not result['can_start'] and status.get('state') != 'running' and status.get('formation_incomplete')
                    and 'researcher' in actor['roles'] and actor['account_id'] in envelope.get('named_reviewers', [])):
                work_revision_url = '/review/policy?' + urlencode({'document': sid})
            # collect has already loaded this request's full envelope; the list row is compact.
            document = console._envelope(sid)
            if 'decision_graph' in document:
                if 'reviewer' in actor['roles'] and actor['account_id'] in document.get('named_reviewers', []):
                    graph = esc(urlencode({'document': sid, 'task': 'graph'}))
                    action += f'<a class="btn-secondary" href="/source-selection?{graph}">Beslisstructuur vastleggen</a>'
                if not review:
                    review = f'<a class="btn-primary" href="/review?document={esc(sid)}">Naar Review</a>'
            problems = source_recovery_controls(document, status, actor)
            problems += ('<section class="formation-room" id="formation-problems">' +
                _formation_problems_html(report, offset=offset, esc=esc, work_revision_url=work_revision_url) + '</section>')
        key = progress_attempt_key(next(reversed(envelope.get('processing_attempts') or []), {}))
        live = ''
        status_markup = f'<p role="status">Status: {esc(result["state"])}</p>'
        progress_markup = _progress_html(result, esc)
        if active and key:
            live = (f' data-source-attempt="{esc(key)}" data-source-phase="{esc(result["phase"])}"'
                    f' data-source-state="{esc(result["state"])}"'
                    f' data-source-range="{esc(json.dumps(result["estimate"]["range_seconds"]))}"')
            status_markup = f'<p role="status" data-source-status>Status: {esc(result["state"])}</p>'
            progress_markup = f'<div data-source-progress>{progress_markup}</div>'
        return (f'<article class="doc-card" id="source-{esc(sid)}" data-source-document="{esc(sid)}" data-document-class="{esc(envelope["class"])}"'
                f' data-selected="{str(sid == selected).lower()}"{live}>'
                f'<h2>{esc(result["title"])}</h2><p class="source-meta">{esc(result["filename"])} · Bronversie {esc(result["version"])} · {esc(extent)}</p>'
                f'{status_markup}<p class="source-estimate">{esc(_estimate(result["estimate"]))}</p>'
                f'{progress_markup}{summary}'
                f'<div class="source-actions">{action}{review}{diagnosis_link}</div>{problems}</article>'), result

    @app.get('/source-selection', response_class=HTMLResponse)
    def selection_get(request: Request, document: str = '', selected_document: str = '', offset: int = Query(0, ge=0),
                      object: str = '', task: str = '', graph_saved: str = ''):
        context_editor = request.query_params.get('context_target') or request.query_params.get('context_mode') == 'source'
        if object or context_editor or task not in {'', 'graph', 'disposition'}:
            raise HTTPException(status_code=404)
        with diagnostic_phase("authorization"):
            actor = require(request)
        if task and not document:
            raise HTTPException(status_code=404)
        if task:
            from src.vorming.source_selection_v1 import authorize_account
            if actor.get('_view_document') and document != actor['_view_document']:
                raise ConsoleError('reviewer_not_named_on_snapshot')
            envelope = console._envelope(document)
            authorize_account(actor, envelope)
            require_decision_tree(envelope)
        if document and not task and not selected_document and not actor.get('_view_document'):
            from src.vorming.human_annotation_v1 import owns_source
            if owns_source(console, document):
                return RedirectResponse('/annotations?' + urlencode({'document': document}), status_code=303)
        if task == 'graph' and document:
            from src.review.decision_review_ui_v1 import render_graph
            body = render_graph(console, actor, document, editing=True)
            if graph_saved == 'yes':
                body = body.replace('<h2>Beslisstructuur vastleggen</h2>', '<h2>Beslisstructuur vastleggen</h2><p class="banner ok" role="status">De beslisstructuur is opgeslagen. Beoordeel de huidige graaf in Review.</p>')
            return body
        if task == 'disposition' and document:
            return render_source_accountability(console, actor, document)
        # Overview owns compact progress inputs; only the chosen document loads detail.
        scoped_document = actor.get('_view_document')
        documents = console.source_selection_documents(
            actor_id=actor['account_id'],
            document=document if not selected_document and not scoped_document else '',
            snapshot_ids=[scoped_document] if scoped_document else None,
        )
        document = selected_document or document
        visible = documents
        if document and document not in {row['snapshot_id'] for row in visible}:
            raise ConsoleError('reviewer_not_named_on_snapshot')
        selected = document or (visible[-1]['snapshot_id'] if visible else '')
        options = ''.join(f'<option value="{esc(row["snapshot_id"])}" {"selected" if row["snapshot_id"] == selected else ""}>{esc(row["title"])} — {esc(row["version"])}</option>' for row in visible)
        cards = []
        running_visible = False
        # Eén keer per verzoek (PR-b): vergelijkbare metingen over alle documenten.
        observations = comparable_observations([row for row in documents if row['class'] == 'beslisboom'])
        for envelope in visible:
            markup, _ = render_card(envelope, actor, observations, selected=selected,
                detail=bool(document) and envelope['snapshot_id'] == document, offset=offset)
            cards.append(markup)
            running_visible |= 'data-source-attempt=' in markup
        notice = '<div class="banner ok">Document veilig ontvangen. Start de bronverwerking wanneer je wilt.</div>' if request.query_params.get('received') == 'yes' else ''
        controls = ''
        script = '<script>document.addEventListener("submit",function(event){const form=event.target;if(!form.matches("form[action=\\"/source-selection/start\\"]"))return;if(form.dataset.submitting){event.preventDefault();return;}form.dataset.submitting="yes";form.querySelector("button").disabled=true;});</script>'
        if running_visible and not scoped_document:
            refresh_url = request.url.path + (f'?{request.url.query}' if request.url.query else '')
            refresh = f'<a class="btn-secondary" href="{esc(refresh_url)}">Ververs status</a>'
            controls = (f'<div data-source-poll data-source-detail="{esc(document)}" data-source-offset="{offset}" hidden>'
                        '<div class="source-actions"><button class="btn-secondary" type="button" data-source-pause>'
                        'Updates pauzeren</button>' + refresh + '</div>'
                        '<p role="status" data-source-feedback></p></div><noscript>' + refresh + '</noscript>')
            script += _progress_script()
        return HTMLResponse(page(nav(actor, 'selection') + '<section class="room" id="source-selection"><h1>Vorming</h1>' + notice
                    + '<form method="get" class="source-picker"><label for="source-document">Document</label>'
                    + '<div class="source-picker-row"><select id="source-document" name="selected_document">' + options + '</select>'
                    + '<button class="btn-secondary" type="submit">Document selecteren</button></div></form>' + controls
                    + (''.join(sorted(cards, key=lambda card: 'data-selected="true"' not in card)) or '<p data-source-empty>Geen documenten beschikbaar voor bronverwerking.</p>') + '</section>' + script),
                            headers={'Cache-Control': 'no-store'})

    @app.get('/source-selection/progress', response_class=JSONResponse)
    def selection_progress(request: Request, snapshot: list[str] = Query(min_length=1, max_length=50),
                           detail: str = '', attempt: str = '', offset: int = Query(0, ge=0)):
        headers = {'Cache-Control': 'no-store'}
        try:
            actor = require(request)
            scoped = actor.get('_view_document')
            requested = list(dict.fromkeys(key for key in snapshot if not scoped or key == scoped))
            documents = (console.source_selection_documents(actor_id=actor['account_id'], snapshot_ids=requested)
                         if requested else [])
            rows = []
            for envelope in documents:
                if envelope['class'] != 'beslisboom':
                    continue
                result = summary_projection(console, envelope=envelope, observations={})
                sid = result['snapshot_id']
                running = result['state'] in ACTIVE_PROGRESS
                row = {'snapshot': sid, 'attempt': result['attempt_key'], 'state': result['state'],
                       'phase': result['phase'], 'phase_label': _phase_label(result['phase']),
                       'elapsed': result['elapsed_seconds'], 'progress': _progress_html(result, esc),
                       'running': running}
                if sid == detail and attempt and attempt == row['attempt'] and not running:
                    card, current = render_card(envelope, actor, {}, selected=sid, detail=True, offset=offset)
                    if (attempt in (current['attempt_key'], current['attempt_started_at'])
                            and current['state'] not in ACTIVE_PROGRESS):
                        row['detail'] = card
                rows.append(row)
        except ConsoleError as error:
            if error.code == 'not_authenticated':
                return JSONResponse({'error': 'not_authenticated'}, status_code=401, headers=headers)
            if error.code in {'reviewer_not_named_on_snapshot', 'researcher_role_required'}:
                return JSONResponse({'error': 'access_denied'}, status_code=403, headers=headers)
            raise
        return JSONResponse({'rows': rows}, headers=headers)

    @app.get('/inzicht/document/verwerkingsspoor')
    def processing_trace_export(request: Request, document: str = '', attempt: str | None = None,
                                origin_request: str | None = None):
        from src.vorming.source_selection_v1 import authorize
        from src.vorming.processing_trace_v1 import processing_trace, select_processing_attempt
        actor = require(request)
        envelope = console._envelope(document)
        authorize(console, actor['account_id'], envelope)
        trace = processing_trace(envelope)
        if attempt is not None or origin_request is not None:
            selection = select_processing_attempt(envelope, attempt=attempt, origin_request=origin_request)
            trace['selection'] = {'status': selection['status'],
                                  'attempt_id': (selection.get('attempt') or {}).get('attempt_id')}
        return JSONResponse(trace, headers={'Cache-Control': 'no-store',
            'Content-Disposition': 'attachment; filename=processing-trace.json'})

    @app.get('/inzicht/document/publicatiebewijs')
    def publication_evidence_get(request: Request, document: str = ''):
        from src.publication.publication_evidence_v1 import collect_publication
        actor = require(request)
        return JSONResponse(collect_publication(console, actor_id=actor['account_id'], snapshot_id=document),
            headers={'Cache-Control':'no-store',
                     'Content-Disposition':'attachment; filename=publication-evidence.json'})

    @app.get('/inzicht/document/blokkade')
    def blockage_get(request: Request, document: str = '', checks: bool = False,
                     download: bool = False, attempt: str = Query('', pattern=r'^(?:pa_[0-9a-f]{32})?$')):
        from src.vorming.blockage_diagnostics_v1 import collect_blockage
        from src.settings.insight_v1 import insight_tabs
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
        return HTMLResponse(page(nav(actor, 'settings') + '<section class="room" id="blockage-report" style="overflow-wrap:anywhere">' + insight_tabs('documenten') +
            '<p><a href="/inzicht/document?' + esc(urlencode({'document': document})) + '">← Documentdiagnose</a></p>' + _blockage_html(report, esc) + selector + links + '</section>'), headers={'Cache-Control':'no-store'})

    def reserve_tree(actor, sid, command, revision):
        from src.vorming.source_selection_v1 import authorize_account
        envelope = console._envelope(sid)
        authorize_account(actor, envelope)
        # Changing to or from a tree requires a separate successor snapshot.
        require_decision_tree(envelope)
        return console.reserve_source_selection(actor_id=actor['account_id'], snapshot_id=sid,
                                                command_id=command, expected_revision=revision)

    @app.post('/source-selection/start')
    async def selection_start(request: Request):
        actor = require(request)
        form = await request.form()
        sid = str(form.get('document') or '')
        try:
            attempt, fresh = await asyncio.to_thread(reserve_tree, actor, sid,
                str(form.get('command_id') or ''), str(form.get('expected_revision') or ''))
        except ConsoleError as exc:
            if exc.code != 'processing_attempt_in_progress':
                raise
            return RedirectResponse('/source-selection?' + urlencode({'document': sid}), status_code=303)
        # A wake is only a hint. The kernel recovers durable pending attempts
        # at startup and on its bounded poll, even if this request disappears.
        if attempt["state"] == "running":
            dispatcher.notify(sid, attempt)
        return RedirectResponse('/source-selection?' + urlencode({'document': sid}), status_code=303)

    return dispatcher
