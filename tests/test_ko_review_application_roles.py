"""One literal assigned to two application roles stays visible in both review views."""
from src.review.ko_receipt_ui_v1 import _review_application


def _obj(entries):
    return {'metadata': {'human_annotation': True,
                         'source_bound_context': {'entries': entries}}}


def test_same_literal_in_two_application_roles_keeps_both_rows():
    text = 'Volwassenen met diabetes'
    entries = [{'role': 'target_group', 'text': text, 'annotation_role': 'population'},
               {'role': 'scope', 'text': text, 'annotation_role': 'scope'}]
    essential = [{'role': 'target_group', 'text': text, 'status': 'bound'},
                 {'role': 'scope', 'text': text, 'status': 'bound'}]

    rows, _scopes, other = _review_application(_obj(entries), essential)

    assert [(row.label, row.text) for row in rows] == [('Doelgroep', text), ('Situatie', text)]
    assert other == []


def test_same_literal_projected_twice_in_one_role_is_shown_once():
    text = 'Bij koorts'
    entries = [{'role': 'condition', 'text': text, 'annotation_role': 'condition'}]
    essential = [{'role': 'condition', 'text': text, 'status': 'bound'},
                 {'role': 'condition', 'text': ' Bij  koorts ', 'status': 'unbound'}]

    rows, _scopes, _other = _review_application(_obj(entries), essential)

    assert [row.label for row in rows] == ['Voorwaarde']
