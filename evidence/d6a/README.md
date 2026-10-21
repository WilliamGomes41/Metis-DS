# D6a, eerste portie — uitvoeringsbewijs

Basis: `9fa2004`. Change class: C. Rewrite risk: none.
Dit beschrijft de eerste portie; D6a en D6b zijn niet gereed.

## Volledige lokale suites

| Meting | Tijd | Groen | Fouten | PG-skips |
| --- | ---: | ---: | ---: | ---: |
| Ongewijzigd `9fa2004` | 1096,328 s | 5638 | 3 | 0 |
| D6a `1be5852` | 1085,310 s | 5643 | 3 | 0 |

Verhouding: **0,9899**, binnen de grens van twee keer de baseline. Beide runs
gebruiken PostgreSQL 16.15 en Python 3.13.5, dezelfde server en afhankelijkheden,
een eigen lege database per suite, en draaien na elkaar. Beide hebben dezelfde
27 optionele skips en 6 bestaande xfails buiten het PG-bewijs. De vijf nieuwe
infrastructuurgevallen verklaren het verschil in het aantal groene tests.

De drie falende tests zijn op beide revisies dezelfde SSRF-proeven uit
`test_security_harden_wave3.py`: HTTPS-SNI bij DNS-rebinding, opnieuw valideren
van een redirect, en het weigeren van een redirect naar metadata. De volledige
lokale suite is dus niet foutvrij; er zijn geen extra fouten door deze portie.
`verification.json` bewaart de exacte testnamen, aantallen en hashes van de
ruwe JUnit-bestanden. `local-before.json` en `local-after.json` bewaren de
meetresultaten. Ruwe lokale XML staat in `/workspace/scratch/d6a-final-before.xml`
en `/workspace/scratch/d6a-verified-after.xml`; CI-artifacts zijn nog nodig.

## Uitgevoerd

- Zeven gemigreerde testbestanden: 37 bestaande tests vóór de wijziging groen
  en 37 erna groen. Vijf nieuwe infrastructuurgevallen controleren isolatie,
  beide productieklassen, alle routes/middleware, verzamelen zonder PG en
  hergebruik van een bestaande server.
- De D4/D5-proef is met automatisch gestarte PostgreSQL 16 uitgevoerd, zonder
  PG-skips: writable control, verboden spiegels en vergiftigde spiegels,
  voor zowel Durable als Azure. Samen met de infrastructuurproeven: 15 groen.
- Root-start in een tijdelijke Docker-container: echte PostgreSQL 16 onder
  `nobody`, succesvolle verbinding, statusbestand van de aanroeper met modus
  `0600`, en verwijderde serverdata/status na `--stop`. Herhaalbaar met
  `python evidence/d6a/probe_root_postgres.py` als root; geen Docker nodig
  wanneer PostgreSQL 16 al aanwezig is.
- Gewone gebruiker in Codex: start, schema, klonen, lifecycle, verbindingen
  en opruimen daadwerkelijk uitgevoerd. PostgreSQL 16.15, Python 3.13.5.
- Na installatie van de actuele Python-afhankelijkheden en toevoeging van
  `psql` aan `PATH` zijn beide volledige suites opnieuw, na elkaar gemeten.
  De aanvankelijke run (1115,091 s, 25 fouten) gebruikte een onvolledige setup
  en geldt niet als vergelijkbare baseline.
- Een tussenrun had tien extra fouten: twee tekstcontroles op de oude
  CI/startupstructuur en acht viewtests met een onvolledige testdouble.
  Die zijn hersteld (75 gerichte tests groen) en de bovenstaande volledige
  nameting is daarna opnieuw uitgevoerd. De startupcontrole toetst nu de
  werkelijk geregistreerde hook; de CI-controle bewaakt dat de meetrunner
  de volledige suite zonder paden of filters start.
- De tijdelijke servicepolicy wordt na succesvolle en mislukte installatie
  hersteld, inclusief een oorspronkelijke symlink. Root en sudo-commandflow
  zijn met APT/command-doubles getoetst; dit is geen uitgevoerde APT-installatie
  in Cursor.
- Productie-GET `/review` gebruikt nu de bestaande leesscope die de basisroute
  al had. De native leestest kiest expliciet `task=individual` en controleert
  gelijkblijvende HTML en authenticatie. Review-workboard-regressies: 13 groen.
- Repository-preflight, release-control, architectuurgrenzen, compilatie,
  contractvalidatie en shellsyntaxis zijn uitgevoerd. Architectuurinvarianten:
  6 groen.

## Fixturekeuze

`database-benchmark.json` vergelijkt drie varianten op dezelfde kleine
commit/leesproef met tien herhalingen. Schemaopbouw per test: mediaan 197 ms;
sjabloonkopie: 79 ms; rollback: 6 ms. De onafhankelijke lezer ziet alleen bij
de eerste twee varianten de write. Rollback is daarmee geen geldige algemene
fixture voor deze suite: herstart, onafhankelijke verbindingen en subprocessen
moeten gecommitteerde toestand kunnen zien. Dit is een fixtureproef, geen
groene volledige portie onder een transactievariant.

De gekozen fixture kopieert een sessiesjabloon en bewaart echte commits.
De benchmark omvat aanmaken, de probe en verwijderen van de testdatabase;
eenmalige schemaopbouw van het sjabloon wordt apart gemeten.

## Nog open

- Dezelfde volledige metingen in CI; de workflow publiceert JSON en JUnit
  als `suite-timing-*`. Er is vanuit deze sessie geen CI-run gestart.
- Cursor lokaal en, indien gebruikt, Cursor cloud: geen uitgevoerde run
  vanuit deze omgeving. Een Codex-run geldt niet als Cursor-bewijs.
- Blijvende Codex-omgevingsinstelling `PGBIN` en setupcommando moeten in de
  beheerde omgevingsconfiguratie worden ingesteld; hiervoor is geen
  configuratieschrijftool beschikbaar in deze sessie. Repo-instructies staan
  in `docs/agents/postgres-tests.md`.
- Resterende consoletests en legacy schema-resetfixtures migreren in volgende
  porties van maximaal ongeveer twintig testbestanden. Ook de volledige
  `file_topology`-inventaris is nog niet af.

D6b blijft wachten op de volledige migratie, nul PG-skips in CI, aanvaardbare
looptijd, de gebruikte agentomgevingen en de review van Lex, Sherlock en Argos.
