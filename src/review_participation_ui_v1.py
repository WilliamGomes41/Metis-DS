"""Read-only team projections and thin forms over participation commands."""
from collections import Counter
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.decision_review_ui_v1 import esc, options
from src.operations_console_v1 import ConsoleError
from src.review_policy_v1 import archived_required, participants, required_reviewers


ACTION_LABELS = {
    'add_optional': 'Optionele reviewer toegevoegd',
    'add_required': 'Verplichte reviewer toegevoegd',
    'archive': 'Deelname gearchiveerd',
    'replace': 'Reviewer vervangen',
}
DECISION_LABELS = {
    'approve': 'Goedgekeurd', 'reject': 'Afgewezen',
    'revise': 'Correctie voorgesteld', 'later': 'Uitgesteld',
}


def navigation(actor, document=None):
    from src.operations_console_app import _nav
    links = '<a href="/review?work=all">Terug naar reviewoverzicht</a>'
    if document:
        links += f' · <a href="/review/trajectory?{esc(urlencode({"document": document}))}">Terug naar traject</a>'
    return _nav(actor, 'review') + '<nav aria-label="Reviewnavigatie">'+links+'</nav>'


def participation_choices(console, env):
    """Presentation of existing command rules; commands recheck on submission."""
    from src.review_participation_v1 import _reviewer
    candidates = []
    for account in console.list_accounts():
        try:
            _reviewer(console, account['account_id'])
        except ConsoleError:
            continue
        candidates.append((account['account_id'], account['display_name']))
    policy = env.get('review_policy')
    active = set(participants(policy) if policy else env['named_reviewers'])
    required = required_reviewers(policy) if policy else active
    archived = archived_required(policy) if policy else set()
    primary = policy['primary'] if policy else env['named_reviewers'][0]
    current = [primary, *[r['reviewer_id'] for r in policy['assignments']]] if policy else env['named_reviewers']
    return {
        'add_optional': [(i,n) for i,n in candidates if i not in active | archived],
        'add_required': [(i,n) for i,n in candidates if i not in active],
        'archive': [i for i in current if i in active and i != primary],
        'replace': [(target, [(i,n) for i,n in candidates if i not in active | required | {target}]) for target in current],
    }


def require_overview(account):
    if not set(account["roles"]) & {"reviewer", "publisher"}:
        raise ConsoleError("reviewer_role_required")


def people(console):
    return {a["account_id"]: a["display_name"] for a in console.list_accounts()}


def roster(console, env, names=None):
    names = people(console) if names is None else names
    policy = env.get("review_policy")
    if not policy:
        return '<p>Toegewezen: ' + esc(', '.join(names.get(i, i) for i in env["named_reviewers"])) + '</p>'
    text = [f'{names.get(policy["primary"], policy["primary"])} — primair']
    for row in policy["assignments"]:
        role = 'verplicht' if row['participation'] == 'required' else 'optioneel'
        status = ' (gearchiveerd; vervanging nodig)' if row.get('status') == 'archived' and role == 'verplicht' else ' (gearchiveerd)' if row.get('status') == 'archived' else ''
        text.append(f'{names.get(row["reviewer_id"], row["reviewer_id"])} — {role}{status}')
    return '<p>Reviewdeelname: ' + esc('; '.join(text)) + '</p>'


def filters(console, *, work, theme, q='', rows=None):
    rows = console.list_envelopes() if rows is None else rows
    themes = sorted({str(e.get('family') or '') for e in rows} - {''})
    return ('<form method="get" action="/review"><label>Werk<select name="work">' +
            options([('mine', 'Mijn werk'), ('all', 'Alle reviewtrajecten')], work) +
            '</select></label><label>Thema<select name="theme">' +
            options([('', 'Alle thema’s'), *[(t, t) for t in themes]], theme) +
            f'</select></label><label>Zoeken<input name="q" value="{esc(q)}"></label><button class="btn-secondary">Filteren</button></form>')


def overview(console, account, *, theme='', q='', page=1):
    require_overview(account)
    from src import operations_console_app as ui
    from src.review_workboard_v1 import _lifecycle_for_work_item
    rows = []
    for env in console.list_envelopes():
        if theme and env.get('family') != theme:
            continue
        life = _lifecycle_for_work_item(console, env['snapshot_id'])
        if life['workflow_status'] == 'closed':
            continue
        rows.append({**env, 'meaningful_status': life['workflow_status']})
    visible, pagination = ui._document_list_page(rows, q=q, page=page, path='/review')
    pagination = pagination[pagination.index('<nav '):]
    # Keep the selection on every paging link without changing the query helper.
    pagination = pagination.replace('/review?', '/review?'+esc(urlencode({'work':'all','theme':theme}))+'&amp;')
    cards = []
    names = people(console)
    for env in visible:
        assigned = account['account_id'] in env['named_reviewers'] and 'reviewer' in account['roles']
        sid = env['snapshot_id']
        action = f'<a href="/review?{esc(urlencode({"document":sid}))}">Mijn reviewwerk</a>' if assigned else '<span>Alleen lezen</span>'
        cards.append('<article class="doc-card">'+ui._document_summary(env)+roster(console,env,names)+action+
                     f' · <a href="/review/trajectory?{esc(urlencode({"document":sid}))}">Traject bekijken</a></article>')
    return ui._page(ui._nav(account, 'review')+'<h1>Review</h1>'+filters(console,work='all',theme=theme,q=q)+pagination+
                    ''.join(cards)+('' if cards else '<p>Geen reviewtrajecten gevonden.</p>'), title='Review — Metis')


def install_routes(app, console, require, page):
    def read(request, sid):
        actor = require(request); require_overview(actor)
        return actor, console._envelope(sid)

    @app.get('/review/trajectory', response_class=HTMLResponse)
    def trajectory(request: Request, document: str):
        from src.operations_console_app import STATUS_LABELS
        actor, env = read(request, document)
        rows = console.snapshot_objects(document)
        counts = Counter(o.get('governance',{}).get('validation_status','onbekend') for o in rows if o['object_type'] != 'document')
        passages = [o for o in rows if o['object_type'] != 'document']
        numbers = {o['object_id']: f'Passage {i}' for i,o in enumerate(passages, 1)}
        content = ''.join('<li><strong>'+esc(numbers[o['object_id']])+':</strong> '+esc(o.get('content',{}).get('clean_text',''))+' — '+esc(STATUS_LABELS.get(o.get('governance',{}).get('validation_status'), 'status onbekend'))+'</li>' for o in passages)
        names = people(console)
        history = []
        for entry in env.get('review_participation_history', []):
            target = names.get(entry['reviewer_id'], 'Voormalige reviewer')
            if entry.get('replacement_id'):
                target += ' → ' + names.get(entry['replacement_id'], 'Voormalige reviewer')
            history.append('<li>'+esc(f'{entry["at"]} — {names.get(entry["actor_id"], "Voormalige gebruiker")}: {ACTION_LABELS.get(entry["action"], "Deelname gewijzigd")} — {target}. Reden: {entry["reason"]}')+'</li>')
        labels = {o['object_id']: o.get('content',{}).get('clean_text','')[:180] for o in rows}
        graph = env.get('decision_graph',{})
        routes = ''.join('<li>'+esc(f'{labels.get(e["from"], "Onbekende stap")} → {labels.get(e["to"], "Onbekende stap")}' + (': '+e['label'] if e.get('label') else ''))+'</li>' for e in graph.get('edges',[]))
        assigned = actor['account_id'] in env['named_reviewers'] and 'reviewer' in actor['roles']
        can_manage = assigned or 'publisher' in actor['roles']
        manage = f'<a href="/review/participants?{esc(urlencode({"document":document}))}">Deelnemers beheren</a>' if can_manage and not console.snapshot_is_published(document) else ''
        bindings = console.object_review_bindings(document)
        decisions = ''.join('<li>'+esc(f'{names.get(b.get("reviewer_id"), b.get("reviewer") or "Voormalige reviewer")}: {DECISION_LABELS.get(b.get("decision"), "Beoordeling vastgelegd")} — {numbers.get(b.get("object_id"), "Eerdere passage")} (versie {b.get("object_version")}) — '+('actueel' if b.get('valid') else 'historisch'))+'</li>' for b in bindings)
        summary = '; '.join(f'{count} {STATUS_LABELS.get(status, "status onbekend")}' for status,count in counts.items()) or 'Nog geen passages beschikbaar.'
        return page(navigation(actor)+'<h1>'+esc(env['title'])+'</h1><p>Trajectoverzicht — alleen lezen. Bekijken geldt niet als beoordeling.</p>'+roster(console,env,names)+
                    '<p>'+esc(summary)+'</p>'+manage+'<h2>Passages</h2><ul>'+content+'</ul><h2>Routes</h2><ul>'+routes+
                    '</ul><h2>Beoordelingen</h2><ul>'+decisions+'</ul><h2>Deelnamehistorie</h2><ul>'+''.join(history)+'</ul>')

    @app.get('/review/participants', response_class=HTMLResponse)
    def manage(request: Request, document: str):
        actor, env = read(request, document)
        publisher = 'publisher' in actor['roles']
        assigned = 'reviewer' in actor['roles'] and actor['account_id'] in env['named_reviewers']
        if not publisher and not assigned:
            raise ConsoleError('participation_publisher_required')
        if console.snapshot_is_published(document):
            raise ConsoleError('published_working_revision_immutable')
        names = people(console)
        policy = env.get('review_policy')
        choices = participation_choices(console, env)
        revision = console.objects_revision(document)
        forms = []

        def form(action, label, available, target=None):
            if not available:
                return '<section><h2>'+esc(label)+'</h2><p>Geen beschikbare reviewers voor deze handeling.</p></section>'
            field = 'replacement_id' if target else 'reviewer_id'
            selector = f'<label>{"Vervanger" if target else "Reviewer"}<select name="{field}">'+options(available)+'</select></label>'
            if target:
                selector += f'<input type="hidden" name="reviewer_id" value="{esc(target)}">'
            return (f'<form method="post"><h2>{esc(label)}</h2><input type="hidden" name="document" value="{esc(document)}">'
                f'<input type="hidden" name="action" value="{action}"><input type="hidden" name="command_id" value="{uuid4().hex}">'
                f'<input type="hidden" name="expected_revision" value="{esc(revision)}">'+selector+
                '<label>Reden<input name="reason" required maxlength="2000"></label><button class="btn-secondary">'+esc(label)+'</button></form>')

        actions = [('add_optional','Optionele reviewer toevoegen')]
        if publisher:
            actions += [('add_required','Verplichte reviewer toevoegen'),('archive','Deelname archiveren')]
        if not policy and not publisher:
            actions = []
        for action,label in actions:
            available = choices[action] if action.startswith('add_') else [(i,names.get(i,'Voormalige reviewer')) for i in choices[action]]
            forms.append(form(action, label, available))
        if publisher:
            for target, available in choices['replace']:
                forms.append(form('replace', 'Reviewer vervangen: '+names.get(target,'Voormalige reviewer'), available, target))
        from src.operations_console_app import _task_links
        note = _task_links('review')
        return page(navigation(actor,document)+'<h1>Deelnemers beheren</h1><p>'+esc(env['title'])+'</p>'+roster(console,env,names)+note+
                    ''.join(forms))

    @app.post('/review/participants')
    async def change(request: Request):
        actor = require(request)
        form = await request.form()
        command = {k: str(form.get(k) or '') for k in ('action','command_id','expected_revision','reason','reviewer_id','replacement_id')}
        sid = str(form.get('document') or '')
        request.state.review_participation_document = sid
        console.manage_review_participation(actor_id=actor['account_id'], snapshot_id=sid, **command)
        return RedirectResponse('/review/trajectory?'+urlencode({'document':sid}), status_code=303)
