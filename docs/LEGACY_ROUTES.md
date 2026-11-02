# Legacy verwerking — expliciete status per pad

De actuele verwerkingsregels staan in [PROTOCOL.md §5](../PROTOCOL.md#5-semantische-interpretatie-en-harde-invarianten); open uitvoering en acceptatie staan in [ROADMAP.md](../ROADMAP.md). Dit register beschrijft compatibiliteit en uitgevoerde verwijderingen, geen aanvullende productnorm.

Eigenaar voor L01–L08: Metis-maintainer; oorspronkelijk uitvoeringsissue #455. De historische machineleesbare inventaris staat in `config/legacy_processing_routes.json`; het oorspronkelijke vervangingsplan staat in [het implementatievoorstel](METIS_SOURCE_BOUND_IMPLEMENTATION_PLAN.md), §6–9.

LEGACY-REMOVED betekent dat de route in Protocol 4.3.0 (besluit William 2026-10-22) is verwijderd zonder rollbackvenster en zonder voorafgaand G4-bewijs; rollback is een softwareterugzetting. Zie `docs/change-contracts/semantic-only-formation.md`.

LEGACY-FROZEN beschrijft behouden compatibiliteit: geen verdere featureontwikkeling in het oude contract; compatibiliteit, huidige productie, vergelijking en noodzakelijk herstel blijven toegestaan. Het label betekent **niet** dat de code al uitgeschakeld is. `cutover_enabled=false` is beschrijvende release-evidence, geen tweede runtimeflag.

| ID | Pad | Huidige code-/compatibiliteitsstatus | Resterend |
|---|---|---|---|
| L01 | Zelfstandige deterministische vrije-tekstroute | **LEGACY-REMOVED** (4.3.0); koppen via `heading_structure_units` | G4 open voor semantische vorming |
| L02 | Semantisch v1-voorstel | V2 is de standaard voor nieuw proza; V1 en V3 zijn expliciet te kiezen contractversies | Inhoudelijke acceptatie; historische contracten leesbaar houden |
| L03 | Regex-invulling na semantisch voorstel | V2 gebruikt uitsluitend gebonden veldbewijs | V1-compatibiliteit blijft |
| L04 | V1-modeselectie | **LEGACY-REMOVED** (4.3.0): `deterministic-v1` is een configuratiefout | — |
| L05 | Broncatalogus via specvorming | Geen | Losmaken catalogus, geen modelcall behouden |
| L06 | Afzonderlijke vergelijking-adapters | **LEGACY-REMOVED** (4.3.0): deterministische arm en nieuwe vergelijkingen geweigerd | Vastgelegde vergelijkingen blijven [leesbaar](history/ROUTE_COMPARISON.md) |
| L07 | Replay voor v1-contract | V2-identity toegevoegd, zelfde mechanisme | Historische readers behouden |
| L08 | Directe vrije-tekstconversie bij klassewijziging | **LEGACY-REMOVED** (4.3.0): via de geïnstalleerde verwerkingsstrategie | — |

Geen van deze labels geldt voor hele modules. Extractie, reconstructie, kopstructuur, beslisboom, bronvalidatie, menselijke repair, review, publicatie, retrieval en kwaliteitsmetingen blijven actief. Voor verwijdering zijn G0–G5, expliciete rollbackafsluiting en nul noodzakelijke aanroepers nodig. Runtimeblokkade en importgrenzen horen bij die cutoverslice; dit register claimt ze niet.
