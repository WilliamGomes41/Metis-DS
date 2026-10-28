"""Pinned execution order, independent of semantic result identity.

Only source references are retained. A possible recommendation is a scheduling
signal; the existing provider, validators and candidate creator decide content.
"""
from copy import deepcopy

from src.vorming.recommendation_coverage_v1 import inventory
from src.vorming.semantic_replay_v1 import stable_json_hash
from src.operations_console_v1 import ConsoleError

VERSION = 'recommendations-first-plan-v1'


def source_identity(blocks, evidence_blocks):
    return stable_json_hash({'source_blocks': blocks, 'evidence_blocks': evidence_blocks})


def build_plan(tasks, blocks, evidence_blocks):
    possibilities = inventory(blocks, recommendation_sections_only=False)
    entries = [{'span': row['span'], 'scope_span': {k: row['scope_cue'][k] for k in ('block_id','start','end')}
                if row.get('scope_cue') else None} for row in possibilities]
    planned = []
    for order, task in enumerate(tasks):
        possible = [i for i, row in enumerate(entries) if any(overlaps(row['span'], ref) for ref in task['target_spans'])]
        planned.append({**{k: deepcopy(task[k]) for k in ('task_id','section_path','target_spans')},
            'source_block_ids': [b['block_id'] for b in task['source_blocks']],
            'evidence_block_ids': [b['block_id'] for b in task['evidence_blocks']],
            'source_order': order + 1, 'priority': 'possible_recommendation' if possible else 'remaining_source',
            'possible_recommendation_indices': possible,
            **({'error_code':task['error_code']} if task.get('error_code') else {})})
    planned.sort(key=lambda task: (task['priority'] != 'possible_recommendation', task['source_order']))
    return {'version': VERSION, 'source_blocks_hash':source_identity(blocks,evidence_blocks),
            'detection_completeness':'not_proven', 'possible_recommendations': entries, 'tasks':planned}


def overlaps(left, right):
    return left['block_id'] == right['block_id'] and max(left['start'],right['start']) < min(left['end'],right['end'])


def remaining_tasks(plan, blocks, evidence_blocks, targets):
    """Keep pinned task boundaries/context; subtract only proven source use.

    Partial recovery can change exact ranges but never crosses an original task
    boundary or drops a range merely because no recommendation was recognised.
    """
    if plan.get('version') != VERSION:
        raise ConsoleError('formation_task_plan_version_unsupported')
    if plan.get('source_blocks_hash') != source_identity(blocks,evidence_blocks):
        raise ConsoleError('formation_task_plan_source_mismatch')
    by_id = {b['block_id']:b for b in [*evidence_blocks,*blocks]}
    # Legacy source-accountability targets can include evidence-only strength
    # labels. Preserve tasks_for's boundary: these remain context, never an
    # extra candidate task. Coverage checks below concern candidate source only.
    candidate_ids = {b['block_id'] for b in blocks}
    targets = [r for r in targets if r['span']['block_id'] in candidate_ids]
    tasks = []
    for recorded in plan['tasks']:
        refs = []
        for original in recorded['target_spans']:
            for target in targets:
                pending = target['span']
                if overlaps(original,pending):
                    refs.append({'block_id':original['block_id'], 'start':max(original['start'],pending['start']),
                                 'end':min(original['end'],pending['end'])})
        if not refs:
            continue
        selectable = {ref['block_id'] for ref in refs}
        context_ids = set(recorded['evidence_block_ids']) | (set(recorded['source_block_ids']) - selectable)
        try:
            task = {**deepcopy(recorded), 'target_spans': refs,
                    'source_blocks':[by_id[bid] for bid in recorded['source_block_ids'] if bid in selectable],
                    'evidence_blocks':[b for b in evidence_blocks if b['block_id'] in context_ids]}
        except KeyError as error:
            raise ConsoleError('formation_task_plan_source_mismatch') from error
        if refs != recorded['target_spans']:
            task['task_id'] = stable_json_hash({'version':'bounded-formation-v1','spans':refs})
        tasks.append(task)
    # Every requested range must belong to the pinned source partition. A
    # corrupted/incompatible plan cannot silently make pending work disappear.
    from src.vorming.source_containers_v1 import _covers
    planned_refs = [s for task in tasks for s in task['target_spans']]
    if any(not _covers(target['span'],planned_refs) for target in targets):
        raise ConsoleError('formation_task_plan_coverage_mismatch')
    return tasks


def report(plan, proposal, targets, *, selection_scope="current_result_set"):
    return {'version':VERSION, 'plan_hash':stable_json_hash(plan),
            'possible_recommendation_count':len(plan['possible_recommendations']), 'selection_scope':selection_scope,
            'selected_recommendation_count':sum(obj.get('proposed_object_type') == 'recommendation'
                                                for obj in proposal.get('objects',[])),
            'remaining_source_ranges':[r['span'] for r in targets], 'detection_completeness':'not_proven'}
