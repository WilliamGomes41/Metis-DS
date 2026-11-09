"""Ephemeral publisher preview/confirmation over the kernel test reset command."""
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.documents import test_document_deletion_v1 as domain
from src.operations_console_v1 import ConsoleError

MESSAGES = {
    'publisher_role_required':'Alleen publishers kunnen een heel testdocument verwijderen.',
    'test_document_deletion_disabled':'Testdocumenten verwijderen is hier uitgeschakeld.',
    'test_document_deletion_storage_not_ready':'Deze verwijderfunctie is nog niet gereed. Laat de beheerder de installatie controleren.',
    'test_document_deletion_grants_required':'Deze verwijderfunctie heeft nog geen databasebevoegdheid. Laat de beheerder dit instellen.',
    'test_document_deletion_database_mismatch':'De gegevensopslag ondersteunt deze verwijderfunctie niet. Neem contact op met de beheerder.',
    'test_document_deletion_confirmation_required':'Bevestig dat het hele document testgegevens bevat en verwijderd mag worden.',
    'test_document_deletion_command_invalid':'Vul een reden in en controleer de bevestiging opnieuw.',
    'delete_title_confirmation_required':'Typ de documenttitel exact over.',
    'test_document_deletion_plan_changed':'Het document is gewijzigd. Controleer de bijgewerkte versies en publicaties en bevestig opnieuw.',
    'test_document_deletion_processing_running':'Er loopt nog een verwerking. Stop die verwerking voordat je het testdocument verwijdert.',
    'test_document_deletion_shared_release':'Een publicatie verwijst ook naar andere gegevens. De beheerder moet dit eerst onderzoeken.',
    'test_document_deletion_cross_lineage_successor':'Een andere documentlijn verwijst naar deze versie. De beheerder moet dit eerst onderzoeken.',
    'test_document_deletion_lineage_required':'De documentlijn is niet vastgelegd. De beheerder moet dit eerst onderzoeken.',
    'test_document_deletion_command_conflict':'Deze bevestiging is al voor een ander verzoek gebruikt. Open het document opnieuw.',
    'test_document_deletion_receipt_missing':'De verwijderregistratie is niet gevonden.',
    'unknown_snapshot':'Dit document is niet meer aanwezig. Controleer Documenten.',
}


def control(account, snapshot_id, esc):
    if not domain.enabled() or 'publisher' not in (account or {}).get('roles', []):
        return ''
    return ('<p class="document-danger"><a href="/documents/test-delete?'+
        esc(urlencode({'document':snapshot_id}))+'">Hele testdocument verwijderen</a></p>')


def install(app, console, require, page, nav, esc):
    def error(actor, exc):
        status = (403 if exc.code in {'publisher_role_required','test_document_deletion_disabled'} else
                  404 if exc.code in {'unknown_snapshot','test_document_deletion_receipt_missing'} else 409)
        return HTMLResponse(page(nav(actor,'tree')+'<section class="room test-document-delete"><h1>Testdocument verwijderen</h1>'
            '<p class="banner warn" role="alert">'+esc(MESSAGES.get(exc.code,'De verwijdering kon niet worden uitgevoerd. Open Documenten en controleer de actuele toestand.'))+
            '</p><p><a href="/tree">Terug naar Documenten</a></p></section>',title='Testdocument verwijderen',stylesheets=('test-document-delete.css',)),
            status_code=status,headers={'Cache-Control':'no-store'})

    def render(actor, document, *, message='', values=None, status=200):
        try:
            plan = domain.preview(console,actor_id=actor['account_id'],snapshot_id=document)
        except ConsoleError as exc:
            return error(actor,exc)
        values = values or {}
        versions = ''.join('<li><strong>Bronversie '+esc(r['source_version'])+'</strong> — '+esc(r['title'])+
            '<p>Passages: '+str(r['objects'])+' · Annotaties: '+str(r['annotations'])+' · Beoordelingen: '+str(r['reviews'])+'</p></li>'
            for r in plan['versions'])
        if plan['historical_snapshot_ids']:
            versions += '<li><strong>Historische bronversies uit het publicatiearchief: '+str(len(plan['historical_snapshot_ids']))+'</strong></li>'
        disabled = bool(plan['running_snapshots'])
        if disabled:
            message = MESSAGES['test_document_deletion_processing_running']
        notice = '<p class="banner warn" role="alert">'+esc(message)+'</p>' if message else ''
        body = (nav(actor,'tree')+'<section class="room test-document-delete"><h1>Hele testdocument verwijderen</h1><h2>'+esc(plan['title'])+'</h2>'+
            '<p>Je verwijdert alle onderstaande versies, annotaties, beoordelingen en publicaties van dit testdocument uit Metis. '
            'De kennis is daarna ook via de API niet meer beschikbaar.</p>'+
            '<p><strong>Publicaties die verdwijnen: '+str(len(plan['release_ids']))+'.</strong></p><ul>'+versions+'</ul>'+
            '<p>De controlehistorie blijft bewaard. Bronbestanden en infrastructuurback-ups behouden hun bestaande bewaarbeleid.</p>'+
            notice+'<form method="post" action="/documents/test-delete">'
            '<input type="hidden" name="snapshot_id" value="'+esc(document)+'">'
            '<input type="hidden" name="command_id" value="'+esc(values.get('command_id') or uuid4().hex)+'">'
            '<input type="hidden" name="expected_plan" value="'+esc(plan['fingerprint'])+'">'
            '<label>Typ de exacte documenttitel<input name="confirm_title" required autocomplete="off" value="'+esc(values.get('confirm_title',''))+'"></label>'
            '<label>Reden voor verwijderen<textarea name="reason" required maxlength="1000" rows="3">'+esc(values.get('reason',''))+'</textarea></label>'
            '<label class="check"><input type="checkbox" name="confirmed_test" value="yes" required> '
            '<span>Dit hele document bevat testgegevens. Ik bevestig de verwijdering van alle versies en publicaties.</span></label>'
            '<button class="btn-primary" type="submit"'+(' disabled' if disabled else '')+'>Hele testdocument permanent verwijderen</button>'
            '</form><p><a href="/tree">Annuleren en terug naar Documenten</a></p></section>')
        return HTMLResponse(page(body,title='Testdocument verwijderen',stylesheets=('test-document-delete.css',)),status_code=status,headers={'Cache-Control':'no-store'})

    @app.get('/documents/test-delete', response_class=HTMLResponse)
    def preview(request: Request, document: str = ''):
        return render(require(request),document)

    @app.post('/documents/test-delete')
    def remove(request: Request, snapshot_id: str = Form(...), command_id: str = Form(...),
               expected_plan: str = Form(...), confirm_title: str = Form(''), reason: str = Form(''),
               confirmed_test: str = Form('')):
        actor = require(request)
        values = {'command_id':command_id,'confirm_title':confirm_title,'reason':reason}
        try:
            domain.delete(console,actor_id=actor['account_id'],snapshot_id=snapshot_id,command_id=command_id,
                expected_plan=expected_plan,confirm_title=confirm_title,reason=reason,confirmed_test=confirmed_test=='yes')
        except ConsoleError as exc:
            if exc.code in {'delete_title_confirmation_required','test_document_deletion_confirmation_required',
                            'test_document_deletion_command_invalid','test_document_deletion_plan_changed'}:
                return render(actor,snapshot_id,message=MESSAGES[exc.code],values=values,
                              status=409 if exc.code=='test_document_deletion_plan_changed' else 400)
            return error(actor,exc)
        return RedirectResponse('/documents/test-delete/receipt?'+urlencode({'command':command_id}),status_code=303)

    @app.get('/documents/test-delete/receipt',response_class=HTMLResponse)
    def receipt(request: Request, command: str = ''):
        actor = require(request)
        try:
            result = domain.receipt(console,actor_id=actor['account_id'],command_id=command)
        except ConsoleError as exc:
            return error(actor,exc)
        return HTMLResponse(page(nav(actor,'tree')+'<section class="room test-document-delete"><h1>Testdocument verwijderd</h1>'
            '<p role="status">De verwijdering is opgeslagen. Versies: '+str(result['versions'])+
            '. Publicaties: '+str(result['publications'])+'.</p><p>Het document is uit Metis en de API verwijderd.</p>'
            '<p><a class="btn-primary" href="/tree">Terug naar Documenten</a></p></section>',title='Testdocument verwijderd',stylesheets=('test-document-delete.css',)),
            headers={'Cache-Control':'no-store'})
