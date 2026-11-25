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


def test_derived_field_in_another_role_is_kept(monkeypatch):
    from src.review import ko_receipt_ui_v1 as receipt
    text = 'Volwassenen met diabetes'
    monkeypatch.setattr(receipt, '_scope_connections',
                        lambda obj, *, annotated: [receipt.KnowledgeConnection('Situatie', text)])
    entries = [{'role': 'target_group', 'text': text, 'annotation_role': 'population'}]
    essential = [{'role': 'target_group', 'text': text, 'status': 'bound'}]

    rows, _scopes, _other = _review_application(_obj(entries), essential)

    assert [(row.label, row.text) for row in rows] == [('Doelgroep', text), ('Situatie', text)]


def test_scope_survives_when_actor_shares_the_passage():
    text = 'In de thuiszorg'
    for order in (('scope', 'actor'), ('actor', 'scope')):
        entries = [{'role': 'scope', 'text': text, 'annotation_role': role} for role in order]
        essential = [{'role': 'scope', 'text': text, 'status': 'bound'} for _ in order]

        rows, _scopes, other = _review_application(_obj(entries), essential)

        assert [(row.label, row.text) for row in rows] == [('Situatie', text)], order
        assert [item['role'] for item in other] == ['scope'], order
