"""Presentation-only regression: links, grouping and gates remain distinct.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from src.operations_console_app import _review_section_groups


def test_sections_keep_same_named_headings_in_separate_source_paths():
    objects = [
        {"object_id": str(i), "structure": {"section_path": path},
         "content": {"clean_text": "Een volledige passage."}}
        for i, path in enumerate([["A", "Inleiding"], ["B", "Inleiding"], ["A", "Inleiding"]])
    ]
    html = _review_section_groups(objects, "snapshot")
    assert html.count('class="review-section"') == 2
    assert "2 passages" in html
    for i in range(3):
        assert html.count(f'object={i}&amp;task=individual"') == 1
    assert "geen inhoudelijke goedkeuring" in html
    assert "<form" not in html


def test_section_title_is_escaped_and_missing_path_remains_visible():
    html = _review_section_groups([
        {"object_id": "x", "structure": {"section_path": ["<script>"]}},
        {"object_id": "y"},
    ], "snapshot")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Brononderdeel nog te controleren" in html


def test_repeated_heading_and_literal_separator_do_not_merge_paths():
    objects = [
        {"object_id": str(i), "structure": {"section_path": path}}
        for i, path in enumerate([
            ["Policy", "Scope", "Policy"], ["Policy", "Scope"],
            ["Policy › Scope"],
        ])
    ]
    html = _review_section_groups(objects, "snapshot", priority_ids={"0"})
    assert html.count('class="review-section"') == 3
    assert "omdat zij advies, een voorwaarde, een uitzondering of mogelijk risico bevat" in html
    assert "kan niet veilig samen met andere passages" in html
