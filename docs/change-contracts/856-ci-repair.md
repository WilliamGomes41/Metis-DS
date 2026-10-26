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
