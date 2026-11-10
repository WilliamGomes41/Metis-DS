"""Reveal motion stays one-shot, short, limited to five places and fades under reduced motion."""
from __future__ import annotations

from pathlib import Path
import re

import pytest

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]

ROOT = Path(__file__).resolve().parents[1]
PLACES = (
    "#documents .document-row[open] > :not(summary)",
    '.care-companion[data-reveal="1"] .care-panel:not([hidden])',
    "[data-session-warning]:not([hidden])",
    "#review-colleagues:not([hidden])",
    "#review-four-eyes:not([hidden])",
    "#replaces-row:not([hidden])",
    ".publication-room .banner.ok",
)


def _block() -> str:
    css = (ROOT / "assets/brand/console.css").read_text()
    assert css.count("/* Reveal motion for occasional and rare state changes") == 1
    return css.split("/* Reveal motion for occasional and rare state changes", 1)[1]


def test_reveal_covers_exactly_the_accepted_places() -> None:
    block = _block()
    base = re.search(r"\n\n(#documents[^{]*)\{\s*animation: metis-fade 150ms", block).group(1)
    assert tuple(part.strip() for part in base.split(",")) == PLACES
    rules = block.split("*/", 1)[1]  # the comment names what stays still; the rules must not select it
    for high_frequency in (".review-", "annotation", ".rooms", ".topbar", ".home-tile", "theme"):
        assert high_frequency not in rules


def test_reveal_is_short_one_shot_and_transform_or_opacity_only() -> None:
    block = _block().split("*/", 1)[1]
    durations = [int(value) for value in re.findall(r"(\d+)ms", block)]
    assert durations and max(durations) <= 240
    assert "infinite" not in block and "animation-iteration-count" not in block
    for frame in re.findall(r"@keyframes [\w-]+ \{ from \{(.*?)\} \}", block):
        properties = {declaration.split(":")[0].strip() for declaration in frame.split(";") if declaration.strip()}
        assert properties <= {"opacity", "transform"}, frame
    assert not re.search(r"\b(height|width|margin|top|left)\s*:", block)


def test_movement_is_absent_under_reduced_motion() -> None:
    block = _block()
    motion = block.split("@media (prefers-reduced-motion: no-preference) {", 1)
    outside, inside = motion[0], motion[1]
    # Outside the media query every place only fades; movement names live inside it.
    rules = outside.split("@keyframes metis-reveal-panel", 1)[1]
    assert "metis-reveal" not in rules.split("}", 1)[1]
    assert inside.count("animation-name: metis-reveal-") == 4


def test_restored_companion_panel_does_not_replay_the_reveal() -> None:
    script = (ROOT / "assets/brand/care-companion.js").read_text()
    assert "root.dataset.reveal = open && focus ? '1' : '';" in script
    assert "setOpen(true, false)" in script
