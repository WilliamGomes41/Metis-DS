"""#1060 slice 4: deterministic proposals for text that belongs to a statement.

A proposal is an exact source position, never model or rewritten text. It only
asks the worker: adding it or declining it is the worker's saved decision. No
model call, no state and no candidate text live here.
"""
import re

VERSION = 'annotation-context-proposal-v1'
# A list rarely spans more items than this; further back the colon belongs elsewhere.
MAX_BETWEEN = 10
_SENTENCE_END = re.compile(r'[.!?;]\s+')


def _introduction(text):
    """Exact span of the last sentence when the block ends on a colon."""
    body = text.rstrip()
    if not body.endswith(':'):
        return None
    start = 0
    for match in _SENTENCE_END.finditer(body, 0, len(body) - 1):
        start = match.end()
    return start, len(body)


def proposals(blocks, ranges, declined=()):
    """Open proposals for one annotation.

    ``blocks`` are the ordered source blocks; ``ranges`` and ``declined`` are the
    stored anchors of the annotation. Text that is linked, overlaps a linked
    range, or was declined is never proposed again.
    """
    order = {block['block_id']: index for index, block in enumerate(blocks)}
    core = [anchor for anchor in ranges if anchor['role'] == 'core' and anchor['block_id'] in order]
    if not core:
        return []
    first = min(order[anchor['block_id']] for anchor in core)
    section = blocks[first].get('section_path') or []
    refused = {(row['block_id'], row['start'], row['end']) for row in declined}
    for index in range(first - 1, max(-1, first - 2 - MAX_BETWEEN), -1):
        block = blocks[index]
        if (block.get('section_path') or []) != section:
            return []
        span = _introduction(block['text'])
        if span is None:
            continue
        start, end = span
        if (block['block_id'], start, end) in refused or any(
                anchor['block_id'] == block['block_id'] and anchor['start'] < end and start < anchor['end']
                for anchor in ranges):
            return []
        return [{'block_id': block['block_id'], 'start': start, 'end': end,
                 'quote': block['text'][start:end], 'role': 'list_introduction'}]
    return []
