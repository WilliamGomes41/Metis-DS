"""Reference validation is plumbing evidence, not a real human/model acceptance."""
import csv
import pytest
from scripts.verify_eenzaamheid_semantic import SOURCE_HASH, FIELDS, reviewed_reference, compare_reference
from src.semantic_passage_v1 import SELECTION_ORIGIN_PROPOSAL


def test_reference_is_literal_complete_and_human_attributed(tmp_path):
    path = tmp_path / 'reference.csv'
    payload = {'source_blocks': [{'block_id': 'b', 'text': 'Advies uit de bron.'}]}
    row = {'source_sha256': SOURCE_HASH, 'block_id': 'b', 'start': 0, 'end': 19, 'text': 'Advies uit de bron.',
           'expected_type': 'recommendation', 'reviewed_by': 'Reviewer fixture', 'reviewed_at': '2026-10-01'}
    def save(value):
        with path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(value)
    save(row)
    assert reviewed_reference(path, payload)[0]['end'] == 19
    save({**row, 'reviewed_by': ''})
    with pytest.raises(ValueError, match='human_reference_incomplete_or_stale'):
        reviewed_reference(path, payload)
    save({**row, 'text': 'Eigen verzonnen tekst'})
    with pytest.raises(ValueError, match='human_reference_not_literal'):
        reviewed_reference(path, payload)
    save({**row, 'end': 6, 'text': 'Advies'})
    with pytest.raises(ValueError, match='human_reference_coverage_incomplete'):
        reviewed_reference(path, payload)


def test_unselected_coverage_does_not_pass_as_a_correct_model_selection():
    rows = [{'block_id': 'b', 'start': 0, 'end': 18, 'expected_type': 'recommendation'}]
    spec = {'objects': [{'object_id': 'candidate', 'proposed_object_type': 'recommendation',
        'semantic_passage': {'selection_origin': SELECTION_ORIGIN_PROPOSAL,
                             'spans': [{'block_id': 'b', 'start': 0, 'end': 18}]}}]}
    assert compare_reference(rows, spec)[0]['passed']
    spec['objects'][0]['semantic_passage']['selection_origin'] = 'coverage_remainder'
    assert not compare_reference(rows, spec)[0]['passed']
