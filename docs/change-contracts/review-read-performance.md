# Passagegerichte Review en samenhangend werkbord

Change class: B
Promise: Review toont geautoriseerd werk met dezelfde domeinuitkomsten en opent één passage zonder standaard de volledige objectverzameling te laden of te beoordelen.
Proof: Native PostgreSQL HTTP-pariteit en afwijzingsproeven, begrensde payload/domeinlezingen, plus de bestaande 3.000-passagesproef op dezelfde fixture.
Touches lifecycle invariants: no
Rewrite risk: high

## Ground — bestaande werking en eigenaren

`review_get` autoriseert het document en kiest `_workboard_page` of
`_render_review_room`. De native summary-adapter verrijkt alle toegewezen
documenten via `review_work_item` vóór filtering/paginering. De projectie gebruikt
herhaald `review_duty_for`, verschillende wachtrijen en bronverantwoording.
`review_duty_v1` blijft eigenaar van reviewplicht en revieweracties;
`source_containers_v1` blijft eigenaar van bronverantwoording. PostgreSQL bewaart
objectversies, reviewbindings en de bestaande monotone documentrevisie.

Een detail leest nu alle objecten, maakt een objectsettoken en toont onder andere
een complete contextkeuzelijst. Reviewcommands lezen zelfstandig actuele toestand
onder de bestaande command-/transactiegrens. Die commands en hun domeinregels
blijven autoritatief. De eerdere native proef op `f133b86` leverde 141 groene
regressietests en 18 overschrijdingen van vijf seconden bij 3.000 kandidaten op.

## Sketch / Agree — twee alternatieven, één auteur

1. Alleen de bestaande documentbrede helpers sneller maken en resultaten binnen
   één berekening delen. Klein compatibiliteitsoppervlak; nuttig voor het
   werkbord, maar passageklik, formulieromvang en contextkeuze blijven afhankelijk
   van het hele document. Dit voldoet niet als zelfstandig detailontwerp.
2. Het werkbord laat aantallen en revieweracties uit dezelfde reviewplichten
   volgen. Het detail krijgt een gericht, operationeel leespakket uit de bestaande
   PG-store: geselecteerde passage, noodzakelijke relatie-/contextburen,
   reviewbindings en actuele documentrevisie. Aanvullende context is expliciet
   bereikbaar via begrensde selectie. Een compacte formulierverwijzing wordt vóór
   opslaan gecontroleerd en vertaald naar de bestaande objectsetrevisie; de
   commandkernel doet daarna zijn bestaande controles.

Gekozen: alternatief 2, met behoud van de bestaande documentbrede renderroute
voor historie, expliciete documenttaken en conflictherstel. Geen nieuw
statusregister, reviewengine, tussen-verzoeken-cache of duurzame projectie.
De gebruiker heeft implementatie van beide oplossingen rechtstreeks opgedragen.

## Gebruik, gegevens en toegangspatronen

- Werkbord: één actuele plichtprojectie per zichtbaar document; exacte totalen
  blijven behouden. Filtering/paginering mag geen open werk of leesfout verbergen.
- Detail: één geselecteerde objectidentiteit, bronrepresentatie en noodzakelijke
  context/relaties. Een index op objectidentiteit ondersteunt gericht selecteren;
  contextverbindingen mogen een groter noodzakelijk pakket opleveren.
- Opslaan: identiteit, actuele bevoegdheid, objectversie, bindings, bronbewijs en
  onafhankelijkheid worden opnieuw door de bestaande commandkernel gecontroleerd.
- Alleen tijdelijke, operatiegebonden leeswaarden veranderen. Duurzame objecten,
  kandidaatidentiteit, bronmapping, reviewbesluiten, publicatie en serving niet.

## Rewrite-mitigatie

Rewrite target: uitsluitend de Review-leesprojectie en de invoeradapter voor haar
formulier-revisieverwijzing; geen review-/publicatiekernel vervangen.

Why local patching is insufficient: hergebruik van volledige documentlezingen
neemt de afhankelijkheid tussen één passage en alle documentobjecten niet weg.

Current authority/writer/reader map: `workflow.document_objects` en
`workflow.documents.revision` via de bestaande documentstore/write_bundle;
reviewbindings via de reviewstore; menselijke commands via de bestaande kernel.
Lezers: Review GET, werkbord, bestaande historie/conflictrenderer. Geen externe
writer krijgt nieuwe bevoegdheden.

Supported runtime topologies: beide ondersteunde volledige PostgreSQL-productie-
composities; pure projectietestconsoles behouden de bestaande renderer.

Persisted-state impact: migratie 024 voegt een afgeleide GIN-index
op de bestaande objectpayload toe voor relatie-/contextprobes en een B-tree-index
op documentidentiteit/eventvolgorde voor de gerichte historie. Geen nieuwe
kolommen, backfill, herschreven objecten of nieuwe autoriteit. De bestaande
documentrevisie wordt alleen gelezen. De index kost opslag en onderhoud bij
objectwrites; dat wordt met de bestaande native commandproeven getoetst.

Compatibility/migration plan: additief gericht detailpakket; bestaande
objectsettokens blijven geldig. Nieuwe formulieren lopen via een smalle adapter
terug naar bestaande commandinvoer. Geen dual-write of gegevensmigratie. Eerst
de additieve index installeren met de bestaande migratieprocedure, daarna pas
de passagegerichte code activeren; oude binaries blijven met die index werken.

De formulierverwijzing bindt documentidentiteit aan zowel `revision` als
`object_generation`. De generatietrigger uit migratie 021 geldt uitsluitend voor
task-storage; bij legacyopslag blijft de bestaande write_bundle-documentrevisie
nodig. Er wordt dus geen algemene triggerdekking verondersteld. Vertaling naar
het oude objectsettoken gebeurt vanuit één herhaalbare leessnapshot; de kernel
blijft daarna controleren op wijzigingen die ná die snapshot plaatsvinden.
Ook uitsluitend gewijzigde documentmetadata kan nu een formulier laten vervallen.

Rollback/recovery plan: code terugdraaien en open formulieren opnieuw laden.
Geen dataherstel nodig; tokens zijn tijdelijke formulierwaarden. Een oude binary
hoeft een nieuw compact formulier niet te accepteren.
De index mag blijven staan bij een rollback en kan later afzonderlijk verwijderd
worden; bestaande domeinwaarden en schrijvers veranderen niet.

Cutover trigger: gerichte lees-, pariteits-, autorisatie- en stale-proeven groen;
dezelfde 3.000-passagesproef opnieuw uitvoeren. Geen merge of deployment in deze
opdracht.

Cleanup/decommission criteria: geen tijdelijke debuglogs of prototypes in src;
alleen de bestaande documentbrede route voor de expliciete taken die haar nodig
hebben. Geen concurrerende plichtberekeningen voor hetzelfde werkbordresultaat.

Failure blast radius: onjuist detailpakket kan context of acties verkeerd tonen;
onjuiste formuliervertaling kan stale invoer accepteren. Beide moeten fail-closed
zijn en mogen de commandkernel nooit omzeilen.

Adversarial proof matrix: verkeerde documentidentiteit; onbekend/vervangen object;
verwijderde reviewer; gewijzigde rol; object-, binding- en contextwijziging tussen
GET en POST; ontbrekende/stale bron; eerste/tweede reviewer; andere schrijfroutes;
oude tokens; nieuwe processtart; PG-leesfout; vergelijkbare tekst uit ander document.

## Implement / Scrap — volgorde en bewijs

Eerst aantoonbaar dubbel werk verwijderen, daarna alleen de ontbrekende gerichte
storelezing en formulieradapter toevoegen. Geen generieke infrastructuur bouwen.
Behoud bestaande autoriteiten en brondragers. Herontwerp als hiervoor een tweede
authority, gewijzigde lifecycle of onafhankelijke validatieregels nodig blijken.
Een geslaagde build of groene correctheidstest bewijst geen prestatiedoel.

## Adversarial review — dezelfde auteur

De eindcontrole is een afzonderlijke code- en tegenproefronde, geen claim van
een onafhankelijke reviewer. De belangrijkste gecontroleerde grenzen:

- De contextkeuzelijst is gepagineerd; noodzakelijke context en inkomende en
  uitgaande relaties volgen zelfstandig de afhankelijkheden. Een native proef
  met dertig gekoppelde doelen controleert dat de grens van 25 keuzeteksten
  geen vereiste context afkapt en vergelijkt bronverantwoording met de volledige
  documentprojectie.
- De bronselectie gebruikt uitsluitend aantoonbaar zelfstandige, afgesloten
  bronfragmenten. Bij samengestelde zinnen, onbekende blokken of ontbrekende
  verwijzingen blijft de volledige bestaande bronrepresentatie gelden. Exacte
  brontoetsen worden differentieel vergeleken; extractiemetadata blijft behouden.
- De compacte revisie is geen bevoegdheid. Werkelijke HTTP-commands weigeren
  stale invoer, ongeldige/verkeerde documenttokens en een ingetrokken reviewerrol
  zonder object- of eventmutatie. Een tijdelijke in-memory mutatie die uitsluitend
  de generatievergelijking verwijdert laat de stale-test aantoonbaar falen
  (303 in plaats van 409); de normale code doorstaat dezelfde proef.
- Een onbekend document behoudt de bestaande foutcode. Een noodzakelijke
  PostgreSQL-leesfout wordt doorgegeven en levert geen leeg werkbord of positieve
  reviewbeslissing op. Geen nieuwe foutstatus of stille degradatie ingevoerd.
- Geen willekeurige nieuwe broncache: de bestaande immutable broncarrier deelt
  identieke views en de maximaal 36 vaste viewdoorsneden binnen één voorbereiding.
  Hashvergelijking blijft exact; zonder een mogelijk passende goedkeuringsbinding
  is geen canonieke reviewhash nodig.

De native regressieronden omvatten werkbordplichten/acties, eerste/tweede
reviewer, wachten op een collega, batch-atomiciteit, stale UX, broncontext,
bronhergebruik en de bestaande karakteriseringsschermen. Architectuurgrenzen,
change-contractvalidatie, repository-preflight en release-control-preflight
worden afzonderlijk gecontroleerd. Lokale ASGI HTTP-metingen omvatten de volledige
respons na authenticatie, steeds bij de eerste Review GET in een nieuw proces.
De fixture bevat 3.000 kandidaten; begin, midden en einde worden herhaald gemeten.
Dit is geen browser- of Azure-acceptatie, en bewijst niet de oorzaak van de
eerder gemelde 46 seconden in productie. Die metingen staan nog open.

## Lokale einduitkomst — 25 oktober 2026

Zelfde PostgreSQL 16-fixture met 3.000 kandidaten; Python 3.12. Nieuwe processen,
eerste geauthenticeerde Review GET, volledige ASGI HTTP-respons. Opstarten en
inloggen vallen buiten de responstijd; dit is geen koude PostgreSQL-bufferproef.
Fixture-identiteiten worden vóór de timer bepaald en worden niet als leesinputs
aan de productie-GET meegegeven.

| Weergave | Herhalingen | Eindmeting |
| --- | ---: | --- |
| Werkbord | 3 | HTTP 200, 5,407–6,908 s |
| Geselecteerd documentwerkbord | 1 | HTTP 200, 4,850 s |
| Passagedetail begin | 3 | HTTP 200, 0,290–0,546 s |
| Passagedetail midden | 3 | HTTP 200, 0,313–0,345 s |
| Passagedetail einde | 3 | HTTP 200, 0,279–0,456 s |
| Expliciete documentbrede individuele wachtrij | 1 | timeout na 20,006 s |

De lokale passagegrens is op deze fixture behaald. Het werkbord berekent iedere
actuele kandidaatplicht eenmaal (eerder zesmaal), verrijkt uitsluitend de gekozen
pagina en leest uitsluitend relevante events. De expliciete documentbrede
individuele wachtrij gebruikt de bestaande renderer en blijft een open
prestatieprobleem; deze implementatie claimt geen algemene subsecond-Review.

Gerichte native PostgreSQL- en karakteriseringsronden zijn uitgevoerd. De brede
ronden leverden respectievelijk 94 en 104 geslaagde tests op, naast aanvankelijk
falende controles die daarna gericht zijn herhaald: bestaande foutstatus,
bronhergebruik bij batchweergave en de parameterloze bindingslezer. Die controles
zijn na herstel groen. De laatste bron-/architectuurronde telt 37 geslaagde tests;
de laatste afhankelijkheidsronde drie, inclusief dertig contextdoelen en
inkomende/uitgaande relaties buiten de keuzepagina. Geen PostgreSQL-skip als
geslaagd bewijs gebruikt; geen claim dat de volledige repositorysuite is gedraaid.

Lokaal bewijs staat in `work/review-acceptance-benchmark.json` en de bijbehorende
`work/review-*.log`-bestanden. De oorspronkelijke rode metingen zijn behouden in
`work/review-before-implementation/`. Geen merge of deployment uitgevoerd.
Voor uitrol eerst migratie 024 installeren en vervolgens Azure-responstijd en
browserbruikbaarheid met een afzonderlijk overeengekomen acceptatiegrens toetsen.

## Integratie voor de PR

Bij het maken van de PR is main `53f7551` opgehaald en is de implementatie
daarop gerebased. De tabel hierboven betreft de eerdere, vastgelegde basis;
deze cijfers worden niet als een nieuwe volledige meting na integratie gepresenteerd.
Het blijvend leesbare meetverslag staat in
`evidence/review-read-performance/verification.json`.

De integratie behoudt de waarschuwing en link naar Vormingsproblemen uit #848,
ook als al onafhankelijke kandidaten bestaan. De compacte documentlezing gebruikt
alleen een negatieve voorselectie: opgeslagen open vorming, onzekere taakstatus
of ontbrekende activatie laat de bestaande volledige `processing_status`- en
bronafsluitingscontrole draaien. Een beperkte passageset bewijst dus nooit dat
een gedeeltelijk document compleet is. Deze gedeeltelijke/onzekere gevallen
kunnen documentbreed werk blijven vereisen; de prestatieproef bewijst dat pad niet.

Na integratie: **99 passed, 1 skipped** in de gerichte native PostgreSQL-,
Review-, bronhergebruik-, architectuur- en karakteriseringsronde. De ene skip is
de expliciete Chromium/Playwright-proef zonder browserconfiguratie, geen
PostgreSQL-skip. De aangescherpte bannerassertie is daarna afzonderlijk groen
(1 passed). Drie aanvullende passagemetingen in nieuwe processen op de
gecombineerde productiecode: begin **0,494 s**, midden **0,526 s**, einde
**0,371 s**, alle HTTP 200.

Repository-preflight, release-control-preflight tegen `origin/main`, compileall,
architectuurgrenzen en change-contractvalidatie slagen. De volledige suite op
de oude basis is vóór uitvoering onderbroken om de nieuwe main te integreren;
een volledige suite op de uiteindelijke PR-head blijft open. De PR wordt daarom
als concept aangeboden, met menselijke review en definitieve CI als verdere
voorwaarden. Geen claim van volledige merge-/releasegereedheid.
