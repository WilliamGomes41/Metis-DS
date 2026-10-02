"""Fixtures explicitly realize context via the real kernel command, never flags."""
from src.admission_gate_v1 import admission_of
from src.source_context_review_v1 import projection, role_of, links_of


def bind_detected_context(console, snapshot_id, reviewer_id):
    for index in range(100):
        rows = console.snapshot_objects(snapshot_id)
        pending = [(target, issue) for target in rows if not role_of(target)
                   for issue in (admission_of(target).get('context_realization') or {}).get('unresolved', [])]
        found = False
        for target, issue in pending:
            source = next((r for r in rows if r['object_id'] != target['object_id'] and
                           str((r.get('content') or {}).get('clean_text') or '') == issue['text']), None)
            if source is None or links_of(source):
                continue
            previous = projection(source, rows)['target_object_ids']
            console.confirm_source_context(actor_id=reviewer_id, snapshot_id=snapshot_id,
                source_object_id=source['object_id'], role='context',
                target_object_ids=list(set(previous + [target['object_id']])),
                reason='Fixture: controleer de letterlijke toepassingscontext bij deze passage.',
                command_id=f'fixture-context-{index}', expected_revision=console.objects_revision(snapshot_id))
            found = True
            break
        if not found:
            return
    raise AssertionError('context fixture did not converge')
