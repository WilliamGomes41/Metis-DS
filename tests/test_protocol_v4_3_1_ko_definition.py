"""Check the Protocol v4.3.1 KO-definition clarification (#1090); no runtime proof.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'PROTOCOL.md'
# SHA-256 of §7 on main 9245b3bf; the clarification MAG NIET change §7.
SECTION_7_SHA256 = '0bae9d9afea6bcbad5728e550b9bee0cf4800013c01b2f8c66fa819cbe9e228c'


def _section(text: str, heading: str) -> str:
    """Body from `heading` up to the next heading of the same or higher level."""
    level = len(heading) - len(heading.lstrip('#'))
    start = text.index(heading + '\n')
    rest = text[start + len(heading) + 1:]
    match = re.search(r'^#{1,%d} ' % level, rest, re.MULTILINE)
    return heading + '\n' + (rest[:match.start()] if match else rest)


def test_protocol_stays_v4_3_1():
    protocol = PROTOCOL.read_text(encoding='utf-8')
    assert protocol.startswith('# V&VN Data Services — Protocol v4.3.1\n')
    assert protocol.count('**Versie:** 4.3.1') == 1
    assert '4.3.2' not in protocol


def test_section_4_2_defines_ko_identity_meaning_and_boundary():
    section = _section(PROTOCOL.read_text(encoding='utf-8'), '### 4.2 Kennisobject')
    for required in (
        'Een kennisobject is een identificeerbare, versiegebonden representatie van één '
        'afgebakende betekeniseenheid die volledig uit de vastgelegde bron kan worden verantwoord.',
        'Een kennisobject is **zelfstandig begrijpelijk** wanneer de volledige brongebonden '
        'betekenis kan worden gereconstrueerd.',
        'De aanwezigheid van alleen een relatieverwijzing zonder controleerbaar contextbewijs volstaat niet.',
        '**Zelfstandige identiteit en beoordeling**',
        'de definitie zelf verleent geen publicatie- of intrekkingsrecht.',
    ):
        assert required in section, required


def test_section_7_is_unchanged_from_main():
    section = _section(PROTOCOL.read_text(encoding='utf-8'), '## 7. Publicatie en G2')
    assert hashlib.sha256(section.encode('utf-8')).hexdigest() == SECTION_7_SHA256
