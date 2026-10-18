# Protocol v4.1 — volledigheidscontrole

Datum: 18 oktober 2026. Opdracht: #757. Beoordeelde baseline: `7bd99d170e21ca2006ee4b4262ff01b4d8d52b6d`.

## Oordeel en reikwijdte

V4.1.0 is een volledige opvolger van de geconsolideerde v4.0-norm en kan als enige vigerende protocolnorm worden aangewezen. Dit oordeel betreft documentconsolidatie: het is geen bewijs dat de software alle normen al implementeert of dat productie is geaccepteerd.

De vergelijking van `docs/history/protocol-v4.0/PROTOCOL.md` met de actuele rootnorm toont dat geen inhoudelijke sectie uit de v4.0-baseline is verwijderd. De inhoudelijke uitbreiding is §5.4; §5.2 verwijst voortaan naar dat kader. Het archiefregister in §16 vermeldt de v4.0-snapshot. Titel, status en de verouderde verwijzing naar een V3-governancevorm zijn redactioneel verduidelijkt.

| Onderdeel | Actuele dekking |
|---|---|
| Normhiërarchie en productgrens | §§1–2 |
| Bevroren bron, locator en versie | §3 |
| Passage-disposition en kennisobjectcontract | §4 |
| Semantisch voorstel, deterministische constructie en herstel | §§5.1–5.3; exclusieve kandidaatmaker expliciet in §5.4 |
| Vormingsroute, retry, opvolger en bronsoortstrategieën | §5.4, met richtlijn en beslisboom |
| Exacte reviewbinding, deelname en correctie | §6 |
| Publicatievoorwaarden, atomaire commit en mislukt herstel | §7 |
| Verwijdering, audit en experimentgrens | §§8–10 |
| Console, identiteit en Product API | §11 |
| Serving authority, retrieval en compiled knowledge | §12 |
| Topologie, deployment en bewijsdiscipline | §§13–14 |
| Directe protocolwijziging en historische versies | §§15–16 |

## Grenzen en open werk

- `ROADMAP.md` R4.6 zegt expliciet dat routekeuze nog deploymentbreed gebeurt en nog niet als documenttoestand is vastgelegd. Het nieuwe kader is normatief, de implementatie blijft open.
- Een semantische beslisboomroute is niet toegelaten door deze consolidatie. De bestaande structurele route blijft gelden; experiment en protocolwijziging zijn vereist voor een nieuwe route.
- De afstemming tussen `decision_unit_construction_v1` en `materialise_knowledge_candidates` staat als open ontwerp-/implementatiepunt in R4.6. Deze archivering lost dat punt niet op.
- De V2-keten bevat ook vervallen tijdelijke verboden en uitvoeringsvolgorden. Die worden niet opnieuw normatief gemaakt. Deze controle is geen nieuwe regel-voor-regel herbeoordeling van alle ooit genomen V2-besluiten; de bestaande consolidatie in V3/V4 blijft het uitgangspunt.

## Archivering en behoud van bewijs

Alle 33 afzonderlijke V2-protocolbestanden zijn met identieke bytes naar `docs/history/protocol-v2/` verplaatst. Op de oude paden staan uitsluitend relatieve compatibiliteitslinks. Dit bewaart de pad- en hashbinding van bestaande approval-manifests en historische verwijzingen zonder een tweede inhoudelijke kopie buiten history te bewaren.

De V3- en v4.0-snapshots en alle historische approval-manifests blijven byte-identiek. Bestaande releaseversies worden niet gewijzigd. `PROTOCOL.md` blijft de enige actuele norm; de roadmap bevat het open implementatiewerk.
