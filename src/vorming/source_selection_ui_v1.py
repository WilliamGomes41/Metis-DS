"""Source selection room: presentation and dispatch over durable kernel commands."""
from src.request_diagnostics_v1 import diagnostic_phase

import asyncio
import re
from html import escape
import uuid
from urllib.parse import urlencode

from fastapi import Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from src.operations_console_v1 import ConsoleError
from src.review.beslisboom_path_v1 import review_path_for_klasse
from src.vorming.source_selection_v1 import UNCHECKED, comparable_observations, projection
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
            else:
                owner = '/source-selection?' + urlencode({'document': document}) + '#source-page-' + str(int(row['page']))
                rows.append(f'<tr><td>Pagina {int(row["page"])}</td><td>{escape(problem)}</td><td>{escape(action)}</td>'
                            f'<td><a href="{escape(owner, quote=True)}">Pagina verantwoorden in Vorming</a></td></tr>')
        parts.append('<section id="paginas"><h3>Onopgeloste pagina’s</h3>'
                     '<p>Verantwoord alleen een pagina zonder kennisinhoud in Vorming. Start daarna de verwerking opnieuw.</p>'
                     '<table><thead><tr><th>Pagina</th><th>Probleem</th><th>Herstelactie</th><th>Verantwoorden</th></tr></thead>'
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
    direct.sort(key=lambda a: 'task=repair' not in a['url'])
    labels = {'Kandidaat herstellen': 'Herstel het voorstel',
              'Bronbereik bekijken en behandelen': 'Bekijk en behandel dit bronstuk',
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
def render_continuation(console, account, document, object, *, return_task='', saved=False, review_revision=''):
    """Present the existing literal repair command over its bounded read."""
    from src import operations_console_app as ui
    from src.review.review_passage_read_v1 import read_review_passage
    inputs = read_review_passage(console, account, document, object)
    obj = next((row for row in inputs.objects if row['object_id'] == object), None)
    if obj is None:
        raise ConsoleError('unknown_object')
    proposal = ui.admission_of(obj).get('expand_merge') or {}
    merged = str(proposal.get('merged_text') or '').strip()
    current = str((obj.get('content') or {}).get('clean_text') or '')
    adds_text = (' '.join(merged.split()) not in
                 {' '.join(current.split()), ' '.join(ui.review_card_sentence(obj).split())})
    available = proposal.get('kind') == 'sentence_continuation' and bool(merged) and adds_text
    panel = '<h2>Afgebroken zin aanvullen</h2><p><b>Huidige passage:</b> ' + ui._esc(current) + '</p>'
    if available:
        parts = list(proposal.get('parts') or [])
        missing = str(parts[1] if len(parts) > 1 else '').strip()
        panel += ('<aside class="source-continuation-proposal">'
            '<p><b>Ontbrekende brontekst:</b> ' + ui._esc(missing) + '</p>'
            '<p><b>Herstelde passage:</b> ' + ui._esc(merged) + '</p>'
            '<p>Na aanvullen ontstaat een nieuwe versie. Die versie is nog niet goedgekeurd '
            'en moet opnieuw worden beoordeeld.</p></aside>')
        if inputs.source_available and not console.snapshot_is_published(document):
            panel += ('<form method="post" action="/review/context/accept">'
                '<input type="hidden" name="snapshot_id" value="' + ui._esc(document) + '">'
                '<input type="hidden" name="object_id" value="' + ui._esc(object) + '">'
                '<input type="hidden" name="return_task" value="' + ui._esc(ui.normalize_review_task(return_task)) + '">'
                + ui._snapshot_revision_input(inputs.revision) +
                ('<input type="hidden" name="review_revision" value="' + ui._esc(review_revision) + '">' if review_revision else '') +
                '<button class="btn-primary" type="submit">Passage aanvullen met brontekst</button></form>')
        else:
            panel += '<p class="banner warn">Bronaanvulling is hier alleen te lezen.</p>'
    else:
        panel += '<p>Er is geen actueel voorstel voor letterlijke bronaanvulling. Beoordeel de huidige passage in Review.</p>'
    back = '/review?' + urlencode({'document': document, 'object': object,
        'task': ui.normalize_review_task(return_task), **({'review_revision': review_revision} if review_revision else {})})
    overview = '/source-selection?' + urlencode({'document': document})
    notice = ('<p class="banner ok" role="status">De bronaanvulling is opgeslagen. '
              'Beoordeel de huidige versie opnieuw in Review.</p>' if saved else '')
    return ui._page(ui._nav(account, 'selection') +
        '<section class="room review-room" data-formation-continuation><h1>Vorming</h1>'
        '<p><a href="' + ui._esc(overview) + '">Voortgang en vormingsproblemen</a> · '
        '<a href="' + ui._esc(back) + '">Deze passage beoordelen in Review</a></p>' + notice +
        panel + ui._broncontext_html(obj, document, object, inputs.source_available) + '</section>')


@source_reconstruction_scope(reuse_existing=True)
def render_context(console, account, document, object, *, context_target='', context_mode='',
                   context_page=0, context_q='', context_saved=False,
                   context_draft=None, context_error='', review_revision=''):
    """Present the existing bounded context read and command in its one workplace."""
    from src import operations_console_app as ui
    from src.review.review_passage_read_v1 import read_review_passage
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    # Draft targets are actual required context, not grounds for a full-corpus
    # fallback. Keep every selected target even when it is outside the page.
    inputs = read_review_passage(console, account, document, object,
        context_target=context_target, choice_page=max(context_page, 0), choice_query=context_q,
        include_choices=True, context_targets=(context_draft or {}).get('target_object_ids') or ())
    envelope, objects, revision = inputs.envelope, inputs.objects, inputs.revision
    obj = next((row for row in objects if row['object_id'] == object), None)
    if obj is None:
        raise ConsoleError('unknown_object')
    projection, _ = ui._review_detail_projection(console, account, document, obj,
        objects, review_path_for_klasse(envelope['class']), inputs)
    editable = not console.snapshot_is_published(document)
    panel = ui._source_context_panel(obj, objects, document, revision,
        context_target=context_target, source_mode=context_mode == 'source',
        draft=context_draft, error=context_error, projection=projection, editable=editable,
        context_choices=inputs.context_choices if inputs is not None else None,
        choices_html=ui._passage_choices_html(document, obj, inputs,
            context_mode=context_mode, context_target=context_target) if editable else '')
    saved = ('<p class="banner ok" role="status">Het contextbesluit is opgeslagen. '
             'Beoordeel de betrokken passages opnieuw.</p>' if context_saved else '')
    if review_revision:
        origin = ui._esc(urlencode({'review_revision': review_revision}))
        panel = re.sub(r'href="(/source-selection\?[^"#]*)(#[^"]*)?"',
            lambda m: 'href="' + m[1] + '&amp;' + origin + (m[2] or '') + '"', panel)
        panel = panel.replace('</form>',  '<input type="hidden" name="review_revision" value="' + ui._esc(review_revision) + '"></form>')
    back = '/review?' + urlencode({'document': document, 'object': context_target or object, **({'review_revision': review_revision} if review_revision else {})})
    overview = '/source-selection?' + urlencode({'document': document})
    if inputs is not None:
        available = inputs.source_available
    else:
        try:
            console.open_source_passage(snapshot_id=document, object_id=object)
            available = True
        except ConsoleError:
            available = False
    return ui._page(ui._nav(account, 'selection') +
        '<section class="room review-room" data-formation-context><h1>Vorming</h1>' +
        '<p><a href="' + ui._esc(overview) + '">Voortgang en vormingsproblemen</a> · '
        '<a href="' + ui._esc(back) + '">Deze passage beoordelen in Review</a></p>' + saved +
        '<h2>Broncontext vastleggen</h2>' +
        ui._broncontext_html(obj, document, object, available) + panel + '</section>')


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
    else:
        objects, revision = console.snapshot_objects_and_revision(document)
        bindings = ui._review_bindings(console, document, objects=objects)
    panel = ui._review_inventory(document, objects,
        review_path=review_path_for_klasse(envelope['class']), bindings=bindings,
        reviewer_id=account['account_id'], task='inventory', snapshot_revision=revision,
        fragments=console.review_source_fragments(document), source_only=True,
        edit_exclusions=not console.snapshot_is_published(document))
    overview = '/source-selection?' + urlencode({'document': document})
    review = '/review?' + urlencode({'document': document})
    return ui._page(ui._nav(account, 'selection') +
        '<section class="room review-room" data-formation-accountability><h1>Vorming</h1>'
        '<h2>Brongebruik verantwoorden</h2>'
        '<p><a href="' + ui._esc(overview) + '">Voortgang en vormingsproblemen</a> · '
        '<a href="' + ui._esc(review) + '">Kennisvoorstellen beoordelen in Review</a></p>' + panel + '</section>')


@source_reconstruction_scope(reuse_existing=True)
def render_structure(console, account, document, *, conflict=False, q='', page=1):
    """One presentation owner for the existing prose heading confirmation."""
    from src import operations_console_app as ui
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    console._require_role(account['account_id'], 'reviewer')
    envelope = console._envelope(document)
    if account['account_id'] not in envelope.get('named_reviewers', []):
        raise ConsoleError('reviewer_not_named_on_snapshot')
    review_path = review_path_for_klasse(envelope['class'])
    if review_path == 'boom':
        return RedirectResponse('/review?' + urlencode({'document': document, 'task': 'structure'}), status_code=303)
    objects, revision = console.snapshot_objects_and_revision(document)
    bindings = ui._review_bindings(console, document, objects=objects)
    headings = ui._review_route_objects(objects, review_path=review_path,
        bindings=bindings, reviewer_id=account['account_id'], canonical_task='structure',
        fragments=console.review_source_fragments(document))
    copy = ui._review_lane_copy(review_path, headings)
    editable = not console.snapshot_is_published(document)
    rows = ''.join(ui._review_index_item(obj, document, checkbox=editable, task='structure') for obj in headings)
    panel = '<p class="review-task-empty">Er zijn geen open koppen om te bevestigen.</p>'
    if headings:
        panel = '<ol class="object-index review-heading-list">' + rows + '</ol>'
        if editable:
            panel = ('<form method="post" action="/review/headings/batch-confirm">'
                '<input type="hidden" name="snapshot_id" value="' + ui._esc(document) + '">'
                '<input type="hidden" name="interaction_id" value="' + ui._esc(ui.new_review_interaction_id()) + '">'
                + ui._snapshot_revision_input(revision) +
                '<div class="review-batch-tools"><span>Selecteer alleen koppen die je hebt gecontroleerd.</span>'
                '<button class="btn-secondary" type="button" data-select-review-batch>Selecteer alles</button>'
                '<button class="btn-secondary" type="button" data-clear-review-batch>Selectie wissen</button></div>'
                + panel + '<button class="btn-primary" type="submit">' + ui._esc(copy['fast_button']) + '</button></form>')
    if not editable:
        panel = '<p class="banner warn">Deze gepubliceerde werkversie is alleen te lezen.</p>' + panel
    overview = '/source-selection?' + urlencode({'document': document})
    review_params = {'document': document}
    if q or page != 1:
        review_params.update(q=q, page=page)
    review = '/review?' + urlencode(review_params)
    return ui._page(ui._nav(account, 'selection') +
        '<section class="room review-room" data-formation-structure><h1>Vorming</h1>'
        + ui._task_links('review') +
        '<h2>' + ui._esc(copy['fast_title']) + '</h2><p>Controleer de koppen tegen de oorspronkelijke bron en bevestig je selectie als structuur.</p>'
        '<p><a href="' + ui._esc(overview) + '">Voortgang en vormingsproblemen</a> · '
        '<a href="' + ui._esc(review) + '">Kennisvoorstellen beoordelen in Review</a></p>'
        + ui._review_conflict_html(conflict) + '<section class="review-section review-lane-fast">' + panel + '</section></section>')


def install(app, console, require, page, nav, esc):
    from src.vorming.source_processing_dispatch_v1 import install_dispatcher
    dispatcher = install_dispatcher(app, console)

    @app.get('/source-selection', response_class=HTMLResponse)
    def selection_get(request: Request, document: str = '', offset: int = Query(0, ge=0),
                      object: str = '', context_target: str = '', context_mode: str = '',
                      context_page: int = 0, context_q: str = '', context_saved: str = '',
                      task: str = '', q: str = '', review_page: int = Query(1, alias='page'),
                      return_task: str = '', continuation_saved: str = '',
                      repair_kind: str = 'source_units', repair_saved: str = '', graph_saved: str = '', review_revision: str = ''):
        with diagnostic_phase("authorization"):
            actor = require(request)
        if task == 'structure' and document:
            return render_structure(console, actor, document, q=q, page=review_page)
        if task == 'graph' and document:
            from src.review.decision_review_ui_v1 import render_graph
            body = render_graph(console, actor, document, editing=True)
            if graph_saved == 'yes':
                body = body.replace('<h2>Beslisstructuur vastleggen</h2>', '<h2>Beslisstructuur vastleggen</h2><p class="banner ok" role="status">De beslisstructuur is opgeslagen. Beoordeel de huidige graaf in Review.</p>')
            return body
        if task == 'repair' and document:
            if object:
                from src.review.deterministic_review_repair_v1 import render_repair
                body = render_repair(console, request, {'snapshot_id': document, 'object_id': object, 'review_revision': review_revision},
                    repair_kind=repair_kind, saved=repair_saved == 'yes')
                return body
            console._require_role(actor['account_id'], 'reviewer')
            envelope = console._envelope(document)
            if actor['account_id'] not in envelope['named_reviewers']:
                raise ConsoleError('reviewer_not_named_on_snapshot')
            from src import operations_console_app as ui
            objects = console.snapshot_objects(document)
            panel = ui._review_inventory(document, objects, review_path=review_path_for_klasse(envelope['class']),
                bindings=ui._review_bindings(console, document, objects=objects), reviewer_id=actor['account_id'],
                task='repair', fragments=console.review_source_fragments(document))
            diagnosis = '/inzicht/document?' + urlencode(dict(document=document))
            return page(nav(actor, 'selection') + '<section class="room"><h1>Vorming</h1><h2>Passages herstellen</h2>' + panel +
                '<p><a href="' + esc(diagnosis) + '">Documentdiagnose en bewijs bekijken</a></p></section>')
        if task == 'continuation' and object:
            return render_continuation(console, actor, document, object,
                return_task=return_task, saved=continuation_saved == 'yes', review_revision=review_revision)
        if object:
            return render_context(console, actor, document, object, context_target=context_target,
                context_mode=context_mode, context_page=context_page, context_q=context_q,
                context_saved=context_saved == 'yes', review_revision=review_revision)
        if task == 'disposition' and document:
            return render_source_accountability(console, actor, document)
        # Overview owns compact progress inputs; only the chosen document loads detail.
        scoped_document = actor.get('_view_document')
        documents = ([console._envelope(scoped_document)] if scoped_document else
                     console.source_selection_documents(actor_id=actor['account_id'], document=document))
        visible = documents
        if document and document not in {row['snapshot_id'] for row in visible}:
            raise ConsoleError('reviewer_not_named_on_snapshot')
        selected = document or (visible[-1]['snapshot_id'] if visible else '')
        options = ''.join(f'<option value="{esc(row["snapshot_id"])}" {"selected" if row["snapshot_id"] == selected else ""}>{esc(row["title"])} — {esc(row["version"])}</option>' for row in visible)
        cards = []
        running_visible = False
        # Eén keer per verzoek (PR-b): vergelijkbare metingen over alle documenten.
        observations = comparable_observations(documents)
        for envelope in visible:
            sid = envelope['snapshot_id']
            # Volledige controle alleen voor het expliciet gekozen document (D-PERF-2).
            from src.vorming.source_selection_v1 import summary_projection
            detail = bool(document) and sid == document
            report = None
            if detail:
                from src.vorming.formation_problems_v1 import collect
                report = collect(console, actor_id=actor['account_id'], snapshot_id=sid)
            result = (projection(console, actor_id=actor['account_id'], snapshot_id=sid, documents=documents,
                                 observations=observations, processing=report['processing']) if detail
                      else summary_projection(console, envelope=envelope, observations=observations))
            action = ''
            if result['state'] in {'bezig', 'wacht op uitvoering'}:
                running_visible = True
            if not detail:
                label = 'Voortgang bekijken' if result['state'] in {'bezig', 'wacht op uitvoering'} else 'Document openen'
                action = f'<a class="btn-secondary" href="/source-selection?document={esc(sid)}">{label}</a>'
                if result['state'] in {'bezig', 'wacht op uitvoering'}:
                    action += '<p class="progress-refresh">Deze pagina ververst elke 5 seconden zolang de verwerking loopt.</p>'
            elif result['state'] in {'bezig', 'wacht op uitvoering'}:
                if sid == selected:
                    # This page already polls the selected document; a link to itself only reloads.
                    action = '<p class="progress-refresh">Deze pagina ververst elke 5 seconden zolang de verwerking loopt.</p>'
                    running_visible = True
                else:
                    action = f'<a class="btn-secondary" href="/source-selection?document={esc(sid)}">Voortgang bekijken</a>'
            elif result['state'] == 'voltooid':
                action = ''  # The primary Naar Review action below owns continuation.
            elif result['state'] == UNCHECKED:
                action = f'<a class="btn-secondary" href="/source-selection?document={esc(sid)}">Volledigheid controleren</a>'
            elif result['can_start']:
                label = 'Starten' if result['state'] == 'nog niet gestart' else 'Hervatten'
                from src.vorming.processing_document_budget_v1 import enabled as document_budget_enabled
                authorization = ('<p>Starten geeft één opdracht voor het volledige document, binnen vier uur inclusief wachttijd. '
                    'Het maximum aantal modelaanroepen is tweemaal het aantal geplande taken.</p>' if document_budget_enabled() else '')
                action = authorization + (f'<form method="post" action="/source-selection/start">'
                          f'<input type="hidden" name="document" value="{esc(sid)}">'
                          f'<input type="hidden" name="expected_revision" value="{esc(result["revision"])}">'
                          f'<input type="hidden" name="command_id" value="{uuid.uuid4().hex}">'
                          f'<button class="btn-primary">{label}</button></form>')
            else:
                action = '<p>Hervatten is nu niet beschikbaar. Bekijk de vormingsproblemen hieronder voor de vervolgstap.</p>'
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
            if result.get('blocked_reason'):
                reason = {'processing_attempt_expired':'De totale tijdslimiet is bereikt',
                          'source_task_budget_exhausted':'Het verwerkingsbudget is uitgeput',
                          'processing_document_call_budget_exhausted':'Het maximum aantal modelaanroepen is bereikt',
                          'processing_configuration_changed':'De verwerkingsconfiguratie is gewijzigd',
                          'researcher_role_required':'De uitvoeringsbevoegdheid is ingetrokken',
                          'not_authenticated':'Het verantwoordelijke account is niet meer actief'}.get(result['blocked_reason'], 'Een verwerkingsvoorwaarde blokkeert de uitvoering')
                progress = (f'<p>Verwerking geblokkeerd: {esc(reason)}. '
                            f'{esc(result.get("required_action") or "Los de blokkade op voordat u opnieuw start.")}</p>')
            if result.get('document_budget'):
                budget = result['document_budget']
                maximum = budget['max_model_calls']
                calls = (f"{budget['calls_reserved']} van {maximum}" if maximum is not None else "maximum volgt uit de taakplanning")
                progress += (f'<p>Documentbudget: vier uur inclusief wachttijd. '
                    f'Resterend: {esc(_minutes(budget["remaining_seconds"]))}. Modelaanroepen gereserveerd: {esc(calls)}.</p>')
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
            summary = ''
            if result['state'] in {'voltooid', 'onderbroken', 'mislukt', UNCHECKED}:
                summary = (f'<p>{result["candidates"]} gevormde kandidaten · {result["source_passages"]} overige bronpassages · {result["blocked"]} geblokkeerde kandidaten · {result["formation_blockers"]} verwerkingsblokkades.</p>'
                           f'<p>Poging technisch geslaagd: {"ja" if result["attempt_succeeded"] else "nee"}. '
                           f'Volledige bronverwerking: {"ja" if result["formation_complete"] else "nog niet bevestigd"}.</p>')
            if result['candidates'] is None:
                summary = '<p>Aantallen kandidaten en bronpassages zijn nog niet gecontroleerd. Open het document voor de actuele controles en vervolgacties.</p>'
            diagnosis_link = ('' if detail else f'<a class="btn-secondary" href="/source-selection?{esc(urlencode({"document": sid}))}#formation-problems">Vormingsproblemen</a>')
            diagnosis_link += f'<a class="btn-secondary" href="/inzicht/document?{esc(urlencode({"document": sid}))}">Bekijk diagnose in Inzicht</a>'
            if (detail and 'reviewer' in actor.get('roles', [])
                    and actor['account_id'] in envelope.get('named_reviewers', [])):
                diagnosis_link += (f'<a class="btn-secondary" href="/source-selection?{esc(urlencode({"document": sid, "task": "disposition"}))}">'
                                   'Brongebruik verantwoorden</a>')
                if review_path_for_klasse(envelope['class']) != 'boom':
                    diagnosis_link += (f'<a class="btn-secondary" href="/source-selection?{esc(urlencode({"document": sid, "task": "structure"}))}">'
                                       'Koppen controleren</a>')
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
                problems = source_recovery_controls(console._envelope(sid), status, actor)
                problems += ('<section class="formation-room" id="formation-problems">' +
                    _formation_problems_html(report, offset=offset, esc=esc, work_revision_url=work_revision_url) + '</section>')
            cards.append(f'<article class="doc-card" id="source-{esc(sid)}" data-source-document="{esc(sid)}" data-selected="{str(sid == selected).lower()}">'
                         f'<h2>{esc(result["title"])}</h2><p class="source-meta">{esc(result["filename"])} · Bronversie {esc(result["version"])} · {esc(extent)}</p>'
                         f'<p role="status">Status: {esc(result["state"])}</p>'
                         f'<p class="source-estimate">{esc(_estimate(result["estimate"]))}</p>'
                         f'{progress}{summary}<div class="source-actions">{action}{review}{diagnosis_link}</div>{problems}</article>')
        notice = '<div class="banner ok">Document veilig ontvangen. Start de bronverwerking wanneer je wilt.</div>' if request.query_params.get('received') == 'yes' else ''
        # Any visible running/waiting document keeps the overview current.
        # Every refresh reads the
        # durable authority; no browser state can start another attempt.
        script = '<script>setTimeout(function(){ window.location.reload(); }, 5000);</script>' if running_visible else ''
        script += '<script>document.querySelectorAll("form[action=\\"/source-selection/start\\"]").forEach(function(form){form.addEventListener("submit",function(event){if(form.dataset.submitting){event.preventDefault();return;}form.dataset.submitting="yes";form.querySelector("button").disabled=true;});});</script>'
        return HTMLResponse(page(nav(actor, 'selection') + '<section class="room" id="source-selection"><h1>Vorming</h1>' + notice
                    + '<form method="get" class="source-picker"><label for="source-document">Document</label>'
                    + '<div class="source-picker-row"><select id="source-document" name="document">' + options + '</select>'
                    + '<button class="btn-secondary" type="submit">Document selecteren</button></div></form>'
                    + (''.join(sorted(cards, key=lambda card: 'data-selected="true"' not in card)) or '<p data-source-empty>Geen documenten beschikbaar voor bronverwerking.</p>') + '</section>' + script),
                            headers={'Cache-Control': 'no-store'})

    @app.get('/formation-problems', response_class=HTMLResponse)
    def formation_problems_get(request: Request, document: str = '', offset: int = Query(0, ge=0)):
        require(request)
        # Historical bookmarks only navigate; the existing owner checks the
        # selected document and renders its one command form on the next GET.
        query = {'document': document} if document else {}
        if offset:
            query['offset'] = offset
        return RedirectResponse('/source-selection' + ('?' + urlencode(query) if query else ''),
                                status_code=303, headers={'Cache-Control': 'no-store'})

    @app.get('/inzicht/document/verwerkingsspoor')
    def processing_trace_export(request: Request, document: str = ''):
        from src.vorming.source_selection_v1 import authorize
        from src.vorming.processing_trace_v1 import processing_trace
        actor = require(request)
        envelope = console._envelope(document)
        authorize(console, actor['account_id'], envelope)
        return JSONResponse(processing_trace(envelope), headers={'Cache-Control': 'no-store',
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
