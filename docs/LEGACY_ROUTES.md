# Legacy verwerking — expliciete status per pad

Eigenaar voor L01–L08: Metis-maintainer; uitvoeringsissue #455. Machineleesbare inventaris: `config/legacy_processing_routes.json`. Volledige vervangingsvoorwaarden: `METIS_SOURCE_BOUND_IMPLEMENTATION_PLAN.md`, §6–9.

LEGACY-FROZEN betekent in deze eerste release: geen verdere featureontwikkeling in het oude contract; compatibiliteit, huidige productie, vergelijking en noodzakelijk herstel blijven toegestaan. Het label betekent **niet** dat de code al uitgeschakeld is. `cutover_enabled=false` is beschrijvende release-evidence, geen tweede runtimeflag.

| ID | Pad | Vervanging in deze PR | Resterend |
|---|---|---|---|
| L01 | Zelfstandige deterministische vrije-tekstroute | Geen cutover | Structurele producent en G4 |
| L02 | Semantisch v1-voorstel | Opt-in v2 toegevoegd | Praktijkvergelijking/cutover |
| L03 | Regex-invulling na semantisch voorstel | V2 gebruikt uitsluitend gebonden veldbewijs | V1-compatibiliteit blijft |
| L04 | V1-modeselectie | V2-opt-in beschikbaar | Eén definitieve productiepolicy na G4 |
| L05 | Broncatalogus via specvorming | Geen | Losmaken catalogus, geen modelcall behouden |
| L06 | Afzonderlijke vergelijking-adapters | Geen | Gedeelde versiegebonden producenten |
| L07 | Replay voor v1-contract | V2-identity toegevoegd, zelfde mechanisme | Historische readers behouden |
| L08 | Directe vrije-tekstconversie bij klassewijziging | Geen | Gedeelde dispatcher, lifecyclebewijs |

Geen van deze labels geldt voor hele modules. Extractie, reconstructie, kopvorming, beslisboom, bronvalidatie, menselijke repair, review, publicatie, retrieval en kwaliteitsmetingen blijven actief. Voor verwijdering zijn G0–G5, expliciete rollbackafsluiting en nul noodzakelijke aanroepers nodig. Runtimeblokkade en importgrenzen horen bij die cutoverslice; deze PR claimt ze niet.
