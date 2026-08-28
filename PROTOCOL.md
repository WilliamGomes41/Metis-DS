# V&VN Data Services — Protocol

## Geldende norm

De geldende normatieve baseline is Protocol v2.8.0 en bestaat uit:

1. [Protocol v2.2.0](docs/PROTOCOL_V2_2.md) — lifecycle, provenance en acceptance;
2. [Protocol v2.3.0](docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md) — setup, stack en kostentransparantie;
3. [Protocol v2.4.0](docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md) — product, distributie en extern gebruik;
4. [Protocol v2.5.0](docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md) — MVP-uitzondering voor een publieke gezaghebbende remote;
5. [Protocol v2.6.0](docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md) — interne operations console als menselijk oppervlak over de knowledge kernel;
6. [Protocol v2.7.0](docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md) — first-wave bron, object-level retrieve-and-abstain API en distributie;
7. [Protocol v2.8.0](docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md) — primaire gebruikers, bronhiërarchie (klasse × familie) en console-bouwvolgorde.

- Status: goedgekeurd voor projectgebruik
- Goedgekeurd: 2026-08-28
- Eigenaar: projecteigenaar V&VN Data Services
- Regel bij conflict: de strengste fail-closed eis geldt. Protocol v2.5 is een begrensde supersessie van v2.2 §4.1 (private remote MUST) uitsluitend voor de gedeclareerde MVP-periode op `WilliamGomes41/VENVN-DS`. Protocol v2.6 is een begrensde supersessie van de v2.4-lezing «geen productfrontend in deze repository»: een interne operations console MAG in deze repository; een zorgapp-frontend, chatbot, EPD/ECD-UI en publieke website blijven verboden. Protocol v2.7 is een begrensde supersessie van v2.4 §10 (geen modeltraining in het MVP): training MAG alleen als tweede licentie, en alleen als de client DS op vraagmoment nog aanroept om de gepubliceerde status te controleren. Protocol v2.8 is een begrensde supersessie van v2.6 §7 en v2.7 §2 uitsluitend voor de bouwvolgorde console-versus-Fase-2 en de eerstvolgende concrete taak: de volgende implementatie is een echte console-MVP op de bestaande kernel; duurzame immutable opslag wordt niet overgeslagen. Alle v2.6-consoleregels blijven van kracht. Alle v2.7-bron-/API-/distributieregels blijven van kracht, behalve die begrensde bouwvolgorde. Overige eisen blijven fail-closed.

Dit bestand is de stabiele ingang naar het geldende protocol. Normatieve eisen worden uitsluitend in de versiegebonden protocolspecificatie gewijzigd. Een nieuwe productregel, architectuurgrens, safety-invariant, verantwoordelijkheid of verboden route vereist eerst een geversioneerde protocolwijziging.

## Productgrens

V&VN Data Services beheert de gevalideerde kennislaag, Product API, interne inspection en — onder Protocol v2.6 — een interne operations console als menselijk oppervlak over de knowledge kernel. De console is goedgekeurde scope, niet bestaande code. Primaire DS-gebruikers zijn richtlijnonderzoekers (console) en B2B-abonnees (EPD, instelling, hun bot). Verpleegkundigen zijn geen primaire DS-gebruikers; ontwerp de console niet voor verpleegkundigen. Het MVP ondersteunt bronverwijzing en kennisrespons met provenance en abstention. De Product API is object-level retrieve-and-abstain; DS genereert geen proza; er is geen LLM in het MVP. RAG op kennisplatform-HTML is niet het product; DS is de eigen live gecureerde schakel, geen scrape. Een zorgapp-frontend, chatbot, EPD/ECD-UI, publieke website, beslisregel, patiëntspecifiek advies of getraind model is geen impliciet onderdeel van deze repository. Chat hoort niet in de console; eventuele chat is een latere consument van de Product API (G7/C6, U1/U2).

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
