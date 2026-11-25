"""A shared heading is no automatic strength label for each recommendation below it."""
from src.vorming.semantic_passage_v1 import bind_annotation_strength_label

HEADING = 'Sterk – voor'
SECTION = [HEADING]


def _block(block_id, position, text, *, heading=False):
    public = {'block_id': block_id, 'text': text, 'position': position, 'section_path': SECTION,
              'source_fragment_ids': [], **({'heading': text} if heading else {})}
    return block_id, (public, {'object_type': 'heading'} if heading else {})


def _blocks():
    return dict([
        _block('h', 0, HEADING, heading=True),
        _block('r1', 1, 'Breng de risicofactoren voor smetten in kaart.'),
        _block('r2', 2, 'Controleer de huidplooien dagelijks.'),
    ])


def _selected(blocks, block_id):
    text = blocks[block_id][0]['text']
    return [{'block_id': block_id, 'start': 0, 'end': len(text), 'text': text, 'section_path': SECTION}]


def test_shared_heading_is_not_an_automatic_strength_label():
    blocks = _blocks()
    for block_id in ('r1', 'r2'):
        assert bind_annotation_strength_label(_selected(blocks, block_id), blocks, fragments=None) is None
