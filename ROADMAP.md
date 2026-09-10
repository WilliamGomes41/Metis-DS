# Metis — Roadmap v3

**Status:** actief  
**Datum:** 2026-09-10  
**Functie:** alleen actieve veranderopgaven, experimenten, beslispoorten en stopvoorwaarden. Uitgevoerde geschiedenis hoort in changelog, audit of `docs/history/`.

## R3.1 Governance-migratie afronden

Doel: Protocol v3 als enige actuele norm laten functioneren zonder verlies van V2-auditbewijs.

Gereed wanneer:
- `PROTOCOL.md` Protocol v3 is;
- historische V2-rootstanden bevroren zijn onder `docs/history/protocol-v2/`;
- approval-manifests controleerbaar blijven;
- governance-tests huidige invarianten bewijzen in plaats van historische V2-tekst in actuele stuurdocumenten af te dwingen;
- CI groen is.

Besluit: `ACTIVATE V3` wanneer alle voorwaarden zijn gehaald; anders `REVISE V3`.

## R3.2 Governance-tests migreren

Doel: documenttests terugbrengen tot actuele V3-invarianten en afzonderlijke historische auditchecks.

Niet doen:
- productgedrag wijzigen om documenttests groen te krijgen;
- historische approval-manifests herschrijven;
- oude V2-artefacten verwijderen wanneer hun bytes of paden deel zijn van auditbewijs.

Gereed wanneer:
- actuele tests geen V2-deltatekst meer vereisen in root `PROTOCOL.md` of `ROADMAP.md`;
- historische tests alleen historische bestanden en manifests controleren;
- release-control preflight de migratie accepteert;
- volledige CI groen is.

## R3.3 Audit > Experiments

Bouw binnen `Audit` een beperkte experimenteerfunctie die:
- een document en vaste dataset vastzet;
- baseline en kandidaatroute parallel uitvoert;
- varianten blind of aantoonbaar vergelijkbaar laat reviewen;
- metrics, correcties en reviewtijd vastlegt;
- een expliciet `KEEP`, `ITERATE` of `PROCEED`-besluit registreert;
- nooit rechtstreeks naar canonieke publicatie schrijft.

Geen console-rewrite. Geen nieuw frontendframework. Geen microservicesplitsing voor dit doel.

## R3.4 Eerste experiment: passagevorming

Onderzoeksvraag: kan brongebonden semantische passagevorming betere kennisobjectvoorstellen maken dan de huidige deterministische passagevorming zonder brontrouw of publicatieveiligheid te verliezen?

Baseline: huidige productiepassagevorming.  
Kandidaat: brongebonden semantische voorstellen.  
Deterministische verificatie van harde invarianten blijft verplicht.

Meet minimaal:
- onvolledige kennisobjecten;
- ontbrekende context, voorwaarden of uitzonderingen;
- benodigde handmatige correcties;
- reviewtijd;
- onverifieerbare toevoegingen.

Veiligheidscriterium: nul tolerantie voor onverifieerbare toevoegingen die als brongebonden kennis zouden kunnen doorstromen.

Besluit: `KEEP`, `ITERATE` of `PROCEED`.

Tot een `PROCEED`-besluit blijft de bestaande productiepassagevorming leidend.

## R3.5 Semantiek en invarianten gericht scheiden

Alleen na voldoende bewijs uit R3.4:
- identificeer lexicale regels die semantische interpretatie proberen te doen;
- behoud bron-, review-, status- en publicatie-invarianten deterministisch;
- verwijder of vereenvoudig semantische uitzonderingslogica alleen met regressiebewijs.

Geen brede rewrite.

## R3.6 Review-statusovergangen isoleren

Alleen wanneer verdere consolewijzigingen dit aantoonbaar nodig maken: isoleer statusovergangen uit grote consolefuncties tot een kleine expliciete grens. Geen algemene console-refactor.

## R3.7 GitHub Actions → Azure OIDC herstellen

Herstel de bedoelde CI/CD-route en bewijs een gecontroleerde deployment vanaf een identificeerbare commit. Cloud Shell ZIP blijft daarna uitsluitend noodprocedure, niet de normale workflow.

Dit spoor verandert geen kennis-, review- of publicatielogica.

## Open governancebesluiten

De operationele beslisstatus blijft in `docs/GOVERNANCE.md`. Open beslissingen blijven `BLOCKED` waar hun deadline-gate dat vereist.

De gevestigde GD-03 reviewermatrix blijft van kracht:
- C3 Canonical/review: 2 onafhankelijke reviewers, clinical + technical;
- C4 Retrieval/answerability: 2, evaluation + technical;
- C5 Publication/security: 2, security/operations + technical;
- C6 Generation: 3, clinical + technical + safety/evaluation.

AI, Grok Bot en Metis tellen niet als vereiste menselijke C3–C6-reviewer, mogen niet goedkeuren en mogen niet publiceren.

## Stopregels

- Geen nieuwe Protocol-v2-delta's.
- Geen keten van Protocol-v3-delta's.
- Geen nieuwe lexicale taalregel zonder classificatie als semantische interpretatie of harde invariant.
- Geen frontend-rewrite.
- Geen microservicesplitsing zonder afzonderlijk bewijs dat de huidige grens het probleem veroorzaakt.
- Geen experimentele modelroute met directe canonieke publicatierechten.
- Geen algemene G2-`PASS`: publicatie blijft conditioneel per snapshot volgens `PROTOCOL.md`.
- Geen Product API-activatie als neveneffect van G2-publicatie.

## Besluitlog

| Besluit | Status |
|---|---|
| Protocol v3 activeren | IN UITVOERING — rootnorm omgezet; testmigratie + groene CI nog vereist |
| Audit > Experiments bouwen | OPEN — na/naast afronding governance-migratie |
| Hybride passagevorming invoeren | NIET BESLOTEN — afhankelijk van experiment |
| Bestaande passagevorming vervangen | NIET BESLOTEN |
| OIDC standaard deployment herstellen | OPEN |
