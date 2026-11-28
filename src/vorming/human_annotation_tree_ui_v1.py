"""The decision-tree controls of the annotation card."""
from html import escape
import json
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid4, uuid5

from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_v1 as domain
from src.vorming.decision_tree_construction_v1 import proposal_inputs
from src.vorming.human_annotation_decision_tree_v1 import empty_entries, export_entries


def tree_card(console, actor_id, envelope):
    sid = envelope['snapshot_id']
    scope = {'actor_id': actor_id, 'snapshot_id': sid}
    state = build.overview(console, **scope)
    row, fragments = domain._read_set(console, sid)
    inventory = row['extraction']['tree_source']['inventory']
    export = envelope['content_kind'] == 'boom'
    saved = state['entries'][0] if state['entries'] else None
    graph = saved['graph'] if saved else export_entries(fragments, inventory) if export else empty_entries()
    blocks = proposal_inputs(fragments)
    command = {'snapshot_id': sid, 'annotation_id': saved['annotation_id'] if saved else str(uuid5(NAMESPACE_URL, sid)),
               'expected_revision': saved['revision'] if saved else 0, 'expected_generation': state['generation'],
               'extraction_hash': state['extraction_hash'], 'normalization': state['normalization'],
               'expected_objects_revision': state['objects_revision']}
    data = json.dumps({'command': command, 'graph': graph, 'export': export, 'blocks': blocks,
                       'evidence': inventory['items']}, ensure_ascii=True).replace('<', r'\u003c')
    query = escape(urlencode({'document': sid}))
    content = f'<h1>Beslisboom annoteren</h1><h2>{escape(envelope["title"])}</h2><p><a href="/annotations/original?{query}">Originele bron downloaden</a></p>'
    if not export:
        content += ('<fieldset><legend>Bronselectie</legend><label>Bronpassage <select id="tree-block"></select></label>'
                    '<p>Wijs de tekst in de bron aan en kies welke rol die in de beslisboom heeft.</p>'
                    '<p id="tree-passage" tabindex="0"></p><button type="button" id="tree-whole">Hele passage aanwijzen</button>'
                    '<p id="tree-selection" role="status"></p><label>Rol <select id="tree-role"><option value="">Kies een rol</option></select></label>'
                    '<button type="button" disabled id="tree-add-unit">Selectie labelen</button></fieldset>')
    content += '<section><h2>Gelabelde bronpassages</h2><div id="tree-units"></div></section><section><h2>Verbindingen</h2><ul id="tree-edges"></ul>'
    if not export:
        content += ('<fieldset><legend>Verbinding aanwijzen</legend><label>Van <select id="tree-from"></select></label>'
                    '<label>Naar <select id="tree-to"></select></label><label>Soort <select id="tree-kind">'
                    '<option value="answer">Antwoord</option><option value="continue">Doorgaande pijl</option>'
                    '<option value="page_transition">Paginaovergang</option></select></label>'
                    '<label>Bronbewijs <select id="tree-evidence" multiple></select></label>'
                    '<button type="button" id="tree-add-edge">Verbinding vastleggen</button></fieldset>'
                    '<fieldset><legend>Context koppelen</legend><label>Contextpassage <select id="tree-context"></select></label>'
                    '<label>Geldt voor <select id="tree-applies" multiple></select></label>'
                    '<button type="button" id="tree-bind">Context koppelen</button></fieldset><ul id="tree-bindings"></ul>'
                    '<fieldset><legend>Twijfellabel</legend><label>Passage of verbinding <select id="tree-subject"></select></label>'
                    '<label>Reden <select id="tree-code"></select></label><button type="button" id="tree-add-doubt">Twijfel vastleggen</button></fieldset>')
    content += '</section><ul id="tree-doubts"></ul><button id="tree-save" class="btn-primary">Annotatie opslaan</button><p id="tree-status" role="status"></p>'
    if state['can_finalize']:
        fields = {'document': sid, 'command_id': str(uuid4()), 'overview_hash': state['overview_hash'],
                  'expected_generation': state['generation'], 'expected_revision': state['objects_revision']}
        content += '<form id="tree-build" method="post" action="/annotations/finalize">'+''.join(
            f'<input type="hidden" name="{k}" value="{escape(str(v))}">' for k, v in fields.items()
        )+'<button type="submit">Afronden en bouwen</button></form>'
    content += f'<p><a href="/annotations/build?{query}">Bouwstatus</a> · <a href="/review?{query}">Naar review</a></p>'
    if console.snapshot_is_published(sid):
        content = '<p>Deze gepubliceerde versie is alleen te lezen.</p><fieldset disabled>'+content+'</fieldset>'
    return content+f'<script type="application/json" id="tree-input">{data}</script><script defer src="/annotations/tree.js"></script>'
