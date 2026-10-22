# Legacy verwerking — expliciete status per pad

Eigenaar voor L01–L08: Metis-maintainer; uitvoeringsissue #455. Machineleesbare inventaris: `config/legacy_processing_routes.json`. Volledige vervangingsvoorwaarden: `METIS_SOURCE_BOUND_IMPLEMENTATION_PLAN.md`, §6–9.

LEGACY-REMOVED betekent dat de route in Protocol 4.3.0 (besluit William 2026-10-22) is verwijderd zonder rollbackvenster en zonder voorafgaand G4-bewijs; rollback is een softwareterugzetting. Zie `docs/change-contracts/semantic-only-formation.md`.

LEGACY-FROZEN betekent in deze eerste release: geen verdere featureontwikkeling in het oude contract; compatibiliteit, huidige productie, vergelijking en noodzakelijk herstel blijven toegestaan. Het label betekent **niet** dat de code al uitgeschakeld is. `cutover_enabled=false` is beschrijvende release-evidence, geen tweede runtimeflag.

| ID | Pad | Vervanging in deze PR | Resterend |
|---|---|---|---|
| L01 | Zelfstandige deterministische vrije-tekstroute | **LEGACY-REMOVED** (4.3.0); koppen via `heading_structure_units` | G4 open voor semantische vorming |
| L02 | Semantisch v1-voorstel | Opt-in v2 toegevoegd | Praktijkvergelijking/cutover |
| L03 | Regex-invulling na semantisch voorstel | V2 gebruikt uitsluitend gebonden veldbewijs | V1-compatibiliteit blijft |
| L04 | V1-modeselectie | **LEGACY-REMOVED** (4.3.0): `deterministic-v1` is een configuratiefout | — |
| L05 | Broncatalogus via specvorming | Geen | Losmaken catalogus, geen modelcall behouden |
| L06 | Afzonderlijke vergelijking-adapters | **LEGACY-REMOVED** (4.3.0): deterministische arm en nieuwe vergelijkingen geweigerd | Vastgelegde vergelijkingen blijven leesbaar |
| L07 | Replay voor v1-contract | V2-identity toegevoegd, zelfde mechanisme | Historische readers behouden |
| L08 | Directe vrije-tekstconversie bij klassewijziging | **LEGACY-REMOVED** (4.3.0): via de geïnstalleerde verwerkingsstrategie | — |

Geen van deze labels geldt voor hele modules. Extractie, reconstructie, kopstructuur, beslisboom, bronvalidatie, menselijke repair, review, publicatie, retrieval en kwaliteitsmetingen blijven actief. Voor verwijdering zijn G0–G5, expliciete rollbackafsluiting en nul noodzakelijke aanroepers nodig. Runtimeblokkade en importgrenzen horen bij die cutoverslice; deze PR claimt ze niet.
