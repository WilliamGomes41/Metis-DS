# V&VN Data Services — Protocol

## Geldende norm

De geldende normatieve baseline is Protocol v2.3.0 en bestaat uit:

1. [Protocol v2.2.0](docs/PROTOCOL_V2_2.md) — lifecycle, provenance en acceptance;
2. [Protocol v2.3.0](docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md) — setup, stack en kostentransparantie.

- Status: goedgekeurd voor projectgebruik
- Goedgekeurd: 2026-08-25
- Eigenaar: projecteigenaar V&VN Data Services
- Regel bij conflict: de strengste fail-closed eis geldt

Dit bestand is de stabiele ingang naar het geldende protocol. Normatieve eisen worden uitsluitend in de versiegebonden protocolspecificatie gewijzigd. Een nieuwe productregel, architectuurgrens, safety-invariant, verantwoordelijkheid of verboden route vereist eerst een geversioneerde protocolwijziging.

## Ontwikkelhiërarchie

De verplichte volgorde is:

`PROTOCOL.md → ROADMAP.md → HANDOFF.md → acceptatietests → code`

De uitvoeringscyclus is:

`probleem of failure → protocoltoets → roadmapbesluit → handoff → tests → code → validatie → handoff`

De volledige werkwijze en uitzonderingsregels staan in [docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md).

## Wijzigingsregel

- Een bug die aantoonbaar strijdig is met een bestaande protocolregel wordt gerepareerd met tests; een nieuwe protocolversie is niet nodig.
- Een nieuwe of gewijzigde productregel, architectuurgrens, safety-invariant, verantwoordelijkheid of toegestane/verboden route vereist eerst een protocolwijziging.
- Als de norm tijdens implementatie onduidelijk blijkt, stopt de implementatie totdat het protocol of een formeel besluit de onduidelijkheid oplost.

