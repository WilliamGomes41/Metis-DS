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

**Status:** IN UITVOERING — owner-approved ontwerp-lock, retro-lock en UX-lock 2026-09-10; basis geïmplementeerd via PR #153.

Doel: `Audit` wordt de centrale interne inspectiekamer voor meerdere vormen van controle en onderzoek, zonder vooraf een generiek auditframework te bouwen.

Ontwerp-lock:
- de Audit-kamer is generiek; onderliggende audits blijven expliciet en lokaal totdat echte herhaling een gedeelde abstractie rechtvaardigt;
- gebruikers kunnen zelf een audit aanmaken door een beschikbaar audittype te kiezen;
- audittypen worden als kleine gesloten configuratie aangeboden; nieuwe typen krijgen hun eigen uitvoering en hoeven geen universele workflow te delen;
- de gedeelde persistence kent alleen een minimale type-onafhankelijke envelope: audit-id, type, titel, maker, timestamps en een type-specifieke payload;
- experiment-specifieke baseline, kandidaat, dataset, review en besluit horen niet in de gedeelde storelogica;
- bestaande controles worden hergebruikt vóór nieuwe auditlogica wordt gemaakt;
- eerste echte auditvormen zijn **Experiment** en een minimale read-only **Documentkwaliteit**-audit; **Publicatiecontrole** en **Techniek & release** blijven nog uitgeschakeld;
- Documentkwaliteit dient tevens als architectuurproef: toevoegen van een tweede auditvorm mag de gedeelde storevorm niet veranderen;
- read-only controles hoeven geen universele audit-lifecycle te krijgen;
- bestaande object-/reviewevents blijven in de huidige append-only audit/review-ledger;
- er komt geen nieuwe accountrol `auditor` voor deze MVP;
- audit wijzigt geen canonieke kennis, publiceert niets en opent geen Product API;
- geen console-rewrite, nieuw frontendframework, microservicesplitsing of generieke `AuditEngine`.

UX-lock:
- `Audit` staat als normale kamer in de bestaande gedeelde topnavigatie, tussen **Documenten** en **Accounts**;
- op **Mijn werk** blijven **Inleveren → Review → Publiceren → Documenten** de vier gelijkwaardige primaire workflowtegels;
- Audit wordt daar als afzonderlijke brede meta-tegel onder de workflow getoond onder **Onderzoeken & controleren**;
- de Audit-tegel gebruikt de bestaande V&VN-paarse signatuur op wit en introduceert geen nieuwe merkkleur of apart tegelcomponent;
- Audit wordt niet visueel gepresenteerd als vijfde stap in de publicatiestroom.

Eerste implementatievolgorde:
1. Audit-kamer, zelf audit aanmaken, minimale type-onafhankelijke persistence en read-only Documentkwaliteit als tweede echte auditvorm;
2. Audit zichtbaar maken in de normale console-navigatie en als afzonderlijke meta-tegel op Mijn werk;
3. begrensde experiment-persistence voor dataset-freeze en blind A/B-review;
4. passagevormingsexperiment uit R3.4.

Retro-besluit 2026-09-10: **SIMPLIFY BEFORE EXTENDING**. Dataset-freeze en A/B-uitvoering worden niet toegevoegd voordat de gedeelde AuditStore aantoonbaar type-onafhankelijk blijft en een tweede auditvorm zonder wijziging van de storevorm werkt.

Capability-closure-regel:
- voor iedere nieuwe materiële capability moet vooraf expliciet zijn wat de input is, welke output ontstaat, wie of wat de volgende stap uitvoert en waar de verantwoordelijkheid van Metis eindigt;
- een downstream-stap die geen bestaande technische executor heeft, mag niet als werkende Metis-capability worden beschreven;
- Audit-output mag op zichzelf een eindproduct zijn: bewijs hoeft niet automatisch tot code, GitHub of deployment te leiden.

## R3.4 Eerste experiment: passagevorming

**Status:** ARCHITECTUUR HERZIEN EN LOCKED — owner-approved 2026-09-10; Audit stopt bij bewijs en verbeterbundel, softwareontwikkeling blijft buiten Metis.

Onderzoeksvraag: kan brongebonden semantische passagevorming betere kennisobjectvoorstellen maken dan de huidige deterministische passagevorming zonder brontrouw of publicatieveiligheid te verliezen?

Baseline: huidige productiepassagevorming.  
Kandidaat: brongebonden semantische bronselectie binnen Audit.  
Beide routes lopen na kandidaatvorming door dezelfde deterministische verificatie van harde invarianten.

Architectuurlock AI en Kernel:
- AI is uitsluitend een experimenteel instrument binnen de Audit-kamer;
- de Kernel blijft AI-vrij: geen modelcall, modeloutput of modelprovider krijgt een direct schrijfpad naar canonieke kennis, reviewstatus, publicatielogica of productie-state;
- het LLM mag uitsluitend exacte bronspans selecteren of combineren en context/type/relaties voorstellen;
- het LLM mag geen canonieke brontekst schrijven, herschrijven of parafraseren als bronwaarheid;
- Metis reconstrueert een kandidaat zelf uit de aangewezen spans van de frozen bron, zodat kandidaattekst herleidbaar blijft tot bronbytes, bronhash en locator;
- de reviewer ziet altijd de relevante originele bron, baseline, kandidaat en bijbehorende bronspans;
- modeloutput, experimentresultaten en conclusies blijven Audit-bewijs en stromen niet automatisch door naar de Kernel.

LLM-secretlock:
- de gebruiker kan de LLM API-key uitsluitend via **Audit → LLM-instellingen** invoeren, vervangen of verwijderen;
- de API-key is write-only: na opslaan toont de console alleen `Geconfigureerd` of `Niet geconfigureerd` en nooit de sleutel zelf;
- de plaintext API-key komt niet in Audit-records, frozen datasets, Kernel-state, roadmap/configbestanden of Git;
- de opgeslagen API-key wordt versleuteld met een afzonderlijke deployment-masterkey uit `METIS_AUDIT_SECRET_KEY`; zonder geldige masterkey is invoer in de console fail-closed niet beschikbaar;
- alleen de Audit-runtime mag de ontsleutelde key opvragen voor een toekomstige modelcall; de Kernel importeert deze secretstore niet;
- dit is geen algemene environment-variable- of secret-editor: andere deploymentsettings blijven buiten de console;
- vervangen en verwijderen van de LLM-key geven geen implementatie-, merge-, deploy- of publicatierechten.

Vaste workflow:
1. **Opzetten** — onderzoeksvraag, baseline, kandidaat, beoordelingscriteria en stopregel vastleggen;
2. **Dataset vastzetten** — een kleine representatieve frozen set maken met gewone én moeilijke passages, `item_id`, `snapshot_id`, `source_hash`, `source_locator`, exacte `source_text` en `baseline_commit`; na freeze niet stilzwijgend wijzigen of vervangen;
3. **Beide routes uitvoeren** — baseline en kandidaat produceren alleen experimentoutputs; de kandidaatroute mag uitsluitend werken binnen de frozen bron en publiceert niets;
4. **Blind beoordelen** — reviewer ziet bron + Variant A + Variant B zonder route-identiteit en kiest A, B, gelijkwaardig of beide onvoldoende;
5. **Foutcategorieën vastleggen** — minimaal onvolledig, context gemist, voorwaarde/uitzondering gemist, verkeerde merge/split, onverifieerbare toevoeging en correctie nodig;
6. **Menselijke correctie vastleggen** — een reviewer kan een uitkomst als correct of incorrect markeren en, bij incorrect, de gewenste brongebonden uitkomst vastleggen;
7. **Verbetercollectie vullen** — bevestigde foutgevallen én bestaande goede voorbeelden worden append-only verzameld als regressiebewijs; een individueel voorbeeld leidt niet tot een softwarewijziging of PR;
8. **Patroon bundelen** — meerdere voorbeelden van hetzelfde onderliggende probleem kunnen als één verbeterbundel worden samengebracht met probleemomschrijving, foutgevallen, goede regressiegevallen, gewenste uitkomsten en onderzochte Metis-versie;
9. **READY FOR IMPLEMENTATION** — alleen een voldoende onderbouwde verbeterbundel kan deze status krijgen. Daarmee eindigt de verantwoordelijkheid van Metis; softwareontwerp, programmeren, tests, branch, PR, merge en deployment gebeuren buiten Metis.

Verbetercollectie-lock:
- de collectie is Audit-evidence, geen tweede bron van waarheid en geen generieke learning engine;
- bewaar minimaal bronidentiteit, bronhash/locator, huidige uitkomst, gewenste uitkomst, correct/incorrect, foutcategorie, reviewer en onderzochte Metis-versie;
- bewaar ook goede voorbeelden zodat toekomstige wijzigingen aantoonbaar geen bestaande correcte gevallen breken;
- groepeer op onderliggend foutpatroon; geen vaste PR-drempel per aantal voorbeelden;
- één voorbeeld mag nooit automatisch één change proposal, codewijziging of PR veroorzaken.

Verantwoordelijkheidsgrens:
- Metis detecteert, vergelijkt, laat beoordelen, bewaart bewijs en bundelt verbeterbehoeften;
- Metis programmeert zichzelf niet;
- Metis krijgt voor deze flow geen GitHub-write-integratie, ingebouwde coding-agent of algemene APPLY-executor;
- een menselijke architect/developer kan een `READY FOR IMPLEMENTATION`-bundel buiten Metis samen met een coding-agent of andere ontwikkeltools omzetten in code en regressietests;
- na een externe implementatie mag Audit dezelfde evidence opnieuw gebruiken om te toetsen of het probleem is opgelost en regressies zijn ontstaan;
- een PR- of commitreferentie mag achteraf als Audit-metadata worden vastgelegd, maar GitHub blijft de bron van waarheid voor software.

Meet minimaal:
- reviewer voorkeur A/B/gelijkwaardig/beide onvoldoende;
- onvolledige kennisobjecten;
- ontbrekende context, voorwaarden of uitzonderingen;
- verkeerde merge/split;
- benodigde handmatige correcties;
- reviewtijd;
- gate-rejecties en bruikbare yield/coverage;
- onverifieerbare toevoegingen;
- aantal bevestigde foutgevallen en goede regressiegevallen per foutpatroon.

Veiligheidscriterium: nul tolerantie voor onverifieerbare toevoegingen die als brongebonden kennis zouden kunnen doorstromen.

Beslisbetekenis:
- `KEEP`: huidige productieaanpak behouden;
- `ITERATE`: kandidaat aanpassen binnen Audit en opnieuw experimenteren;
- `EVIDENCE`: een menselijke beoordeling is sterk genoeg om als fout- of regressievoorbeeld in de verbetercollectie op te nemen;
- `READY FOR IMPLEMENTATION`: een gebundeld probleem is voldoende onderbouwd om buiten Metis als ontwikkelopdracht te gebruiken; deze status autoriseert geen codewijziging, GitHub-actie, merge, deploy of publicatie.

Tot een afzonderlijk extern ontwikkelde, geautoriseerde en gereleasete productiewijziging blijft de bestaande productiepassagevorming leidend.

## R3.5 Semantiek en invarianten gericht scheiden

Alleen wanneer een `READY FOR IMPLEMENTATION`-verbeterbundel buiten Metis als expliciete ontwikkelopdracht wordt opgepakt:
- identificeer lexicale regels die semantische interpretatie proberen te doen;
- behoud bron-, review-, status- en publicatie-invarianten deterministisch;
- verwijder of vereenvoudig semantische uitzonderingslogica alleen met regressiebewijs uit de verbetercollectie.

Softwareontwerp, codewijziging en PR vallen buiten Audit en zijn geen Metis-runtimeverantwoordelijkheid.

Geen brede rewrite.

## R3.6 Review-statusovergangen isoleren

Alleen wanneer verdere consolewijzigingen dit aantoonbaar nodig maken: isoleer statusovergangen uit grote consolefuncties tot een kleine expliciete grens. Geen algemene console-refactor.

## R3.7 GitHub Actions → Azure OIDC herstellen

Herstel de bedoelde CI/CD-route en bewijs een gecontroleerde deployment vanaf een identificeerbare commit. Cloud Shell ZIP blijft daarna uitsluitend noodprocedure, niet de normale workflow.

Dit spoor verandert geen kennis-, review- of publicatielogica en is onafhankelijk van Audit-verbeterbundels.

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
- Geen AI/modelroute buiten Audit zolang geen afzonderlijk architectuurbesluit dat expliciet wijzigt.
- Geen modeloutput met directe schrijf-, review-, publicatie- of canonieke rechten in de Kernel.
- Geen algemene environment-variable- of secret-editor in de console voor de Audit-LLM-koppeling.
- Geen plaintext LLM API-key in Git, gewone config, auditrecords, frozen datasets of Kernel-state.
- Geen individuele fout of correctie die automatisch een softwarewijziging, branch of PR veroorzaakt.
- Geen `READY FOR IMPLEMENTATION` als impliciete autorisatie voor codewijziging, GitHub-write, merge, deploy of publicatie.
- Geen GitHub-write-integratie, coding-agent of algemene software-executor in Audit zonder een nieuw expliciet architectuurbesluit met capability-closure.
- Geen downstream-capability als werkend beschrijven zolang geen echte technische executor bestaat.
- Geen algemene G2-`PASS`: publicatie blijft conditioneel per snapshot volgens `PROTOCOL.md`.
- Geen Product API-activatie als neveneffect van G2-publicatie.

## Besluitlog

| Besluit | Status |
|---|---|
| Protocol v3 activeren | GEREED — PR #149 gemerged; Protocol v3.0.0 actief; CI groen |
| Audit-kamer als brede inspectiekamer | LOCKED — 2026-09-10 |
| Gebruiker maakt zelf audit aan via audittype | LOCKED — 2026-09-10 |
| AuditStore blijft type-onafhankelijk; type-uitvoering lokaal | LOCKED NA RETRO — 2026-09-10 |
| Documentkwaliteit als tweede architectuurproef | LOCKED NA RETRO — 2026-09-10 |
| Audit als normale nav-kamer + brede paarse meta-tegel onder workflow | LOCKED UX — 2026-09-10 |
| Generiek auditframework vooraf bouwen | AFGEWEZEN — eerst expliciete auditvormen en hergebruik |
| Passagevormingsexperiment | LOCKED — frozen dataset, blind A/B, menselijke correctie en verbetercollectie |
| AI uitsluitend als experimenteel instrument binnen Audit | LOCKED — geen direct pad naar Kernel of productie-state |
| LLM API-key via Audit-console | LOCKED — write-only, versleuteld at rest, geen algemene secret-editor |
| Audit-verbetercollectie | LOCKED — append-only bewijs van fouten én goede regressiegevallen; geen tweede bron van waarheid |
| Audit → READY FOR IMPLEMENTATION | LOCKED — hier eindigt Metis; ontwikkeling gebeurt buiten Metis |
| Metis programmeert zichzelf / automatische APPLY → GitHub | AFGEWEZEN — geen coding- of GitHub-writeverantwoordelijkheid in Audit |
| Hybride passagevorming invoeren | NIET BESLOTEN — afhankelijk van bewijs en afzonderlijke externe implementatiebeslissing |
| Bestaande passagevorming vervangen | NIET BESLOTEN |
| OIDC standaard deployment herstellen | OPEN |
