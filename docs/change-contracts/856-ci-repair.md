Change class: B
Promise: Documentdiagnose geeft de bestaande blokkades en actuele verwerkingsfase consequent weer, en alle verplichte PR-controles worden werkelijk uitgevoerd.
Proof: Bestaande change-contractvalidator en echte bronselectie-browsertest rood/groen; GET-regressies voor toelatingsblokkades en lopende fasen; volledige ongewijzigde CI inclusief PostgreSQL en browsers.
Touches lifecycle invariants: no
Rewrite risk: none

# PR #856 — herstel en verificatie binnen #854

Directe opdracht van William: alle gefaalde checks onderzoeken en oplossen op
de bestaande PR. Geen merge of deployment. De oorspronkelijke mergevoorwaarden
(Sherlock, Argos, Vignet en Williams eigen GO) blijven gelden.

## Mechanisme en begrenzing vóór reparatie

`GET /inzicht/document` autoriseert de actor, leest de bestaande verwerkingsstatus
en laatste poging, en uitsluitend voor de aangewezen reviewer de bestaande
objectdiagnostiek. `processing_diagnostics` beheert de afgeleide aantallen;
`knowledge_publication_blockers` blijft de bestaande eigenaar van
publicatieblokkades. `_diagnosis_steps_html` projecteert de al gelezen
diagnostische fase/checkpoints. Geen nieuwe reads, writes, bevoegdheden,
opslagstatus, publicatiepoort of wijziging aan gedeelde Review-helpers.

Deze reparatie is Class B, omdat het oordeel en de getoonde actuele stap
observeerbaar gedrag corrigeren; uitsluitend de CSS/tekst als Class C benoemen
zou de twee inhoudelijke bevindingen onvoldoende beschrijven. Rewrite risk none.

## Bevindingen en bewijsplan

- `change-contract` op 816ddbc faalt door vijf ontbrekende machineleesbare
  velden; de validator reproduceert dit op de oorspronkelijke PR-tekst.
- De daaropvolgende ontbrekende suite-artefacten zijn gevolgfouten van de
  overgeslagen suites, geen afzonderlijke backendregressies.
- `source-processing-proof` zoekt nog de oude kop `Verwerking` in de
  diagnosepagina. De echte browserroute moet het juiste document en het nieuwe
  oordeel aantonen en de bestaande blokkade-/downloadroute blijven uitvoeren.
- De rode afgewezen-retryproef draait bewust op een vastgepinde historische
  versie; de actuele native acceptatiestap slaagde. Geen autorisatiewijziging.
- GET met technisch geslaagde verwerking en toelatingsblokkades mag geen
  `Geen blokkade vastgelegd` tonen. Tegenvoorbeeld: zonder die blokkades en
  zonder verwerkingsfout blijft dit neutrale oordeel bestaan.
- Lopende verwerking moet de huidige bekende fase tonen; bij een onbekende
  fase geldt het laatste bekende checkpoint, en zonder bekend bewijs stap 1.
  Een bereikt checkpoint bewijst niet dat de bijbehorende stap geslaagd is.
  Eerdere stappen krijgen daarom bij lopend werk geen nieuw succesbewijs.

Behoud toetsenbord/320–390–1280px, rolafscherming, één object- en ledgerread,
herstelcontrols, downloads en letterlijke broncontext. Bestaande betekenisvolle
tests blijven staan. Geen skips of versoepeling om een check groen te maken.
Nieuwe CI moet alle workflows op de uiteindelijke head uitvoeren.

## Lokaal uitgevoerd vóór nieuwe CI

- Oorspronkelijke PR-tekst: de echte validator meldt alle vijf ontbrekende
  velden. Herstelde tekst: PASS; dezelfde validator, geen versoepeling.
- Oorspronkelijke bronselectie-browsertest: rood (43,86 s), timeout op de oude
  kop `Verwerking`. Herstelde echte route: groen (19,21 s), inclusief behoud
  van het gekozen document, download en latere Review, toetsenbord en
  320/390/1280px op Documentdiagnose.
- Nieuwe GET-regressies vóór reparatie: 5 failed, 4 passed (12,25 s).
  De fouten zijn precies het verborgen toelatingsoordeel en vier gevallen
  van lopende verwerking na stap 1. Tegenvoorbeelden blijven groen.
- Na reparatie: 61 gerichte tests geslaagd (122,15 s), waaronder alle 32
  diagnosetests, rolafscherming, read-budget, bestaande herstel/diagnostiek
  en architectuurinvarianten.
- De releasepreflight vond bovendien een ontbrekende `releasebewijs`-marker
  in de oorspronkelijke testmodule. Die verwijst nu ook naar deze echte
  GET-proeven; de verplichte categorie en de validator blijven intact.

Een extra browserassertie nam aanvankelijk ten onrechte aan dat ontvangst
zonder verwerkingspoging al een verwerkingsfoutcode oplevert. De bestaande
projectie bevat die code niet. De proef toetst nu het werkelijk bedoelde
ontvangstcontract: juiste documentcontext en nul gestarte pogingen. Dit is
geen wijziging van verwerkings- of publicatieautoriteit.

Volledige lokale regressie, alle verplichte browsercases en CI op de
uiteindelijke head moeten nog afronden; historische of gedeeltelijke runs
worden niet als dat eindbewijs voorgesteld. Geen productieacceptatie.

Alle zeven verplichte browsercases zijn daarna lokaal geslaagd zonder skips
(241,25 s). De screenshots scrollen expliciet terug naar boven na de
toetsenbordproef, zodat de gedeelde sticky header het beeld niet midden in de
pagina bedekt. De bestaande beoordelings- en downloadcontroles blijven staan.
Voor het definitieve bewijs wordt de inmiddels bijgewerkte main geïntegreerd;
de volledige lokale collectie en CI draaien vervolgens op één vaste head.

## Aanvullende review: onderzoeker zonder reviewerrol

De review op 8dda279 wees terecht op dezelfde ontbrekende blokkade voor
onderzoekers/uploaderaccounts. De eerdere correctie ontving alleen de
reviewerdiagnostiek. De uitgebreide GET-matrix reproduceert dit: 2 failed,
4 passed (7,77 s), met en zonder toelatingsblokkades voor alle drie toegestane
rollen. De eerdere volledige runs worden daarom niet als eindbewijs gebruikt.

Voor reparatie: hergebruik de bestaande requestgebonden `_read_current_objects`
waaruit `processing_status` bij onuitgegeven werk al leest.
`processing_issue_objects` is dezelfde pure blokkadeprojectie die
`processing_diagnostics` in Documenten gebruikt. Gebruik voor
het oordeel/tijdlijn alleen de booleaanse blokkade; details, aantallen, codes,
passage-exports en ledger blijven uitsluitend bij de aangewezen reviewer.
Geen nieuwe querydefinitie of autoriteitsregel toevoegen. De onderzoekerroute
gebruikt nu expliciet de bestaande objectreader; requesteigendom hergebruikt
reeds geladen invoer. Het bewijs is maximaal één objectload, geen universele
claim van exact hetzelfde SQL-aantal bij iedere publicatietoestand.
De GET-bewijsgrens
wordt uitgebreid tot alle vier rollen: hoogstens één objectload, één
objectkopie, geen ledgerread voor onderzoekers/publishers en geen mutaties.

Een vastgelegde verwerkingsfout bepaalt de stopstap vóór onafhankelijke
toelatingsblokkades; bij foutloze afgeronde verwerking blokkeren die stap 4.
Lopende verwerking blijft de actuele fase tonen. De volledige suite en CI
moeten op de uiteindelijke nieuwe head opnieuw afronden.

Na die aanvullende correctie: **68 gerichte tests geslaagd** (87,18 s),
waaronder alle 39 diagnosetests en de budget-/toegangsproeven voor vier rollen.
De echte bronselectie-browserroute slaagt opnieuw (14,79 s), inclusief de
diagnose op drie breedtes en toetsenbordbediening. Preflights, compileall,
architectuurgrenzen en diffcontrole slagen.

De eerste volledige lokale poging miste `psql` op PATH; een afzonderlijke
SQL-proef reproduceerde dat en slaagde na herstel van het zoekpad (3,79 s).
De daarna gestarte volledige poging op 8dda279 is gestopt vanwege de nieuwe
inhoudelijke reviewbevinding. Beide pogingen blijven expliciet onvolledig en
tellen niet als groen eindbewijs. De definitieve run gebruikt PostgreSQL 16
met zijn tools op PATH en opnieuw vier geïsoleerde databases op de nieuwe head.

## Volledigheid van de vastgelegde fasen

De review op 011e6e9 vond dat `validation_started` en `validation_rejected`
nog ontbraken in de oorspronkelijke beperkte fasenkaart. Onderzoek van
`processing_trace_v1.PHASES` en alle checkpointproducenten in
`pre_review_semantic_v1`, `formation_checkpoint_v1`, `processing_retry_v1`,
`worker_handover_v1` en `source_preparation_context_v1` bepaalt nu de hele
bestaande lijst: extractie/reconstructie bij stap 1, taak-/modelvoorstellen
bij stap 2 en controle/bronverantwoording bij stap 4. Geen nieuwe fase of
runtime-workflow wordt geïntroduceerd. Stap 3/5 krijgen geen verzonnen
actieve verwerkingsfase.

Bewijs vóór reparatie: de pure HTML-projectie wordt voor alle bestaande
fasen zowel lopend als mislukt getoetst, met een vroeger modelcheckpoint
als tegenvoorbeeld. Nieuwe canonieke fases vereisen een expliciete
presentatieverwachting. Twee aanvullende echte GET-cases toetsen specifiek
lopende validatie en afgewezen validatie. Ook de volledige poging op
011e6e9 is daarom onvolledig; alleen de uiteindelijke head telt als eindbewijs.

Rood vóór de volledige fasenkaart: **22 failed, 29 passed** (5,23 s).
Na de kaart en expliciete dekking van uitsluitend werkelijk vastgelegde
eerdere stappen: **117 gerichte tests geslaagd** (87,83 s). De browserroute
slaagt eveneens (17,27 s). Repository-/releasepreflight, architectuurgrenzen,
compileall en diffcontrole slagen. De volledige lokale suite en alle vijf
CI-workflows worden opnieuw op de definitieve commit uitgevoerd.

## Retrybeperking is geen mislukte verwerking

De review op 719211c vond een afzonderlijke oorspronkelijke fout: de
retryprojectie kan na een geslaagde laatste poging nog een limiet-/wachttijdreden
dragen. Onderzoek van de hele `processing_retry_v1.status`-beslisboom bevestigt
dat `reason_code` ook beschikbaarheid van een volgende poging beschrijft.
De projectie en haar opslag-/budgetregels blijven ongewijzigd.

De weergave moet daarom technische/retrycode behouden voor inzage, maar voor
het primaire oordeel/tijdlijn apart uitgaan van actuele vormingsproblemen,
vastgelegde fouten/ongelukte toestanden en toelatingsblokkades. Bij een
geslaagde poging is een retryreden zonder fout/bronprobleem geen stopreden.
Een echt mislukte/onderbroken/verlopen of budgetgestopte poging blijft ook
zonder foutcode zichtbaar gestopt. Een overbodig eenmalig herstelformulier
wordt na volledig geslaagde verwerking niet aangeboden; de bestaande guards
voor werkelijk geblokkeerd werk blijven staan.

De native GET-matrix gebruikt de echte retryprojectie met opgeslagen
poginggeschiedenis: limiet/wachttijd × geslaagd/mislukt × wel/geen
toelatingsblokkade × drie toegestane rollen. De vier onvolledige toestanden
zonder code zijn aparte tegenvoorbeelden. De eerdere volledige poging op
719211c blijft expliciet onvolledig, ongeacht de losse groene CI-browserjob.

Rood vóór deze statusscheiding: **16 failed, 12 passed** (62,05 s).
De eerste uitgebreide groene opdracht had een verkeerd testpad en voerde
nul tests uit; zij telt niet als bewijs. Een volgende opdracht gaf vier
onjuiste stopstapverwachtingen: de basisfixture bevatte al een opgeslagen
fase. De proef onderscheidt nu expliciet geen fase (stap 1) en bekende
validatie (stap 4), zonder productgedrag af te zwakken.

Daarna **164 gerichte tests geslaagd** (136,96 s), inclusief de bestaande
native retry-/herstelproeven. Twee aanvullende tegenvoorbeelden slagen
(2,76 s): een geslaagde laatste poging met werkelijk onvolledige vorming
blijft geblokkeerd bij stap 2/4 en behoudt de bestaande eenmalige herstelactie.
De echte browserroute slaagt opnieuw (14,88 s). Alle preflights, compileall,
architectuur- en diffcontrole slagen. Alleen de volledige lokale collectie en
alle CI-workflows op de hierna vastgelegde definitieve head tellen als eindbewijs.
