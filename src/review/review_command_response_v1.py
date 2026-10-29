"""Render only the failed passage and its draft; navigation belongs to GET."""
import html
from urllib.parse import urlencode

from fastapi.responses import HTMLResponse

from src.review.revision_workflow import current_revisions


def review_command_error(console, account, snapshot_id, object_id, revision, task, draft, error):
    from src.operations_console_app import (
        _nav, _page, _render_review_card, _review_conflict_html, _sanitize_review_draft,
    )
    from src.operations_console_v1 import SNAPSHOT_OBJECT_WRITE_CONFLICT
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    from src.review.review_passage_read_v1 import ReviewPassageInputs

    conflict = error.code == SNAPSHOT_OBJECT_WRITE_CONFLICT
    inputs = getattr(error, 'review_command_inputs', None)
    draft = _sanitize_review_draft(draft)
    location = '/review?' + urlencode({'document': snapshot_id, 'object': object_id, 'task': task})
    navigation = f'<p><a href="{html.escape(location, quote=True)}">Bekijk de actuele passage</a></p>'
    if inputs is not None and not conflict:
        objects = current_revisions(list(inputs.histories), snapshot_id=snapshot_id)
        obj = next(row for row in objects if row['object_id'] == object_id)
        view = ReviewPassageInputs(dict(inputs.envelope), objects, list(inputs.bindings),
            revision, inputs.fragments, getattr(error, 'review_source_available', False))
        content = _render_review_card(console, snapshot_id, obj, objects,
            review_path_for_klasse(inputs.envelope['class']), draft, '',
            snapshot_revision=revision, task=task, read_inputs=view)
        if inputs.envelope.get('_review_check_formation'):
            content = ('<p class="banner warn" data-formation-incomplete>'
                'De bronvorming vraagt nog controle. Bekijk de documentpagina voor de volledige status.</p>') + content
    else:
        # Stale input is retained without issuing a fresh mutation precondition.
        # The reviewer must open and inspect the current passage before saving.
        fields = ''.join(
            f'<input type="hidden" name="{html.escape(str(key or ""), quote=True)}" value="{html.escape(str(item or ""), quote=True)}">'
            for key, value in draft.items()
            if key not in {'comment', 'proposed_correction'}
            for item in (value if isinstance(value, list) else [value]))
        content = (_review_conflict_html(True)
            + '<section data-review-draft><h2>Je invoer is bewaard</h2>'
            + '<p>Controleer de actuele passage voordat je opnieuw een besluit neemt.</p>'
            + fields
            + f'<label>Toelichting<textarea name="comment">{html.escape(draft.get("comment", ""), quote=True)}</textarea></label>'
            + f'<label>Voorgestelde correctie<textarea name="proposed_correction" readonly>{html.escape(draft.get("proposed_correction", ""), quote=True)}</textarea></label>'
            + '</section>')
    return HTMLResponse(_page(_nav(account, 'review') + content + navigation, title='Review'),
        status_code=409 if conflict else 400, headers={'Cache-Control': 'no-store'})
