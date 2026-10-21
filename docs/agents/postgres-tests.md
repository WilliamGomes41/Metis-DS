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
