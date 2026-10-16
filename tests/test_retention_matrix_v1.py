"""Lex/Metis 2026-10-16: the refusal store MOET be in the retention matrix with Lex's conditions.

# release-control-evidence: scope/belofte
# release-control-evidence: releasebewijs
"""
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / 'docs' / 'RETENTION_MATRIX.md'


def test_refusal_store_is_in_the_retention_matrix_with_lex_conditions():
    text = DOC.read_text(encoding='utf-8')
    row = next(line for line in text.splitlines() if 'workflow.publication_refusals' in line and line.startswith('|'))
    assert '400' in row and '200000' in row and 'publication_refusal_retention.py' in row
    for condition in ('account_id', 'least-privilege', 'retention'):
        assert condition in text
