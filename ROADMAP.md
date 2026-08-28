# V&VN Data Services — Technische roadmap

## Functie

Deze roadmap bepaalt de uitvoeringsvolgorde van de geldende norm uit `PROTOCOL.md`. De roadmap mag het protocol niet afzwakken of stilzwijgend uitbreiden. `HANDOFF.md` bevat de actuele voortgang; deze roadmap bevat de geplande volgorde en stopvoorwaarden.

Deze repository is uitsluitend V&VN Data Services. Status, fasen of UI van andere producten horen niet in dit document.

## Niet-onderhandelbare doelen

- Fail-closed bronintegriteit en publicatie.
- Retrieval en answerability blijven gescheiden.
- Onafhankelijke no-answer-acceptatie richt zich op `FAR = 0%`.
- Holdout A wordt niet gebruikt voor tuning of een nieuwe onafhankelijkheidsclaim.
- Alleen actieve, gepubliceerde, entitled en herleidbare kennis mag een ondersteund resultaat vormen.
- Eén integrity-kernel is de hash-autoriteit voor review-snapshot, store-import en publicatiegate.
- Het DS-MVP blijft beperkt tot U1 bronverwijzing en U2 kennisrespons.
- Technische toegang is nooit automatisch een licentie, V&VN-goedkeuring of toestemming voor modeltraining.
- Een interne operations console MAG in deze repository als menselijk oppervlak over de knowledge kernel (Protocol v2.6, goedgekeurde scope, niet gebouwd). Een zorgapp-frontend, chatbot, EPD/ECD-UI of publieke website MAG dat niet. Chat hoort niet in de console.
- First-wave officiële bestanden zijn HTML-pagina en PDF; kennisplatform `story.html`-boomplayers vallen buiten de first wave (Protocol v2.7).
- De Product API is object-level retrieve-and-abstain; DS genereert geen proza; geen LLM in het MVP; `supported` draagt V- en VN-labels; tenant = wie de API MAG aanroepen.
- Het standaardproduct is een live retrieve-and-abstain-abonnement. Training MAG alleen als tweede licentie mét live publicatiestatuscheck. Care-impact-onderzoek en federated learning horen niet bij DS.

## Fasen naar MVP

### Fase 1 — Repository en governance-baseline

Status: G1-technische protection ON; gezaghebbende remote is public onder Protocol v2.5.0; resterende nazorg: named GD-03-reviewers en retrospectieve C5-review. Azure/G8 niet gestart. Protocol v2.7.0 is live. Protocol v2.6.0 blijft de goedgekeurde-niet-gebouwde console-scope; de console is niet geïmplementeerd.

- Gezaghebbende remote `WilliamGomes41/VENVN-DS` is public tijdens de gedeclareerde MVP-periode (Protocol v2.5.0). Publiek is niet de latere productiestandaard; na de MVP MUST een nieuw plan private hosting of een organisatieplan herstellen.
- CI, repository-preflight en architectuur-invarianttests.
- Protocol v2.7.0 vastgesteld en live (v2.2 + v2.3-delta + v2.4-delta + v2.5-delta + v2.6-delta + v2.7-delta), inclusief G0, product-/distributiegrenzen, de MVP-uitzondering voor een publieke remote, de interne operations console als goedgekeurde-niet-gebouwde scope, en first-wave bron / retrieve-and-abstain / distributieregels.
- Ontwikkelhiërarchie en handoffdiscipline geborgd.
- Stackbaseline en machineleesbaar infrastructuurmanifest aanwezig.
- G0 Local Development: `PASS`; G0 Azure DEV: `BLOCKED` totdat open keuzes zijn opgelost. Geen Azure starten in deze fase.
- Integrity kernel als enige canonical-hash voor store én publication gate (herstel 2026-08-26).
- GD-03 reviewervereisten ESTABLISHED (2026-08-27); evidence in `docs/GOVERNANCE.md`. Named reviewers blijven een latere bezettingsstap en zijn niet bezet.
- Historische STEP-/audit-/repair-rapporten verplaatst naar `docs/history/` (2026-08-27); de root is het operationele oppervlak, geen vijfde stuurlaag.
- Retrospectieve onafhankelijke review van de C5-wijzigingen in PR #4, PR #5, PR #16, Protocol v2.6 / PR #18 en Protocol v2.7 blijft verschuldigd.
- G1 technische protection is ON. GitHub-ruleset **G1 main** (id `21686159`, 2026-08-27T22:10:53Z): geen verwijderen van `main`, geen force-push / non-fast-forward, required CI `test (3.12)` en `test (3.13)` (strict), pull request verplicht vóór merge, 0 vereiste goedkeurende reviews (solo owner). Protected branch, required CI en PR-workflow bestaan. Volgende uitvoeringsstap is Fase 2 (duurzame immutable opslag van bron 2). De console komt daarna, niet in plaats daarvan.

Stopvoorwaarde: C3–C6-merges vereisen de vastgestelde GD-03-matrix en onafhankelijke menselijke reviewers op dezelfde commit/snapshot; named reviewers zijn nog niet bezet. Bugfixes van bestaande protocolregels blijven toegestaan. Protocol v2.5 (PR #16), Protocol v2.6 (PR #18) en Protocol v2.7 zijn eigenaarsgoedgekeurde C5-delta's; retrospectieve technical- en security/operations-review van PR #4, PR #5, PR #16, v2.6 en v2.7 blijft verschuldigd. GD-03 blijft ESTABLISHED.

### Fase 2 — Canonieke bron 2

Status: technische acquisitie en extractie ontwikkeld; menselijke en duurzame opslagstappen open. Niet overslaan voor consolewerk.

- Exacte officiële bronrepresentatie duurzaam en immutable opslaan.
- First-wave officiële bestanden zijn de HTML-pagina en de PDF; kennisplatform `story.html`-boomplayers vallen buiten de first wave. De officiële file is de kennisplatform-freeze, geen levend Word-document. Een URL MUST onmiddellijk naar exacte bytes worden gesnapshot (Protocol v2.7).
- Source manifest voltooien en integriteit opnieuw verifiëren.
- Deterministische extractie en object-diff genereren.
- Klinische review uitvoeren op de exacte snapshot en afgeleide objecten.
- Alleen na alle gates goedkeuren en publiceren.

Stopvoorwaarde: ontbrekende bytes, checksum, immutable locator, provenance of review houdt publicatie `BLOCKED`. Console-implementatie start pas nadat bron 2-opslag ten minste vastlegbaar is (bytes + hash + locatorpad).

### Fase 2b — Interne operations console (Protocol v2.6)

Status: gepland intern oppervlak; Protocol v2.6 keurt de scope goed; de console is niet geïmplementeerd. Niet in plaats van Fase 2.

- Start pas nadat bron 2-opslag ten minste vastlegbaar is (bytes + SHA-256 + locatorpad).
- Frontend: intuïtieve console voor richtlijnonderzoekers en reviewers. Backend: immutable bronstore + canonieke kennisobjecten. Product API blijft een aparte machinedeur.
- Vier kamers, geen vier knoppen voor één persoon: Ingest (mailbox), Review (verplichte return-loop), Publish (apart geautoriseerd besluit), Analytics (laatst, na verkeer).
- Console-MVP: ingest + review-loop. Publish is een kleine derde kamer. Analytics niet eerst bouwen.
- Identiteit verplicht in de console: researcher, reviewer, publisher; geen gedeelde login voor review/publish. Uploader MAG reviewer zijn, MUST NOT de enige vereiste reviewer op die snapshot zijn. Publicatie blijft BLOCKED tot minstens één andere benoemde reviewer dezelfde snapshot heeft goedgekeurd — afdwingen in accounts, niet als sociale regel.
- Chat is geen kamer in deze console. Zorgapp-frontend, chatbot, EPD/ECD-UI en publieke website blijven verboden in deze repository.
- Console-ingest vereist een immutable store (Azure Blob wanneer G0 Azure DEV PASSes; lokaal `sources/private/` alleen als G0 Local-substituut, expliciet geen productie).
- Identiteitsprovider blijft `TBD` en onderworpen aan G0; dit sluit G8 niet en provisioneert geen Azure AD.

Stopvoorwaarde: geen consolecode claimen als bestaande waarheid; geen analytics-first; geen chat in de console; geen shared login; uploader niet de enige vereiste reviewer; geen bronbinaries in Git.

### Fase 3 — Evaluatie en onafhankelijke acceptatie

Status: nog uit te voeren.

- Development set vastleggen zonder holdoutcontaminatie.
- Holdout B onafhankelijk ontwerpen, vergrendelen en hashen.
- Answerable en moeilijke no-answer-cases opnemen, inclusief relationele, numerieke, populatie- en versieconflicten.
- Onafhankelijke acceptatie uitvoeren zonder tuning op holdout B.
- Release alleen bij alle protocolgates en `FAR = 0%` binnen de afgesproken scope.
- Console-analytics MUST NOT worden gebruikt om Holdout B te tunen.

Stopvoorwaarde: geen onafhankelijkheidsclaim op basis van Holdout A of de development/golden set.

### Fase 4 — MVP-servicelaag

Status: deels aanwezig (Product API + interne inspection); afronden na Fase 2–3. Interne operations console is Fase 2b, niet deze servicelaag.

- Product API uitsluitend voeden met `supported` evidence op objectniveau.
- Ongepubliceerde branch-objecten MUST abstainen, ook als de trunk gepubliceerd is.
- `supported` MUST V- en VN-labels dragen. Alle gepubliceerde V- en VN-objecten serveren.
- Inspection en Product API gebruiken dezelfde answerability-gate.
- Abstention is een gesloten zinnencatalogus in de console (reviewed als een kleine richtlijn); reason codes zichtbaar maken.
- DS MUST NOT proza genereren. Geen LLM in het MVP.
- End-to-end validatie van query tot bronverwijzing.
- Stabiele object-ID's, bronversie, status en canonical links leveren.
- API/schema versieerbaar maken en contracttests voor provenance en withdrawal toevoegen.
- Logging en audittrail zonder vertrouwelijke bron- of reviewdata te lekken.
- Geen zorgapp-frontend, chatbot, EPD/ECD-UI of publieke website in deze repository. Inspection is intern en read-only. De interne operations console is een apart goedgekeurd oppervlak (Fase 2b), nog niet gebouwd.

Stopvoorwaarde: geen generation/LLM in deze service; similarity is nooit answerability; U3–U5 zijn buiten MVP; chat is geen Product API-kamer en geen consoleruimte; geen ziekenhuisprotocollen, adoptielijsten of patiëntgegevens opslaan.

### Fase 5 — Azure DEV en operationele gereedheid

Status: `BLOCKED` onder G0 Azure DEV totdat toegang, eigenaarschap, kosten en platformbesluiten beschikbaar zijn.

- Infrastructuurmanifest per gekozen Azure-component afronden: provider/product, regio, data boundary, identity/secrets, eigenaar en kosten.
- Azure DEV inrichten met immutable bronopslag en gescheiden runtime-opslag.
- Console-identiteit en console-hosting blijven `TBD`; geen vendor geselecteerd; geen Vercel/Neon/LLM vereist.
- Deployment reproduceerbaar koppelen aan commit, protocolversie en build-ID.
- Security-, rollback-, withdrawal- en incidenttest uitvoeren.
- MVP-go/no-go assurance-record afronden.

Stopvoorwaarde: geen Azure-provisioning zolang G0 Azure DEV `BLOCKED` is.

### Fase 6 — Externe integratiepilot

Status: gepland na PASS van toepasselijke bron-, acceptance- en operationele gates.

- Eerste betalende abonnee is een Nederlands EPD/ECD (live retrieve-and-abstain-abonnement).
- Ziekenhuis- of universiteits-LLM-bots MAGEN op dezelfde wijze abonneren; DS bouwt die bots niet.
- Eén richtlijn of expliciet begrensde bronset.
- Eén U1- of U2-toepassing.
- Eén zorgorganisatie, één leverancier/ontwikkelpartner en één gebruikersgroep.
- Consumentenregistratie en gebruiksovereenkomst vastleggen.
- Attribution, updates, supersession, withdrawal en incidentmelding end-to-end testen.
- Vooraf veiligheids-, gebruiks- en stopcriteria vaststellen.

Stopvoorwaarde: geen externe toegang zonder juridische, privacy/security- en verantwoordelijkheidstoets; geen U3–U5 zonder nieuwe protocolbeslissing en toepasselijke C3–C6-review.

## Scopebeheer

Nieuwe functionaliteit komt alleen in de roadmap nadat is vastgesteld dat deze door het huidige protocol wordt gedekt. Buiten scope voor de eerste MVP zijn uitbreidingen die de onafhankelijke acceptatie, bronintegriteit of fail-closed publicatie omzeilen of vertragen, een zorgapp-frontend, chatbot, EPD/ECD-UI of publieke website, beslisregels, patiëntspecifiek advies, algemene modeltraining, care-impact-onderzoek en federated learning. Training MAG alleen als tweede licentie mét live publicatiestatuscheck (Protocol v2.7). De interne operations console is onder Protocol v2.6 in scope als gepland intern oppervlak en mag Fase 2 bron 2 niet overslaan.
