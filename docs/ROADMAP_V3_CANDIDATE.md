# Metis — Roadmap v3 candidate

**Status:** candidate  
**Datum:** 2026-09-10  
**Functie:** alleen actieve veranderopgaven, experimenten en beslispoorten. Uitgevoerde geschiedenis hoort niet in deze roadmap.

## Nu — governance vereenvoudigen

### R3.1 Protocol v3 activeren

Doel: de gestapelde Protocol-v2-deltaketen vervangen door één actuele norm.

Gereed wanneer:
- Protocol v3 de blijvende product-, bron-, review-, publicatie-, audit- en security-invarianten dekt;
- de pre-v3 protocol- en roadmapstand bevroren in historie staat;
- historische approval-manifests controleerbaar blijven;
- tests niet langer historische formuleringen in actuele stuurdocumenten afdwingen;
- CI groen is.

Besluit: `ACTIVATE V3` of `REVISE V3`.

### R3.2 Governance-tests ontkoppelen van historische tekst

Doel: tests bewijzen huidig gedrag en harde invarianten in plaats van te eisen dat oude deltatekst in `PROTOCOL.md` of `ROADMAP.md` blijft staan.

Niet doen:
- productgedrag wijzigen om documenttests groen te krijgen;
- historische approval-manifests herschrijven;
- historische auditbestanden verwijderen.

Gereed wanneer huidige governance-tests tegen Protocol v3 werken en historische tests uitsluitend historische artefacten controleren.

## Volgende — Audit > Experiments

### R3.3 Generieke experimenteerfunctie in de console

Bouw binnen `Audit` een beperkte experimenteerfunctie die:
- een document en vaste dataset vastzet;
- baseline en kandidaatroute parallel uitvoert;
- varianten blind of vergelijkbaar laat reviewen;
- metrics en correcties vastlegt;
- een expliciet `KEEP`, `ITERATE` of `PROCEED`-besluit registreert;
- nooit rechtstreeks naar canonieke publicatie schrijft.

Geen console-rewrite. Geen nieuw frontendframework. Geen microservicesplitsing voor dit doel.

### R3.4 Eerste experiment: passagevorming

Onderzoeksvraag: kan semantische passagevorming betere kennisobjectvoorstellen maken dan de huidige deterministische passagevorming zonder brontrouw te verliezen?

Baseline: huidige productiepassagevorming.  
Kandidaat: brongebonden semantische voorstellen.  
Deterministische verificatie blijft verplicht.

Meet minimaal:
- onvolledige kennisobjecten;
- ontbrekende context, voorwaarden of uitzonderingen;
- benodigde handmatige correcties;
- reviewtijd;
- onverifieerbare toevoegingen.

Veiligheidscriterium: nul tolerantie voor onverifieerbare toevoegingen die als brongebonden kennis zouden kunnen doorstromen.

Besluit: `KEEP`, `ITERATE` of `PROCEED`.

Tot een `PROCEED`-besluit blijft de bestaande productiepassagevorming leidend.

## Daarna — alleen bij bewezen noodzaak

### R3.5 Semantiek en invarianten gericht scheiden

Alleen na voldoende bewijs uit R3.4:
- identificeer lexicale regels die semantische interpretatie proberen te doen;
- behoud harde bron-, review- en publicatie-invarianten deterministisch;
- verwijder of vereenvoudig semantische uitzonderingslogica alleen met regressiebewijs.

Geen brede rewrite.

### R3.6 Review-statusovergangen isoleren

Alleen wanneer verdere consolewijzigingen dit aantoonbaar nodig maken: statusovergangen uit grote consolefuncties isoleren tot een kleine expliciete grens. Geen algemene console-refactor.

## Operationeel spoor

### R3.7 GitHub Actions → Azure OIDC herstellen

Herstel de bedoelde CI/CD-route en bewijs een gecontroleerde deployment vanaf een identificeerbare commit. Cloud Shell ZIP blijft daarna uitsluitend noodprocedure, niet de normale workflow.

Dit spoor verandert geen kennis-, review- of publicatielogica.

## Stopregels

- Geen nieuwe Protocol-v2-delta's.
- Geen keten van Protocol-v3-delta's.
- Geen nieuwe lexicale taalregel zonder classificatie als semantische interpretatie of harde invariant.
- Geen frontend-rewrite.
- Geen microservicesplitsing zonder afzonderlijk bewijs dat de huidige grens het probleem veroorzaakt.
- Geen experimentele modelroute met directe canonieke publicatierechten.

## Besluitlog

Alleen nog open of richtinggevende besluiten staan hier. Uitgevoerde stappen gaan naar changelog/audit/history.

| Besluit | Status |
|---|---|
| Protocol v3 activeren | OPEN — na testmigratie en groene CI |
| Audit > Experiments bouwen | OPEN — na/naast V3-governanceconsolidatie |
| Hybride passagevorming invoeren | NIET BESLOTEN — afhankelijk van experiment |
| Bestaande passagevorming vervangen | NIET BESLOTEN |
| OIDC standaard deployment herstellen | OPEN |
