Change class: B
Promise: Een gebruiker herkent in Vormingsproblemen het bronstuk, de reden en de volgende beschikbare handeling.
Proof: Impeccable voor/na-beoordeling en echte PostgreSQL/Playwright op desktop, mobiel, donker thema en toetsenbord; alle oorspronkelijke bevindingen en bestaande herstel-/publicatiegrenzen blijven aantoonbaar behouden.
Touches lifecycle invariants: no
Rewrite risk: none

# #851 — Vormingsproblemen begrijpelijk maken

Gebruikersopdracht: `npx impeccable install`; gebruik Impeccable om de pagina te
verbeteren en cognitieve belasting te verlagen. Geen merge of deployment.

## Bestaand mechanisme en grens

GET `/formation-problems` → bestaande actor-/documentautorisatie →
`formation_problems_v1.collect` → bestaande workflowbevindingen,
bronverantwoording en Admission → HTML in `source_selection_ui_v1`.
POST `/source-selection/start`, Review en bron-/kandidaatreparatie houden
hun bestaande bevoegdheden, revisiecontrole en duurzame schrijfeigenaar.

Alleen afgeleide presentatie verandert. Letterlijke fragmenten komen via de
bestaande `stored_extraction`-integriteitscontrole en `semantic_source_blocks`
uit dezelfde bronversie; ongeldige/onbekende bereiken krijgen geen citaat.
Er komt geen nieuwe taak, status, opslag, sluitingsregel of publicatiepoort.

## Ontwerpbesluit vóór UI-code

Operate-modus, bestaande Metis-huisstijl behouden. Bovenaan de actuele toestand
en mogelijke vervolgstap. Daaronder bronstukken in bronvolgorde: eerst leesbare
brontekst, dan begrijpelijke reden en beschikbare handeling. Technische codes
en offsets staan in een native disclosure.

Alleen exact gelijke, bekende bronbereiken worden visueel gegroepeerd;
onbekende en slechts overlappende bereiken blijven afzonderlijk. Aantal
bronstukken en aantal meldingen zijn verschillend benoemd. Iedere oorspronkelijke
bevinding behoudt haar anker, reden en handelingen. Paginering gebeurt over de
getoonde groepen en verbergt geen onderliggende bevindingen. Groepering is geen
sluiting of domeinbesluit.

Lopende verwerking, beperkte herstelrechten, nog niet verwerkte bron,
geen actuele problemen en nog geen gekozen document krijgen eigen uitleg.
Er komt geen automatische verwerking op GET. Bestaande exacte brongetrouwheid,
herstelguards en publicatievoorwaarden blijven staan.

## Impeccable en baseline

CLI 4.7.0 via npm. De standaard bundeldownload faalt op de proxy. Installatie
is daarna voltooid met dezelfde CLI en een lokale bundel uit de officiële
GitHub-bron `pbakaus/impeccable`, commit
`3671d50f0ac9a662ce0615e85a256110c9cd720b` (skill 4.7.1), plus de officiële
npm-engine. Projectinstallatie zonder hooks; tooling/binaries blijven lokaal
buiten de productcode. `impeccable context` is uitgevoerd. Geen PRODUCT.md of
DESIGN.md aanwezig; scoped verbetering volgt de bestaande implementatie.
Toegepast: audit, distill, clarify, Operate en craft-floor; polish volgt na bouw.

Verse baseline: bestaande echte browser-/Raad-proef slaagt (1 passed, 11,74 s).
De synthetische mobiele opname toont twee kaarten voor hetzelfde bronbereik,
geen leesbare brontekst, herhaalde herstel-/diagnoselinks en direct zichtbare
controlecodes/offsets. Geen actuele Smetten-bron of productieclaim.

Geprioriteerde bevindingen:

- P1: het getroffen bronstuk is niet leesbaar; de gebruiker kan de melding niet plaatsen. Clarify + distill.
- P2: twee meldingen over hetzelfde bereik ogen als twee afzonderlijke taken. Exacte presentatiegroepering en expliciete aantallen.
- P2: technische codes en herhaalde links verdringen de volgende handeling. Native disclosure en één duidelijke handeling per bronstuk.
- P2: generieke lege toestand en hersteltekst vereisen interne voorkennis. Toestandsspecifieke taal.

Behoud: echte bestaande handelingen, native links/formulieren, duidelijke
rol-/bronbeperkingen, responsieve huisstijl en expliciete publicatievoorwaarden.
Dit is een deskundigenbeoordeling, geen gemeten afname van menselijke taakduur.

## Verificatie en oplevering

Voor/na-beelden, begrensde detectorbevindingen, werkelijk uitgevoerde controles
en resterende beperkingen worden bij deze wijziging en in #851 bijgehouden.
Controleer onder meer escape van brontekst, ongeldige spans, onbekende scope,
alle bevindingen bij groepering/paginering, herstel na menselijke review,
achtergrondverwerking tijdens navigeren en de echte Raad-worker.
