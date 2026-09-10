# Metis — Roadmap v3

**Status:** actief  
**Datum:** 2026-09-10  
**Functie:** alleen actieve veranderopgaven, experimenten, beslispoorten en stopvoorwaarden. Uitgevoerde geschiedenis hoort in changelog, audit of `docs/history/`.

## R3.1 Governance-migratie afronden

**Status:** GEREED — Protocol v3.0.0 is geactiveerd via PR #149; de definitieve CI was groen.

Doel: Protocol v3 als enige actuele norm laten functioneren zonder verlies van V2-auditbewijs.

Gereed wanneer:
- `PROTOCOL.md` Protocol v3 is;
- historische V2-rootstanden bevroren zijn onder `docs/history/protocol-v2/`;
- approval-manifests controleerbaar blijven;
- governance-tests huidige invarianten bewijzen in plaats van historische V2-tekst in actuele stuurdocumenten af te dwingen;
- CI groen is.

Besluit: `ACTIVATE V3` — uitgevoerd via PR #149.

## R3.2 Governance-tests migreren

**Status:** GEREED — actuele V3-tests en historische V2-auditchecks zijn gescheiden; volledige CI was groen voor merge.

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

## R3.3 Audit-kamer + experimentbasis

**Status:** VOLGEND — owner-approved ontwerp-lock 2026-09-10.

Doel: `Audit` wordt de centrale interne inspectiekamer voor meerdere vormen van controle en onderzoek, zonder vooraf een generiek auditframework te bouwen.

Ontwerp-lock:
- de Audit-kamer is generiek; onderliggende audits blijven expliciet en lokaal totdat echte herhaling een gedeelde abstractie rechtvaardigt;
- bestaande controles worden hergebruikt vóór nieuwe auditlogica wordt gemaakt;
- eerste ingangen zijn **Documentkwaliteit**, **Publicatiecontrole** en **Experimenten**;
- read-only controles hoeven geen universele audit-lifecycle of nieuw permanent `audit_record` te krijgen;
- bestaande object-/reviewevents blijven in de huidige append-only audit/review-ledger;
- er komt geen nieuwe accountrol `auditor` voor deze MVP;
- audit wijzigt geen canonieke kennis, publiceert niets en opent geen Product API;
- geen console-rewrite, nieuw frontendframework, microservicesplitsing of generieke `AuditEngine`.

Eerste implementatievolgorde:
1. Audit-kamer en read-only hergebruik van bestaande documentkwaliteit/publicatiecontroles;
2. begrensde experiment-persistence en blind A/B-review;
3. passagevormingsexperiment uit R3.4.

## R3.4 Eerste experiment: passagevorming

**Status:** ONTWERP GEBLOKKEERD — owner-approved 2026-09-10; uitvoering volgt na R3.3 experimentbasis.

Onderzoeksvraag: kan brongebonden semantische passagevorming betere kennisobjectvoorstellen maken dan de huidige deterministische passagevorming zonder brontrouw of publicatieveiligheid te verliezen?

Baseline: huidige productiepassagevorming.  
Kandidaat: brongebonden semantische voorstellen.  
Beide routes lopen na kandidaatvorming door dezelfde deterministische verificatie van harde invarianten.

Vaste workflow:
1. **Opzetten** — onderzoeksvraag, baseline, kandidaat, beoordelingscriteria en stopregel vastleggen;
2. **Dataset vastzetten** — een kleine representatieve frozen set maken met gewone én moeilijke passages, bronidentiteit en baseline-commit; na freeze niet stilzwijgend wijzigen;
3. **Beide routes uitvoeren** — baseline en kandidaat produceren alleen experimentoutputs; de kandidaatroute mag bronspans selecteren/combineren en context/type/relaties voorstellen, maar geen canonieke tekst verzinnen, parafraseren als bronwaarheid, buiten de frozen bron lezen of publiceren;
4. **Blind beoordelen** — reviewer ziet bron + Variant A + Variant B zonder route-identiteit en kiest A, B, gelijkwaardig of beide onvoldoende;
5. **Foutcategorieën vastleggen** — minimaal onvolledig, context gemist, voorwaarde/uitzondering gemist, verkeerde merge/split, onverifieerbare toevoeging en correctie nodig;
6. **Resultaten vergelijken** — toon onderliggende tellingen en reviewtijd, gate-yield/coverage en correctielast; geen samengestelde kwaliteitsscore als primaire uitkomst;
7. **Besluit** — pas na review route-identiteit onthullen en `KEEP`, `ITERATE` of `PROCEED` vastleggen met motivering.

Meet minimaal:
- reviewer voorkeur A/B/gelijkwaardig/beide onvoldoende;
- onvolledige kennisobjecten;
- ontbrekende context, voorwaarden of uitzonderingen;
- verkeerde merge/split;
- benodigde handmatige correcties;
- reviewtijd;
- gate-rejecties en bruikbare yield/coverage;
- onverifieerbare toevoegingen.

Veiligheidscriterium: nul tolerantie voor onverifieerbare toevoegingen die als brongebonden kennis zouden kunnen doorstromen.

`PROCEED` betekent uitsluitend dat er voldoende bewijs is voor een aparte, begrensde productie-integratieproef. Het is geen publicatiebesluit en geen automatische vervanging van de bestaande route.

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
- Geen generiek auditframework voordat meerdere echte auditvormen aantoonbaar dezelfde state en persistence delen.
- Geen experimentele modelroute met directe canonieke publicatierechten.
- Geen algemene G2-`PASS`: publicatie blijft conditioneel per snapshot volgens `PROTOCOL.md`.
- Geen Product API-activatie als neveneffect van G2-publicatie.

## Besluitlog

| Besluit | Status |
|---|---|
| Protocol v3 activeren | GEREED — PR #149 gemerged; Protocol v3.0.0 actief; CI groen |
| Audit-kamer als brede inspectiekamer | LOCKED — 2026-09-10 |
| Generiek auditframework vooraf bouwen | AFGEWEZEN — eerst expliciete auditvormen en hergebruik |
| Passagevormingsexperiment | LOCKED ONTWERP — frozen dataset, blind A/B, gedeelde harde gates, KEEP/ITERATE/PROCEED |
| Hybride passagevorming invoeren | NIET BESLOTEN — afhankelijk van experiment |
| Bestaande passagevorming vervangen | NIET BESLOTEN |
| OIDC standaard deployment herstellen | OPEN |
