# #1064 — Kennisobject opnieuw bouwen vanuit de kaart

Change class: B
Promise: Een reviewer past een kennisobject uit annotatie aan in dezelfde kaart, bouwt het met één knop opnieuw en vindt de nieuwe versie terug in Review, met de vorige versie in de versieregel.
Proof: Native browser/PostgreSQL-proef van reviewkaart naar kaart, opnieuw bouwen en terug naar de reviewkaart van de nieuwe versie, plus kerntests voor de bouwstatus en de nieuwe route.
Touches lifecycle invariants: no
Rewrite risk: none

Part of MET-76. GO projectlead 13 november 2026: “Start met de bouw van #1064.”
Deel 1 (dit contract) is Class B. Deel 2, afwijzen in de tweede review, wijzigt
de statusovergangen van review en wordt vóór de bouw apart geclassificeerd.

## Program-design gate (deel 1)

**Bestaand mechanisme en autoriteit.** Een correctie is een gewone opslag in
`human_annotation_v1.save`; bij een al opgebouwd document trekt die de
beoordeling van geraakte objecten in (`reset_review_state`, binding-intrekking)
en blokkeert de database goedkeuring van de oude versie
(`guard_annotation_pending_approval`, `annotation_correction_pending`). Een
nieuwe versie ontstaat alleen via `human_annotation_build_v1.finalize` en de
bestaande opbouw (`formation_evidence_v1` → `build_objects` →
`apply_annotation_revisions`), die alleen gewijzigde objecten een nieuwe versie
met `revision_lineage` geeft.

**Gedragswijziging.**

1. Nieuwe route `POST /annotations/rebuild`: leest het documentoverzicht, eist
   dat de generatie gelijk is aan die van de kaart, en roept de bestaande
   `finalize` aan met het overzicht dat zij zelf leest. Daarna dezelfde
   dispatcher als de bestaande afsluitroute. Geen eigen opbouw, geen tweede
   kandidaatmaker.
2. De kaart toont bij een al opgebouwd object één knop: “Kennisobject opnieuw
   bouwen” als er iets gewijzigd is, anders “Terug naar review”. Het uitlegblok
   over broncorrecties vervalt. Na het starten gaat de kaart naar de reviewkaart
   van dat object.
3. Reviewkaart, alleen voor objecten uit annotatie: één ingang, “Aanpassen in de
   kaart”. Vervallen: de zin “Wil je iets aanpassen?”, de tweede link in de
   acties, “Andere plek kiezen” (de plek volgt uit de bron) en
   “Oorspronkelijke annotatie en bronbereiken bekijken”. Andere objecten houden
   hun bestaande correctieroute.
4. De bestaande statusplek op de reviewkaart toont “Correctie opgeslagen, nog niet
   opnieuw gebouwd” of “Nieuwe versie wordt opgebouwd”. Goedkeuren is dan
   uitgeschakeld; dat weigert de database nu ook al.
5. De bestaande versieregel toont bij een nieuwe versie “opnieuw gebouwd na
   correctie van versie …”.

**Wat ongewijzigd blijft.** Opslag, intrekken van beoordelingen, de
databasebewaking, de opbouw en zijn bewijs, review- en publicatieregels, de
tweede review en afwijzen.

**Muteerbare staat.** Alleen wat de bestaande `finalize` al schrijft: seal,
bouwopdracht en procespoging. De nieuwe statusweergave leest alleen.

**Kleinste waarneembare bewijs.** Een correctie van een goedgekeurd object leidt
via de knop tot een nieuwe versie met `revision_lineage`, terwijl de reviewkaart
tussendoor de bouwstatus toont en niet goedkeurt.

## Uitvoering deel 1 (13 november 2026)

- `human_annotation_build_v1.correction_state` (alleen lezen) en `rebuild`;
  route `POST /annotations/rebuild` in `human_annotation_ui_v1`.
- Kaart: knop `#annotation-rebuild` bij een al opgebouwd object, in beide
  formulieren; het blok `#annotation-current-object` blijft in de kaart dicht;
  status- en koptekst spreken over het object in plaats van over de
  documentcontrole.
- Reviewkaart (`ko_review_page_v1`): één ingang “Aanpassen in de kaart”,
  bouwstatus in de bestaande statusplek, “opnieuw gebouwd na correctie van
  versie …” in de bestaande versieregel. Tijdens het bouwen ververst de pagina
  zichzelf.

Bekende beperking: haalt de reviewer tekst weg zonder haar elders te gebruiken,
dan is die brontekst niet meer verantwoord en weigert opnieuw bouwen met de
bestaande melding dat het document niet compleet is. Dat volgt uit de regel dat
de hele bron verantwoord moet zijn (besluit 2 in het ontwerp van #1060) en is
hier niet veranderd.

Niet gebouwd: een weergave van de vorige versie zelf. De versieregel noemt het
vorige versienummer; een vergelijking volgt bij deel 2, waar reviewer 2 moet
zien wat reviewer 1 veranderde.

Bewijs: `tests/test_rebuild_from_card_1064.py` (bouwstatus, één ingang,
opnieuw bouwen, nieuwe versie met herkomst, verouderde kaart, route) en
`tests/browser_human_review_check.cjs` (reviewkaart → kaart → één knop → nieuwe
versie in review → goedkeuren), beide op native PostgreSQL.
