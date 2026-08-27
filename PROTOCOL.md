# V&VN Data Services — Protocol

## Geldende norm

De geldende normatieve baseline is Protocol v2.5.0 en bestaat uit:

1. [Protocol v2.2.0](docs/PROTOCOL_V2_2.md) — lifecycle, provenance en acceptance;
2. [Protocol v2.3.0](docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md) — setup, stack en kostentransparantie;
3. [Protocol v2.4.0](docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md) — product, distributie en extern gebruik;
4. [Protocol v2.5.0](docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md) — MVP-uitzondering voor een publieke gezaghebbende remote.

- Status: goedgekeurd voor projectgebruik
- Goedgekeurd: 2026-08-27
- Eigenaar: projecteigenaar V&VN Data Services
- Regel bij conflict: de strengste fail-closed eis geldt. Protocol v2.5 is een begrensde supersessie van v2.2 §4.1 (private remote MUST) uitsluitend voor de gedeclareerde MVP-periode op `WilliamGomes41/VENVN-DS`; overige eisen blijven fail-closed.

Dit bestand is de stabiele ingang naar het geldende protocol. Normatieve eisen worden uitsluitend in de versiegebonden protocolspecificatie gewijzigd. Een nieuwe productregel, architectuurgrens, safety-invariant, verantwoordelijkheid of verboden route vereist eerst een geversioneerde protocolwijziging.

## Productgrens

V&VN Data Services beheert de gevalideerde kennislaag, Product API en interne inspection. Het MVP ondersteunt bronverwijzing en kennisrespons met provenance en abstention. Een referentietoepassing, chatbot, productfrontend, EPD/ECD-integratie, beslisregel, patiëntspecifiek advies of getraind model is geen impliciet onderdeel van deze repository en vereist een afzonderlijke scope en goedkeuring volgens Protocol v2.4.

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
