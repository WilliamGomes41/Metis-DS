"""Controlled findings on real received sources and the native workflow store."""
from copy import deepcopy

from src.vorming.bounded_model_call_v1 import ModelCallLimits
from src.operations_console_v1 import ConsoleError
from src.vorming.processing_retry_v1 import reserve, finish, now


def blocked_source(console, author, reviewer, name, *, pages=False):
    import fitz
    with fitz.open() as pdf:
        pdf.new_page().insert_text((72, 72), 'Controleer de broninhoud.')
        pdf.new_page().insert_text((72, 72), 'Alle rechten voorbehouden.')
        data = pdf.tobytes()
    sid = console.receive_source(actor_id=author, filename=name + '.pdf', data=data,
        content_type='application/pdf', ingest_kind='new', title=name, version='1',
        date='2026-10-26', live_url='', class_='richtlijn', family=name,
        named_reviewers=[author, reviewer], command_id='receive-' + name)['snapshot_id']
    limits = ModelCallLimits(max_attempts=1)
    console._model_call_limits_reader = lambda: limits
    with console._reprocessing_transaction(sid):
        envelope = deepcopy(console._envelope(sid))
        attempt, _ = reserve(envelope, actor_id=author, command_id='failed-' + name,
            revision=console.objects_revision(sid), clock=now(), limits=limits)
        finish(envelope, attempt['attempt_id'], state='failed',
            error=ConsoleError('docling_pages_unresolved' if pages else 'processing_dependency_failed'))
        if pages:
            envelope['processing_attempts'][-1]['diagnostic'] = {'page_findings': [{'page': 2, 'reasons': ['docling_page_text_unverified']}]}
        console._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    return sid
