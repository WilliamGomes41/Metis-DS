"""Read-only team projections and thin forms over participation commands."""
from collections import Counter
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.decision_review_ui_v1 import esc, options
from src.operations_console_v1 import ConsoleError
from src.review_policy_v1 import participants


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
            f'</select></label><label>Zoeken<input name="q" value="{esc(q)}"></label><button>Filteren</button></form>')


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
    for env in visible:
        assigned = account['account_id'] in env['named_reviewers'] and 'reviewer' in account['roles']
        sid = env['snapshot_id']
        action = f'<a href="/review?{esc(urlencode({"document":sid}))}">Mijn reviewwerk</a>' if assigned else '<span>Alleen lezen</span>'
        cards.append('<article class="doc-card">'+ui._document_summary(env)+roster(console,env)+action+
                     f' · <a href="/review/trajectory?{esc(urlencode({"document":sid}))}">Traject bekijken</a></article>')
    return ui._page(ui._nav(account, 'review')+'<h1>Review</h1>'+filters(console,work='all',theme=theme,q=q)+pagination+
                    ''.join(cards)+('' if cards else '<p>Geen reviewtrajecten gevonden.</p>'), title='Review — Metis')


def install_routes(app, console, require, page):
    def read(request, sid):
        actor = require(request); require_overview(actor)
        return actor, console._envelope(sid)

    @app.get('/review/trajectory', response_class=HTMLResponse)
    def trajectory(request: Request, document: str):
        actor, env = read(request, document)
        rows = console.snapshot_objects(document)
        counts = Counter(o.get('governance',{}).get('validation_status','onbekend') for o in rows if o['object_type'] != 'document')
        content = ''.join('<li>'+esc(o.get('content',{}).get('clean_text',''))+' — '+esc(o.get('governance',{}).get('validation_status',''))+'</li>' for o in rows if o['object_type'] != 'document')
        names = people(console)
        history = ''.join('<li>'+esc(f'{e["at"]}: {names.get(e["actor_id"], e["actor_id"])} — {e["action"]}: {names.get(e["reviewer_id"], e["reviewer_id"])} → {names.get(e.get("replacement_id"), e.get("replacement_id") or "—")} — {e["reason"]}')+'</li>' for e in env.get('review_participation_history',[]))
        labels = {o['object_id']: o.get('content',{}).get('clean_text','')[:180] for o in rows}
        graph = env.get('decision_graph',{})
        routes = ''.join('<li>'+esc(f'{labels.get(e["from"], "Onbekende stap")} → {labels.get(e["to"], "Onbekende stap")}: {e.get("label", "")}')+'</li>' for e in graph.get('edges',[]))
        assigned = actor['account_id'] in env['named_reviewers'] and 'reviewer' in actor['roles']
        can_manage = assigned or 'publisher' in actor['roles']
        manage = f'<a href="/review/participants?{esc(urlencode({"document":document}))}">Deelnemers beheren</a>' if can_manage and not console.snapshot_is_published(document) else ''
        bindings = console.object_review_bindings(document)
        decisions = ''.join('<li>'+esc(f'{names.get(b.get("reviewer_id"), b.get("reviewer", ""))}: {b.get("decision")} — {b.get("object_id")} / {b.get("object_version")} — '+('actueel' if b.get('valid') else 'historisch'))+'</li>' for b in bindings)
        return page('<h1>'+esc(env['title'])+'</h1><p>Trajectoverzicht — alleen lezen. Bekijken geldt niet als beoordeling.</p>'+roster(console,env)+
                    '<p>'+esc(dict(counts))+'</p>'+manage+'<h2>Passages</h2><ul>'+content+'</ul><h2>Routes</h2><ul>'+routes+
                    '</ul><h2>Beoordelingen</h2><ul>'+decisions+'</ul><h2>Deelnamehistorie</h2><ul>'+history+'</ul>')

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
        candidates = [(i,n) for i,n in names.items() if 'reviewer' in console._account(i)['roles'] and not console._account(i).get('retirement')]
        policy = env.get('review_policy')
        current = [policy['primary'], *[r['reviewer_id'] for r in policy['assignments']]] if policy else env['named_reviewers']
        forms = []
        actions = [('add_optional','Optionele reviewer toevoegen')]
        if publisher:
            actions += [('add_required','Verplichte reviewer toevoegen'),('replace','Reviewer vervangen'),('archive','Deelname archiveren')]
        if not policy and not publisher:
            actions = []
        for action,label in actions:
            choices = candidates if action.startswith('add_') else [(i,names.get(i,i)) for i in current]
            extra = '<label>Vervanger<select name="replacement_id">'+options(candidates)+'</select></label>' if action=='replace' else ''
            forms.append(f'<form method="post"><h2>{esc(label)}</h2><input type="hidden" name="document" value="{esc(document)}">'
                f'<input type="hidden" name="action" value="{action}"><input type="hidden" name="command_id" value="{uuid4().hex}">'
                f'<input type="hidden" name="expected_revision" value="{esc(console.objects_revision(document))}">'
                '<label>Reviewer<select name="reviewer_id">'+options(choices)+'</select></label>'+extra+
                '<label>Reden<input name="reason" required maxlength="2000"></label><button>'+esc(label)+'</button></form>')
        note = '<p>Een publisher activeert bij de eerste wijziging expliciet het deelnemersbeheer. Bestaande verplichte reviewers en onafhankelijkheid blijven behouden.</p>' if not policy else ''
        return page('<h1>Deelnemers beheren</h1>'+roster(console,env)+note+
                    '<p>Archiveren bewaart historie. Een verplichte plek blijft open tot vervanging. De vervanger beoordeelt zelf; geldig werk van anderen blijft behouden. Vervang de primaire reviewer in één handeling.</p>'+
                    ''.join(forms))

    @app.post('/review/participants')
    async def change(request: Request):
        actor = require(request)
        form = await request.form()
        command = {k: str(form.get(k) or '') for k in ('action','command_id','expected_revision','reason','reviewer_id','replacement_id')}
        sid = str(form.get('document') or '')
        console.manage_review_participation(actor_id=actor['account_id'], snapshot_id=sid, **command)
        return RedirectResponse('/review/trajectory?'+urlencode({'document':sid}), status_code=303)
