"""Thin forms over the kernel's source-bound route commands."""
from __future__ import annotations

import html
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.decision_graph_v1 import CONTRACT, publication_issues
from src.operations_console_v1 import ConsoleError


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def options(values, selected=""):
    return "".join(f'<option value="{esc(k)}" {"selected" if k == selected else ""}>{esc(v)}</option>' for k, v in values)


def install_decision_review_routes(app, console, require, page):
    def authorized(request, sid, *, graph_required=True):
        actor = require(request)
        env = console._envelope(sid)
        if "reviewer" not in actor["roles"] or actor["account_id"] not in env["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        if graph_required and "decision_graph" not in env:
            raise ConsoleError("decision_graph_not_available")
        return actor, env

    @app.get("/review/policy", response_class=HTMLResponse)
    def policy_get(request: Request, document: str):
        actor = require(request)
        env = console._envelope(document)
        if ((env.get("review_policy") or {}).get("contract") == "managed-review-v2" and not console.snapshot_is_published(document)) or ("publisher" in actor["roles"] and actor["account_id"] not in env["named_reviewers"]):
            return RedirectResponse(f"/review/participants?document={document}", status_code=303)
        actor, env = authorized(request, document, graph_required=False)
        policy = env.get("review_policy") or {"primary": env["uploader_account_id"], "revision": 0, "assignments": []}
        assignments = {r["reviewer_id"]: r["participation"] for r in policy["assignments"]}
        people = [(r["account_id"], r["display_name"]) for r in console.list_reviewer_accounts()]
        fields = "".join(f'<label>{esc(name)}<input type="hidden" name="reviewer" value="{esc(oid)}">'
                         f'<select name="participation">{options([("none", "Niet toegewezen"), ("optional", "Optioneel"), ("required", "Verplicht")], assignments.get(oid, "none"))}</select></label>'
                         for oid, name in people)
        from src.operations_console_v1 import ALLOWED_CLASSES
        successor = (f'<label>Klasse van opvolgende werkrevisie<select name="new_class">'
                     f'{options([(c, c) for c in sorted(ALLOWED_CLASSES)], env["class"])}</select></label>'
                     '<button formaction="/review/successor">Nieuwe werkrevisie maken</button>'
                     if "researcher" in actor["roles"] else '')
        update = ''
        return page(f'<a href="/review/participants?document={esc(document)}">Deelnemers van dit traject beheren</a><h1>Nieuwe werkrevisie</h1><p>Dit formulier maakt een nieuwe werkrevisie met eigen reviewbewijs. Gepubliceerde historie blijft gesloten.</p>'
                    f'<form method="post"><input type="hidden" name="document" value="{esc(document)}">'
                    f'<input type="hidden" name="expected_revision" value="{esc(console.objects_revision(document))}">'
                    f'<input type="hidden" name="command_id" value="{uuid.uuid4().hex}">'
                    f'<input type="hidden" name="policy_revision" value="{policy["revision"] + 1}">'
                    f'<label>Primaire reviewer<select name="primary">{options(people, policy["primary"])}</select></label>'
                    f'{fields}<label>Reden<input name="reason" required></label>{update}{successor}</form>')

    @app.post("/review/policy")
    @app.post("/review/successor")
    async def policy_post(request: Request):
        from src.review_policy_v1 import CONTRACT as POLICY_CONTRACT
        form = await request.form()
        sid = str(form.get("document") or "")
        actor, _ = authorized(request, sid, graph_required=False)
        ids, participation = form.getlist("reviewer"), form.getlist("participation")
        if len(ids) != len(participation):
            raise ConsoleError("invalid_review_assignment")
        try:
            revision = int(form.get("policy_revision") or "")
        except ValueError as exc:
            raise ConsoleError("invalid_review_policy") from exc
        primary = str(form.get("primary") or "")
        policy = {"contract": POLICY_CONTRACT, "revision": revision, "primary": primary,
                  "assignments": [{"reviewer_id": oid, "participation": role} for oid, role in zip(ids, participation)
                                  if role != "none" and oid != primary]}
        command = dict(actor_id=actor["account_id"], snapshot_id=sid, policy=policy,
            command_id=str(form.get("command_id") or ""), expected_revision=str(form.get("expected_revision") or ""),
            reason=str(form.get("reason") or ""))
        if request.url.path == "/review/successor":
            receipt = console.create_review_successor(**command, class_=str(form.get("new_class") or ""))
            sid = receipt["snapshot_id"]
        else:
            console.change_review_policy(**command)
        return RedirectResponse(f"/review/policy?document={sid}", status_code=303)

    @app.get("/review/decision-graph", response_class=HTMLResponse)
    def graph_get(request: Request, document: str):
        actor, env = authorized(request, document)
        rows = [o for o in console.snapshot_objects(document) if o["object_type"] != "document"]
        graph = env["decision_graph"]
        nodes = {n["object_id"]: n for n in graph["nodes"]}
        names = [(o["object_id"], o["content"]["clean_text"][:150]) for o in rows]
        text_evidence = [("", "Geen antwoordlabel")]
        graphic_evidence = []
        for k, v in env["decision_graph_evidence"]["items"].items():
            if v["kind"] == "text":
                text_evidence.append((k, v["text"]))
            elif v["kind"] == "export_edge":
                graphic_evidence.append((k, f'Bronverbinding: {v["record"]}'))
                if v.get("text"):
                    text_evidence.append((k, v["text"]))
            elif v["kind"] == "graphic":
                graphic_evidence.append((k, f'Pagina {v["page"]}, lijngebied {v["bbox"]}'))
        modes = [("unresolved", "Nog bepalen"), ("single", "Eén antwoord"), ("multiple", "Meerdere antwoorden"),
                 ("continue", "Vervolgstap"), ("terminal", "Eindpunt"), ("context", "Broncontext / label")]
        fields = []
        for o in rows:
            oid = o["object_id"]
            bundle = (o.get("metadata") or {}).get("result_bundle")
            bundle_note = ('<small>Onderdeel van een resultaatbundel: kies broncontext; de route hoort bij de bundel.</small>'
                           if bundle and bundle["role"] == "member" else '')
            fields.append(f'<p>{esc(o["content"]["clean_text"])}<input type="hidden" name="node_id" value="{esc(oid)}">'
                          f'{bundle_note}'
                          f'<select name="node_mode">{options(modes, nodes.get(oid, {}).get("mode", "unresolved"))}</select>'
                          f'<label><input type="checkbox" name="entrypoint" value="{esc(oid)}" {"checked" if oid in graph["entrypoints"] else ""}>Beginpunt</label></p>')
        edges = []
        for i, edge in enumerate([*graph["edges"], {}, {}, {}]):
            evidence = edge.get("evidence_ids", [])
            label_id = next((k for k, text in text_evidence if k in evidence and text == edge.get("label")), "")
            edges.append(f'<fieldset><legend>Route {i + 1}</legend>'
                         f'<label>Van<select name="from">{options([("", "Geen route"), *names], edge.get("from"))}</select></label>'
                         f'<label>Naar<select name="to">{options(names, edge.get("to"))}</select></label>'
                         f'<label>Routevorm<select name="kind">{options([("continue", "Onvoorwaardelijk vervolg"), ("answer", "Antwoord")], edge.get("kind"))}</select></label>'
                         f'<label>Letterlijk antwoord<select name="label">{options(text_evidence, label_id)}</select></label>'
                         f'<label>Lijnbewijs<select name="evidence-{i}" multiple>{"".join(options([(k, v)], k if k in evidence else "") for k,v in graphic_evidence)}</select></label></fieldset>')
        revision = console.objects_revision(document)
        common = f'<input type="hidden" name="document" value="{esc(document)}"><input type="hidden" name="expected_revision" value="{esc(revision)}">'
        co_review = ""
        if actor["account_id"] != env["review_policy"]["primary"]:
            co_review = "<h2>Passages mede-beoordelen</h2>" + "".join(
                f'<form method="post" action="/review/decision-passage">{common}'
                f'<p>{esc(o["content"]["clean_text"])}</p><input type="hidden" name="object_id" value="{esc(o["object_id"])}">'
                '<button>Deze actuele passage bevestigen</button></form>' for o in rows)
        problems = publication_issues(env, console.snapshot_objects(document))
        proposals = env.get("decision_graph_proposals", [])
        proposal_note = (f'<p>{len(proposals)} geometrische routevoorstellen. Richting, antwoordlabel en eindpunten '
                         'zijn nog niet bevestigd. Controleer ook routes die niet zijn herkend.</p>' if proposals else '')
        original = f'/review/brondocument?document={esc(document)}&amp;object={esc(rows[0]["object_id"])}' if rows else ""
        return page(f'<h1>Beslisroutes controleren</h1><p>Controleer iedere route en ieder antwoord tegen de originele pagina. Extra review vervangt ontbrekend bronbewijs niet.</p>'
                    f'<p><a href="/review?document={esc(document)}">Passages beoordelen</a> · <a href="{original}">Open origineel</a> · <a href="/review/policy?document={esc(document)}">Reviewdeelname</a></p>'
                    f'{proposal_note}<p>Open controles: {esc(", ".join(problems) or "geen")}</p>{co_review}'
                    f'<form method="post">{common}<input type="hidden" name="command_id" value="{uuid.uuid4().hex}">'
                    + "".join(fields + edges) + '<label>Toelichting<input name="reason" required></label>'
                    '<button name="action" value="graph">Routes opslaan</button></form>'
                    f'<form method="post">{common}<input type="hidden" name="command_id" value="{uuid.uuid4().hex}">'
                    '<label>Verklaring broncontrole<input name="reason" required></label><button name="action" value="confirm">Actuele volledige graaf bevestigen</button></form>')

    @app.post("/review/decision-passage")
    async def passage_post(request: Request):
        form = await request.form()
        sid = str(form.get("document") or "")
        actor, _ = authorized(request, sid)
        revision = str(form.get("expected_revision") or "")
        if not revision:
            raise ConsoleError("decision_review_command_required")
        console.approve_second_review(actor_id=actor["account_id"], snapshot_id=sid,
            object_id=str(form.get("object_id") or ""), expected_revision=revision)
        return RedirectResponse(f"/review/decision-graph?document={sid}", status_code=303)

    @app.post("/review/decision-graph")
    async def graph_post(request: Request):
        form = await request.form()
        sid = str(form.get("document") or "")
        actor, env = authorized(request, sid)
        command = dict(actor_id=actor["account_id"], snapshot_id=sid,
                       command_id=str(form.get("command_id") or ""), reason=str(form.get("reason") or ""),
                       expected_revision=str(form.get("expected_revision") or ""))
        if form.get("action") == "confirm":
            console.confirm_decision_graph(**command)
        elif form.get("action") == "graph":
            current = {o["object_id"]: o for o in console.snapshot_objects(sid)}
            ids, modes = form.getlist("node_id"), form.getlist("node_mode")
            if len(ids) != len(modes) or any(i not in current for i in ids):
                raise ConsoleError("decision_graph_node_invalid")
            nodes = [{"object_id": oid, "object_version": current[oid]["object_version"], "mode": mode,
                      "evidence_ids": [r["raw_object_id"] for r in current[oid]["provenance"]["source_fragments"]]}
                     for oid, mode in zip(ids, modes)]
            arrays = [form.getlist(k) for k in ("from", "to", "kind", "label")]
            if len({len(a) for a in arrays}) != 1:
                raise ConsoleError("decision_graph_edge_invalid")
            edges = []
            inventory = env["decision_graph_evidence"]["items"]
            for i, (src, dest, kind, label_id) in enumerate(zip(*arrays)):
                if not src:
                    continue
                label = inventory.get(label_id, {}).get("text", "") if kind == "answer" else ""
                evidence = form.getlist(f"evidence-{i}") + ([label_id] if label_id else [])
                edges.append({"id": f"route-{i}", "from": src, "to": dest, "kind": kind, "label": label, "evidence_ids": evidence})
            graph = {"contract": CONTRACT, "source_sha256": env["sha256"], "nodes": nodes,
                     "edges": edges, "entrypoints": form.getlist("entrypoint"), "unresolved": []}
            console.update_decision_graph(**command, graph=graph)
        else:
            raise ConsoleError("decision_review_action_invalid")
        return RedirectResponse(f"/review/decision-graph?document={sid}", status_code=303)
