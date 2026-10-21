"""Protocol v2.31 Forge: Dit klopt exact heading bind.

resolve_found_under_parent MUST bind the exact visible heading title after
normalization. Substring / containment / first-hit-win MUST NOT bind.
Zero or ambiguous exact matches fail closed (empty parent / Andere kop).
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here. publish() stays
G2-BLOCKED. Phase 1–4, v2.28 chooser/TOC and v2.30 cockpit stay.
"""
from __future__ import annotations

from pathlib import Path

from src.review_cockpit_v1 import found_under_path, resolve_found_under_parent


ROOT = Path(__file__).resolve().parents[1]


def _heading(
    object_id: str,
    text: str,
    *,
    role: str = "body",
    extract_index: int = 0,
) -> dict:
    return {
        "object_id": object_id,
        "object_type": "heading",
        "proposed_object_type": "heading",
        "confirmed_object_type": None,
        "extract_index": extract_index,
        "heading_role": role,
        "content": {"clean_text": text, "raw_text": text},
        "text": text,
        "clean_text": text,
    }


def _passage(path_last: str, *, ancestors: list[str] | None = None) -> dict:
    path = [*(ancestors or []), path_last]
    return {
        "object_id": "passage-1",
        "object_type": "unclassified",
        "proposed_object_type": "recommendation",
        "content": {"clean_text": "De werkgroep adviseert valpreventie bij de intake."},
        "metadata": {
            "admission": {
                "section_path": path,
                "current_heading": path_last,
            }
        },
    }


def _resolve(path_last: str, headings: list[dict], *, ancestors: list[str] | None = None) -> str:
    passage = _passage(path_last, ancestors=ancestors)
    objects = [*headings, passage]
    return resolve_found_under_parent(passage, objects)


def test_found_under_path_uses_last_section_segment() -> None:
    passage = _passage("Preventie van vallen", ancestors=["Richtlijn Fractuurpreventie"])
    assert found_under_path(passage) == "Richtlijn Fractuurpreventie › Preventie van vallen"


def test_preventie_path_binds_longer_exact_not_prefix() -> None:
    """Path last 'Preventie van vallen' MUST bind the longer heading, never Preventie."""
    short_first = [
        _heading("h-preventie", "Preventie", extract_index=0),
        _heading("h-preventie-vallen", "Preventie van vallen", extract_index=1),
    ]
    long_first = [
        _heading("h-preventie-vallen", "Preventie van vallen", extract_index=0),
        _heading("h-preventie", "Preventie", extract_index=1),
    ]
    assert _resolve("Preventie van vallen", short_first) == "h-preventie-vallen"
    assert _resolve("Preventie van vallen", long_first) == "h-preventie-vallen"


def test_preventie_path_binds_short_exact_not_longer_containment() -> None:
    """Path last 'Preventie' MUST bind Preventie, never Preventie van vallen."""
    short_first = [
        _heading("h-preventie", "Preventie", extract_index=0),
        _heading("h-preventie-vallen", "Preventie van vallen", extract_index=1),
    ]
    long_first = [
        _heading("h-preventie-vallen", "Preventie van vallen", extract_index=0),
        _heading("h-preventie", "Preventie", extract_index=1),
    ]
    assert _resolve("Preventie", short_first) == "h-preventie"
    assert _resolve("Preventie", long_first) == "h-preventie"


def test_screening_stems_substring_must_not_decide() -> None:
    short_first = [
        _heading("h-screening", "Screening", extract_index=0),
        _heading("h-screening-diag", "Screening en diagnostiek", extract_index=1),
    ]
    long_first = [
        _heading("h-screening-diag", "Screening en diagnostiek", extract_index=0),
        _heading("h-screening", "Screening", extract_index=1),
    ]
    assert _resolve("Screening en diagnostiek", short_first) == "h-screening-diag"
    assert _resolve("Screening en diagnostiek", long_first) == "h-screening-diag"
    assert _resolve("Screening", short_first) == "h-screening"
    assert _resolve("Screening", long_first) == "h-screening"


def test_dit_klopt_unique_exact_title_still_binds() -> None:
    headings = [
        _heading("h-aanbevelingen", "2 Aanbevelingen", extract_index=0),
        _heading("h-preventie", "Preventie", extract_index=1),
        _heading("h-preventie-vallen", "Preventie van vallen", extract_index=2),
    ]
    assert _resolve("2 Aanbevelingen", headings, ancestors=["Richtlijn Fractuurpreventie"]) == "h-aanbevelingen"
    assert _resolve("Preventie van vallen", headings, ancestors=["5 Aanbevelingen"]) == "h-preventie-vallen"


def test_zero_exact_matches_fail_closed_empty_parent() -> None:
    headings = [
        _heading("h-preventie", "Preventie", extract_index=0),
        _heading("h-screening", "Screening", extract_index=1),
    ]
    assert _resolve("Onbekende kop", headings) == ""
    assert _resolve("Preventie van vallen", headings) == ""
    assert _resolve("Screening en diagnostiek", headings) == ""
    only_long = [_heading("h-preventie-vallen", "Preventie van vallen", extract_index=0)]
    assert _resolve("Preventie", only_long) == ""
    only_short = [_heading("h-preventie", "Preventie", extract_index=0)]
    assert _resolve("Preventie van vallen", only_short) == ""


def test_first_hit_substring_and_startswith_are_forbidden() -> None:
    headings = [
        _heading("h-prevent", "Preventie", extract_index=0),
        _heading("h-long", "Preventie van vallen", extract_index=1),
    ]
    assert _resolve("Prevent", headings) == ""
    assert _resolve("van vallen", headings) == ""
    source = (ROOT / "src/review_cockpit_v1.py").read_text(encoding="utf-8")
    start = source.index("def resolve_found_under_parent")
    end = source.index("\ndef ", start + 1)
    fn = source[start:end]
    assert "last in text" not in fn
    assert "text in last" not in fn
    assert "startswith(" not in fn


def test_ambiguous_exact_titles_fail_closed_unless_unique_outline() -> None:
    headings = [
        _heading("h-preventie", "Preventie", extract_index=0),
        _heading("h-52-preventie", "5.2 Preventie", extract_index=1),
    ]
    assert _resolve("Preventie", headings) == ""
    assert _resolve("5.2 Preventie", headings) == "h-52-preventie"
    no_outline_match = [
        _heading("h-31-preventie", "3.1 Preventie", extract_index=0),
        _heading("h-preventie", "Preventie", extract_index=1),
    ]
    assert _resolve("5.2 Preventie", no_outline_match) == ""


def test_normalize_whitespace_and_symmetric_outline_strip() -> None:
    headings = [_heading("h-preventie-vallen", "Preventie van vallen", extract_index=0)]
    assert _resolve("Preventie  van   vallen", headings) == "h-preventie-vallen"
    assert _resolve("5.2 Preventie van vallen", headings) == "h-preventie-vallen"
    outlined = [_heading("h-52", "5.2 Preventie van vallen", extract_index=0)]
    assert _resolve("Preventie van vallen", outlined) == "h-52"
    assert _resolve("5.2 Preventie van vallen", outlined) == "h-52"


def test_toc_crumb_must_not_bind_as_dit_klopt_parent() -> None:
    headings = [
        _heading("h-toc-preventie-vallen", "Preventie van vallen", role="toc", extract_index=0),
        _heading("h-body-screening", "Screening", role="body", extract_index=1),
    ]
    assert _resolve("Preventie van vallen", headings) == ""


def test_dit_klopt_caller_still_uses_resolve_found_under_parent() -> None:
    source = (ROOT / "src/operations_console_v1.py").read_text(encoding="utf-8")
    assert "resolve_found_under_parent" in source
    assert 'documentpositie_action == "dit_klopt"' in source
