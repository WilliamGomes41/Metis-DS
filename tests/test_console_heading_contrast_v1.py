"""Work-page headings meet WCAG AA large-text contrast; the landing heading keeps Water."""
from __future__ import annotations

import re
from pathlib import Path

import pytest


pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]

ROOT = Path(__file__).resolve().parents[1]


def _contrast(hex_a: str, hex_b: str) -> float:
    def luminance(value: str) -> float:
        channels = [int(value.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    high, low = sorted((luminance(hex_a), luminance(hex_b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.pure_function
def test_work_page_headings_use_readable_water_and_landing_keeps_brand_water() -> None:
    css = (ROOT / "assets/brand/console.css").read_text(encoding="utf-8")
    block = css.split("/* Readable headings")[1]
    ink = re.search(r":root\s*\{\s*--heading-ink:\s*(#[0-9a-fA-F]{6})", block).group(1)
    assert _contrast(ink, "#FFFFFF") >= 4.5
    assert re.search(r"h1, h2,\s*\.dictionary-example span\s*\{\s*color:\s*var\(--heading-ink\)", block)
    assert re.search(r"\.home-room h1,\s*\.login-card h1\s*\{\s*color:\s*var\(--water\)", block)
    assert "--water: #45AAC7;" in css


@pytest.mark.pure_function
def test_no_heading_rule_keeps_brand_water_outside_landing_and_login() -> None:
    # More specific heading rules (Review, Over Metis) keep their own ink or
    # purple; none of them may fall back to the low-contrast brand Water.
    css = (ROOT / "assets/brand/console.css").read_text(encoding="utf-8")
    kept = {".home-room h1, .login-card h1"}
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        selector = " ".join(selector.split())
        if not re.search(r"\bh[12]\b", selector) or selector in kept:
            continue
        if re.search(r"(?<![-\w])color\s*:\s*var\(--water\)", body):
            # Only the base rule, which the Readable headings block overrides.
            assert selector == "h1, h2", selector
