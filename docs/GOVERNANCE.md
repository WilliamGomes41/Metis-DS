# Metis governance

**Status:** actief onder Protocol v3.0.0  
**Datum:** 2026-09-10

Dit bestand is het compacte operationele governance-register. Het is geen tweede protocol, geen geschiedenislog en geen vijfde stuurlaag.

## Huidige autoriteit

De sturingsvolgorde is:

`PROTOCOL.md → ROADMAP.md → acceptatietests → code`

Daarbij geldt:

1. `PROTOCOL.md` — actuele product-, veiligheids- en governance-invarianten;
2. `ROADMAP.md` — actieve veranderopgaven en beslispoorten;
3. acceptatie- en regressietests — uitvoerbaar bewijs;
4. code, configuratie en infrastructuur — implementatie.

Protocol-v2-delta's, oude roadmaps, approval-manifests en de pre-v3 governance blijven auditbewijs. Zij zijn niet aanvullend normatief onder V3. De volledige pre-v3 governance staat in `docs/history/protocol-v2/GOVERNANCE_PRE_V3_2026-09-10.md`.

## Besluitdiscipline

- Een blijvende product- of veiligheidsinvariant wordt rechtstreeks in `PROTOCOL.md` verwerkt en waar mogelijk door een gedragstest bewezen.
- Een nog open wijziging, experiment of beslispoort staat in `ROADMAP.md`.
- Afgeronde of gesupersedeerde besluitgeschiedenis gaat naar `docs/history/`, changelog of auditrapport; niet naar de actuele roadmap.
- Er wordt geen nieuwe keten van Protocol-v3-delta's opgebouwd.
- Een tijdelijke deployment- of incidentworkaround wordt niet automatisch architectuurwet.
- Een experiment mag geen canonieke publicatie uitvoeren; overgang naar productie vereist een expliciet evidence-backed `KEEP`, `ITERATE` of `PROCEED`-besluit.

## Auditgrens

Historische approval-manifests en protocolbestanden blijven ongewijzigd op hun bestaande paden wanneer hun hashes of paden onderdeel zijn van de bewijsketen. Dat behoudt reproduceerbaarheid zonder ze opnieuw tot actuele stuurlaag te maken.

Historische V2-regressietests mogen de bevroren pre-v3 rootdocumenten toetsen. V3-regressietests toetsen uitsluitend de actuele rootnorm en actuele roadmap.

## Actuele open besluiten

De actuele lijst staat uitsluitend in `ROADMAP.md`. Dit bestand dupliceert die backlog niet.
