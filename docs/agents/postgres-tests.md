# PostgreSQL voor consoletests (D6a)

Change class: C
Promise: één gedeelde PostgreSQL-testopstelling en productiegetrouwe consolefabrieken, met migratie in porties.
Proof: geïsoleerde databases, dezelfde ASGI-klassen/routes, falen bij verzamelen zonder beschikbare PostgreSQL, en gemeten suites.
Touches lifecycle invariants: no
Rewrite risk: none

Dit is de eerste portie van D6a. De bestandsopstelling blijft bestaan tot D6b;
deze portie sluit D6a niet af. B-D6-1 vervangt de eerdere HOLD op PostgreSQL
voor lokaal ontwikkelen en testen. #695 blijft onafhankelijk en gaat voor bij
capaciteitsgebrek. GNC begint pas na D6b.

## Starten

Activeer de Python-omgeving met `requirements-dev.lock`. `pytest` roept
`scripts/test_postgres.sh` tijdens het verzamelen aan zodra consoletests of
PG-tests geselecteerd zijn. Een bereikbare `METIS_TEST_POSTGRES_DSN` wordt
hergebruikt; de testrol moet `CREATEDB` hebben. Anders start het script een
wegwerpserver uit PostgreSQL 16, op een vrije loopbackpoort. Als dat niet kan,
stopt verzamelen met één fout. Ontbrekende PG-evidence wordt niet overgeslagen.

```bash
export PGBIN=/usr/lib/postgresql/16/bin
export PATH="$PGBIN:$PATH"
python -m pytest -q tests/test_pg_console_without_disk_mirrors.py
```

`PGBIN` kan naar een andere installatie van PostgreSQL 16 wijzen. De client
`psql` moet ook in `PATH` staan voor de bestaande SQL-schadeproeven. Een pure
testselectie zonder console kan zonder database draaien. In gemengde modules
markeert `pure_function` zulke gevallen; `file_topology` markeert uitsluitend
bestandsgedrag dat in D6b vervalt. Deze markeringen omzeilen geen expliciet
aangevraagde PG-fixture.

Het script schrijft alleen de DSN naar stdout. Wie de server handmatig wil
starten, gebruikt `export METIS_TEST_POSTGRES_DSN="$(scripts/test_postgres.sh)"`.
Stderr noemt het eigen statusbestand en het bijbehorende `--stop`-commando.
Pytest ruimt een zelf gestarte server automatisch op; een opgegeven server
blijft draaien. Als root start het script de server als `postgres`, of als
`nobody` wanneer die eerste gebruiker ontbreekt.

## Agentomgevingen

Gebruik tijdens setup op Ubuntu 24.04 `bash scripts/setup_test_environment.sh`.
Dit installeert PostgreSQL 16, de client en de Python-afhankelijkheden. Het
blokkeert het starten van services door pakketinstallatie; de testserver start
pas in de agentfase. Als PostgreSQL ontbreekt, gebruikt setup rootrechten of
wachtwoordloze `sudo` voor APT; Python-pakketten blijven onder de aanroeper.

- Codex: stel het setupcommando in en zet `PGBIN=/usr/lib/postgresql/16/bin`
  als blijvende omgevingsvariabele in de omgevingsconfiguratie. Een `export`
  binnen setup blijft niet beschikbaar in de agentfase. Deze repo kan de
  gebruikersinstelling van de Codex-omgeving niet vervangen.
- Cursor lokaal: installeer PostgreSQL 16, of gebruik `postgres:16` met een
  bereikbare DSN en `CREATEDB`-rechten. Bij een Docker-server hergebruikt het
  script die DSN; het script zelf start geen Docker-container.
- Cursor cloud: `.cursor/environment.json` gebruikt hetzelfde setupscript.
  Gebruik een Ubuntu 24.04-omgeving met Python 3.12/3.13. Zonder expliciet
  `PGBIN` vindt het startscript de standaard apt-installatie van versie 16.

Voer in iedere gebruikte omgeving de D4/D5-proef hierboven uit en registreer
de uitslag afzonderlijk. Een Codex-run bewijst geen werking in Cursor.

## Fixtures en porties

`postgres_template` bouwt het volledige schema eenmaal per pytest-sessie.
`complete_postgres` maakt per test een eigen database met `CREATE DATABASE …
TEMPLATE …` en verwijdert alleen die eigen database. De aangeboden DSN wordt
nooit gereset door deze fixture. Onafhankelijke verbindingen, subprocessen,
commits en herstarts blijven echte PostgreSQL-operaties. Legacy-fixtures die
zelf schema's resetten worden in volgende porties vervangen.

`production_console(...)` roept werkelijk `console_asgi.build_app()` aan, met
de vijf PG-stores, startupreconciliatie en de productieklasse. Gebruik
`azure=True` met een Blob-testadapter voor de Azure-variant. De optionele
`processing_binder` vervangt uitsluitend de modelprovider voor een test.
`production_app(console)` gebruikt dezelfde route-installatie als ASGI.
Store-doubles worden niet door deze factories geaccepteerd.

De eerste portie migreert console-ASGI, workspace, instellingen, uploadnamen,
navigatie, kopbevestiging en de HTTP-helper voor de batchproef. De leestest
selecteert nu de echte reviewkamer (`task=individual`); de vervangende
productieroute gebruikt dezelfde bestaande leesscope als de basisroute.
De HTML-equivalentie en authenticatie blijven onderdeel van het bewijs.
Vier expliciete lokale bestandsgevallen zijn gemarkeerd; de volledige
`file_topology`-inventaris volgt met de resterende porties.

## Meten

```bash
python scripts/benchmark_test_database.py
python scripts/measure_test_suite.py --ref 9fa2004 --output output/d6a-before.json
python scripts/measure_test_suite.py --output output/d6a-after.json --compare output/d6a-before.json
```

Gebruik dezelfde Python-afhankelijkheden, PG-server, runner en lege
testdatabase per suite. De baseline draait in een ongewijzigde Git-worktree;
de metingen draaien na elkaar. JSON bevat de tijd en uitslag; naastliggende
JUnit-XML bevat uitgevoerde tests. PG-skips en een verhouding boven twee
laten de meetopdracht falen. Browser-/Docling-/Bend-uitzonderingen blijven
zichtbaar in XML en worden niet als uitgevoerd bewijs geteld.

CI bewaart de metingen als `suite-timing-*`. Op `codex/d6a*`-PR's meet Python
3.13 eerst de vaste baseline; beide Python-versies meten vervolgens de suite.
Een lokale tijdmeting is geen CI-resultaat. D6b wacht op volledige migratie,
acceptabele CI-looptijd, omgevingsbewijs en de voorgeschreven reviewronde.

## Vervolgporties (lokaal)

Portie 2 vervangt schema-resetfixtures en isoleert ook de afnemers die eerder
stilzwijgend op zo'n reset door een andere module vertrouwden. De aanvullende
publicatie-, successor- en intrekproeven houden hun eigen database.
De tijdens de migratie gevonden directe accountmap-lookup is als afzonderlijke
Class B-reparatie beschreven in
[de lezersreparatie](../change-contracts/d6a-reader-authority.md).

Portie 4 migreert elf pagina-/opslagmodules (128 bestaande gevallen).
Drie expliciete proeven van de lokale JSON-schrijver blijven `file_topology`.
PG-concurrency toetst conflicterende writes op hetzelfde object; de bestaande
PG-store mag onafhankelijke objectwijzigingen samenvoegen.

Portie 5 migreert twaalf oudere ingest-/document-/reviewmodules (257 bestaande
gevallen). Gepubliceerd werk wordt in de fixture met de bestaande canonical
PG-seed vastgelegd, zodat de seal van PostgreSQL komt. De productieworkboard-knop,
de vereenvoudigde parentkeuze en de compacte publicatiepagina vervangen oude
presentatieverwachtingen van de kale basisapp. Publicatiepagina's worden met
een bevoegde publisher gelezen; de bestaande kernelblokkades blijven getoetst.
Twee bestandsspecifieke gevallen blijven `file_topology`. Er zijn geen
productieregels aangepast om deze tests groen te maken.

De JUnit-bronnen en aantallen staan in `evidence/d6a/batches.json`. Een reeks
lokale herhalingen wordt daar onderscheiden van één foutloze volledige run.
De overige porties, CI-metingen, Cursor-bewijs en de D6b-voorwaarden zijn nog open.

Portie 6 verplaatst de native beslisboomhelper naar de gedeelde fixture en echte
ASGI-start. Een geïnjecteerde canonical store moet exact de productie-PG-store
voor dezelfde testdatabase zijn; twee negatieve gevallen weigeren een double
of andere database. Ook de laatste oude `pytest.skip`-tak voor een ontbrekende
PG-DSN is verwijderd. Migratietests bouwen hun oude schema uitsluitend binnen
hun eigen gekloonde database op.

De A09-foutproeven controleren eerst exacte PG-rijen en ledger vóór startup.
Een echte startup mag de bestaande legacy-`revise`-migratie uitvoeren: oude
canonical tuples blijven behouden en alleen de benoemde `clear repair context`-
opvolger met dezelfde bron/inhoud wordt toegestaan. De autorisatie-race start
zijn tweede worker vóór de legacy fixture, zodat alleen de rolwijziging tijdens
de voorbereiding plaatsvindt. Deze aanpassingen veranderen geen runtimecode.

Portie 7 migreert broncontext-, lineage-, closed-loop- en HTTP-leesproeven.
Fixture-aliassen delen één onderliggende geïsoleerde database per test; een
extra onafhankelijke identity-reader bewijst dat zij dezelfde authority zien.
De source-selection-kostproef instrumenteert echte PG-methoden en schrijft
concurrente wijzigingen via een onafhankelijke PG-store. Geen opslagdouble of
vervangende consoleklasse is daarvoor nodig. De productiemiddleware wordt
precies eenmaal gebruikt.

Closed-loop-unitproeven roepen expliciet de bestaande owner-methode aan op de
productieconsole, waar zij historische ongestructureerde `revise`-records nodig
hebben. Dit is owner-unitbewijs; het is geen claim dat de bovenliggende
structured-repair-router die legacy opdracht accepteert. De HTTP-negatiefproef
gebruikt na het klaarzetten van zo'n historisch record de echte productieroutes.
Twee T11-proeven van dubbele exacte tupleversies in een JSON-bestand blijven
`file_topology`; PostgreSQL weigert die representatie via zijn primary key.
De semantische publicatie-sealproef controleert nu canonical PG-rijen.

De aanvullende portievergelijking is reproduceerbaar met
`python scripts/benchmark_console_fixture.py --ref <commit> --output <pad>`.
Zij draait dezelfde zeven modules (37 gevallen) in een tijdelijke worktree.
Een buitenste rollbacktransactie gebruikt de bestaande workflow-binding;
onafhankelijke verbindingen en canonical commits worden niet vervalst.
De resultaten staan in `evidence/d6a/fixture-portion-benchmark.json`: template
37/37 in 15,171 s; rollback 31/37 in 9,139 s. Onder andere de echte
reprocessing-owner- en HTTP-proeven falen bij rollback. Een kortere looptijd
van een falende strategie telt niet als versnelling; databasekopieën blijven
het gekozen mechanisme. Een eerdere proef met een verkeerde psycopg-row-factory
is verworpen en niet als bewijs opgenomen.

Portie 8 repareert de bij de migratie gevonden volledige receiptconstructie
binnen de PG-sleutellijst. De Class B-scope staat in
[het leescontract](../change-contracts/d6a-key-list.md); het pad schrijft niets.

Portie 9 migreert bronbewijs, broncacheherstel, formulierconflicten en
formatieproeven. Formulierconflicten gebruiken een echte definitieve afwijzing
als concurrerende write: `later` bewaart in de productieklasse bewust geen
suitability. De incomplete-formatie-banner wordt in de daadwerkelijke
reviewkamer gelezen (`task=individual`), naast de gewone workboardroute.
De semantische safety-proef injecteert provider/commitbewijs vóór de echte
route-installatie. Canonical publicatie bij herstel gebruikt PostgreSQL.

Afnemers van de formatiehelper krijgen expliciet dezelfde factory mee. Oudere
parametrische helpers die nog niet in deze portie worden gemigreerd, blijven
zichtbaar in de inventaris; dit is geen afronding van D6a. De afzonderlijke
publication-refusal-module bewaart tijdelijk expliciet haar bestaande
bestandsconstructor, zodat een helperwijziging haar oude bewijs niet stilzwijgend
naar een andere opstelling omzet.

Portie 10 migreert receipt-/dispatch-/autorisatie-/trace- en A04-sessieproeven.
De gedeelde testcompositie kan expliciete omgevingsconfiguratie ontvangen,
zodat de Entra-sessieproef via `build_app()` zelf wordt geïnstalleerd.
Een herstart bouwt via dezelfde factory een nieuwe app/console boven dezelfde
PG-authority. De door de factory gemaakte app hoort bij de console; helpers
installeren geen tweede middlewarelaag meer. Een tweede ASGI-lifespan krijgt
expliciet een nieuwe compositie, zoals een echte procesherstart.

Blob-herstel, gelijktijdige receipts en orphan-herstel gebruiken de echte
Azure-productieklasse met alleen Blob als transportfixture. De fork/spawn-
crashproef bouwt in het kindproces dezelfde productiecompositie. Bestaande
barrières, onafhankelijke SQL-lezers, intrekkingen, sessieverval en het bewijs
van behouden checkpoints blijven onderdeel van de portie.

De bronselectie-browserfixture gebruikt ook deze fabriek. Haar proces bezit
zijn eigen wegwerpdatabase en ruimt die bij afsluiten op. Zij gebruikt hetzelfde
startscript als pytest; er wordt geen aangeboden database gereset. Een lokale
geauthenticeerde HTTP-proef is uitgevoerd; een volledige browser- of Cursor-run
wordt daarmee niet geclaimd.

Portie 11 verwijdert de tweede samenstelling uit `complete_console`: ook die
legacy testsignatuur roept nu de gedeelde productie-ASGI-fabriek aan. Alleen de
twee ondersteunde FastBadge-PG-klassen zijn toegestaan. Bestaande model-/Blob-
fixtures blijven transportinjecties. A03 en de native publicatieproef gebruiken
canonical PostgreSQL; persist-tellers observeren de echte adapter en release-ID's
worden uit PostgreSQL gelezen. De parallelle canonical-geheugenstore in die
native publicatieproef is verwijderd.

De D4/D5-gifproef, twee workerprocessen, backup/herstel en rollback blijven
deel van het bewijs. Bij procesafbreking wordt de exacte PG-baseline na de echte
startup en vóór het commando vastgelegd. Tussen de ouder en die startup mogen
uitsluitend bestaande document-revisietellers/tijdstempels veranderen; alle
domeinpayloads blijven exact gelijk. Voor de afgebroken opdracht worden vervolgens
alle tabellen inclusief die tellers exact vergeleken. De rollback-child voert
startupreconciliatie eenmaal uit: via de huidige factory of expliciet bij de
gepinde oude code die die factory nog niet kende.

Portie 12 migreert de broncontext-commandoproef, volledige A15-navigatie,
occurrence-relaties, strength-binding en de consolegevallen in de
pre-review-semantic-module. De geïsoleerde catalogusprobe instrumenteert de
echte productieklasse in plaats van een tweede consoleklasse te construeren.
A06 leest ook in zijn onafhankelijke subprocess uit dezelfde PG-database.
Een synthetic binding voor de heading-regressie bevat nu de verplichte
reviewer-displaynaam van de bestaande PG-store.

De broncontext-browserfixture gebruikt de gedeelde procesfixture en
productie-ASGI-app; geauthenticeerde HTTP-navigatie is lokaal getoetst.
De echte Docling-acceptancemodule is eveneens omgezet, maar de twaalf bestaande
acceptancegevallen blijven zichtbaar overgeslagen zolang de officiële
ML-omgeving niet is ingeschakeld. Dat is geen uitgevoerd Docling-bewijs en geen
PG-skip; normale consoletests blijven zonder PostgreSQL falen.

Portie 13 migreert Home/navigatie, Entra, review-interactie-evidence,
Inzicht/kwaliteit en consoletelemetrie. Expliciete HTTP-configuratie loopt via
dezelfde `build_console_app`-installatie op de reeds door de factory gemaakte
PG-console. Entra gebruikt echte accounts/sessies; alleen de externe Microsoft-
uitwisseling of een expliciete uitvalgrens wordt geïnjecteerd.

De navigatieproef volgt de bestaande productievereenvoudiging: het merklinkje
brengt de gebruiker naar Home, Home heeft de procestegels en de overige pagina's
behouden de werkruimtenavigatie. Publicatie blijft voor de gewone researcher
geweigerd; een bestaande aparte publisher-proef leest die route wel. Lock- en
telemetrieproeven voegen alleen hun probe-endpoint toe aan de echte app en
installeren de diagnostiek niet nogmaals.

De expliciete weigering van Entra op een bestandsconsole en de observability-
proef van de oude `serve-console`-CLI zijn `file_topology`: beide oude starts
verdwijnen in D6b. De Entra- en uitgeversrechten zijn niet gewijzigd.

Een nieuwe lokale run van de ongewijzigde baseline `9fa2004` is volledig groen:
5.641 passed, 27 gewone skips, 6 xfails, nul PG-skips, 1.043,807 s. Dezelfde
synthetische DNS-hostnamen staan nu in `NO_PROXY` als in de latere portieruns.
`evidence/d6a/local-baseline-clean.json` bewaart deze meting; de eerste meting
met drie proxyfouten blijft als historisch bewijs beschikbaar. Dit is een
herhaalmeting van oude code, uitgevoerd ná de eerste porties, geen achteraf
geclaimde CI-run vóór de migratie.

Portie 14 migreert de publicatie-/workboardmodules en hun afnemers. Intrekking
publiceert eerst echt naar PostgreSQL, gebruikt de echte withdrawal-transactie
en controleert teller/idempotentie als observatie van die adapter. Supersession
wordt met een echte successor, review en publicatie voorbereid; de historische
kaart verliest haar formulieren terwijl de actieve opvolger haar eigen kaart
houdt. Het legacy-geval bereidt expliciet pre-lineage-metadata in de eigen
wegwerpdatabase voor.

De bestaande PG-lijstproef verbiedt `ready_for_publication` als lijstbelofte
zonder volledige gereedheidscontrole. De overgezette UI-proef volgt datzelfde
contract: lijsten blijven conservatief, de gekozen publicatiepagina toetst
actuele gereedheid en Blob-beschikbaarheid, canonical publicatiestatus blijft
gedeeld. Geen runtime-statusregel is aangepast.

De geïntegreerde MCP-proef leest accountrollen en blokkades nu eveneens uit
PostgreSQL; alleen de ondertekende JWT/JWKS-transportfixture blijft gecontroleerd.
Gehardcodeerd lege canonical stores en extra route-installaties zijn verwijderd.


Portie 15 zet de beslisboom-, participatie-, heading-batch- en bronreparatieproeven
over op dezelfde productiecompositie. Ook de zelfstandige kenniscontext-browserfixture
gebruikt PostgreSQL; een aangemelde HTTP-proef opent de kenniskaart en beslisboompaden.
De oude fixturevarianten blijven als afzonderlijke cases bestaan, maar delen nu
dezelfde PG-authority. De Azure-bronreparatieproeven houden alleen het Blob-transport
synthetisch en gebruiken de echte AzureBlobSourceStore en Azure-consoleklasse.

Grafpublicatie, herstart en intrekking gebruiken de echte canonical adapter. De
vervalsingsproef wijzigt uitsluitend de eigen PG-auditfixture en controleert nog
steeds tekst, span, grafmodus en reviewbewijs. Accountmutaties gebruiken de
identity store en de bestaande retirement-operatie. Pure controles op de drie
onbeschikbaarheidsvlaggen blijven afzonderlijke functieproeven. De familie/klasse-
projectie wordt expliciet bij haar bestaande owner geïsoleerd; de productiepoort
blijft daarnaast ongereviewde objecten weren.

Een geweigerd heading-commando moet vóór herstart alle zes statecomponenten exact
behouden. Alleen de reeds bestaande startup-reconciliatie van een expliciet
voorbereide historische publicatie mag daarna de opslagrevision één verhogen;
de objecten, envelope, bindings, objectrevision en events blijven exact gelijk.

De volledige lokale herhaalmeting van portie 3 op de vastgepinde commit is groen:
5.647 passed, 27 niet-PG skips, 6 xfails, nul PG-skips, 1.061,821 seconden. Dat
blijft binnen tweemaal beide vastgelegde baselines. De JSON behoudt de oorspronkelijke
vergelijking met de eerste lokale baseline. CI blijft afzonderlijk vereist.

Portie 15: 296 unieke cases groen (220 + 76), inclusief drie aanvullende pure
vlagproeven; geen skips. De T12-proef toetst zowel de productie-dispatch als de
bestaande basisowner op dezelfde PG-console.

Portie 16 zet de aanbevelings-/relatiebevestiging, reserveringsconfiguratie,
replay, diagnostiek en oudere kernelproeven over. 270 unieke cases zijn groen,
zonder skips. De hergebruikte diagnostiekproeven gebruiken nu de productieklasse
in plaats van de oude bestandsadapter. De ongewijzigde twee JSON-historyproeven
blijven expliciet `file_topology`; hun dubbele objecttuples zijn geen ondersteund
PG-schema. De blocked-candidate UI-proef meldt de daadwerkelijk aangewezen reviewer
aan, zodat de productiepoort de juiste werkpagina toont.

Portie 17 vervangt de geheugenautoriteit van publicatiebewijs, refusal-audit,
Blob-verificatie en de centrale review-seal door PostgreSQL. 101 unieke cases
zijn groen, inclusief één nieuwe isolatieproef; geen skips. De observatieproef
vergelijkt alle geëxporteerde recovery-tabellen exact vóór en na het lezen,
inclusief workflow-, identity-, canonical- en API-accessgegevens. De gekozen
release-itemslezer wordt bij een registry-outage gericht onderbroken.

Bestandskopie, manifests en refusal-bestandsrotatie blijven uitsluitend als
`file_topology` bewaard. Gedeelde fixturevoorbereiding voorkomt een tweede
review-/ingestopzet. De Azure-proeven lezen echte PG-release-/registryrijen
en gebruiken de Azure-productieklasse; alleen bron-IO is gecontroleerd.

`production_console(isolated=True)` maakt expliciet een extra sjabloonkopie
voor proeven die twee onafhankelijke situaties vergelijken. De gewone factory
blijft dezelfde database delen voor herstart/workerproeven. Een echte login,
dezelfde accountnaam in beide databases en herstart bewijzen de isolatie.

De ontbrekende factorydoorgifte van de replay-reserveringsafnemer is teruggelegd
in portie 9 (`fe3b288`) en daar groen uitgevoerd; porties 10–16 zijn daarop
gebaseerd. Hun oorspronkelijke loghashes blijven het historische gerichte bewijs.

Portie 18 migreert de oudere admission-/cockpit-/coveragepagina's, de oorspronkelijke
consoleproeven en reviewreparatie. Alle 167 bestaande cases blijven aanwezig;
één pure proef bewaart het compatibility-hashcontract. 168 unieke cases zijn
groen, zonder skips. De telling vergelijkt de oorspronkelijke node-ID's met de
nieuwe namen en herstelt de onbedoeld weggevallen sectiecoverageproef.

De productiepagina heeft één brondeur en een kopkeuze zonder navigatielinks;
de proef volgt die bestaande route-installaties. Uitstel bewaart geen nieuw
reviewbesluit of kopkeuze. De registermapping wordt bij haar bestaande pure owner
gecontroleerd, naast het bewijs dat een uitgestelde review geen objecten schrijft.
Daadwerkelijke correcties gebruiken de bestaande brongebonden repair-operatie.

De raceproeven gebruiken twee echte PG-instanties: de concurrent wacht op de
atomaire batch en verliest met de verouderde revision. De hele batch is dan
opgeslagen; een expliciete nieuwe poging op de actuele revision slaagt en
invalideert uitsluitend het betrokken bindingsbewijs. Er wordt geen gedeeltelijke
bestandsschrijfuitkomst als PG-gedrag aangenomen.

Vijf proeven op atomische JSON-writers blijven `file_topology`. De lege-rollen-
fixture is vervangen door de bestaande PG-weigering van zo'n account; een engineer
krijgt daarmee nog steeds geen alternatieve ingestroute. De URL-transportstub wordt
vóór de productiecompositie geplaatst, zodat de echte downloadlimiet actief blijft.

Deze Class C-portie bouwt op de afzonderlijke Class A-reparatie `a7516ef`, beschreven
in `docs/change-contracts/pg-command-review-evidence.md`: een gestructureerde
onderbouwingsreparatie moet haar eigen voorbereide PG-auditbewijs kunnen lezen.
De publieke audit blijft gecommitteerde toestand lezen. De dedicated HTTP-,
rollback-, herstart- en D5-gifproeven van die reparatie zijn afzonderlijk vastgelegd.

Volledige lokale metingen van de herstelde porties 5 en 6 zijn groen: respectievelijk
1.169,733 en 1.268,878 seconden, nul PG-skips, 1,1206× en 1,2156× de schone baseline.
