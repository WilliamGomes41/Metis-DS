# D6a, eerste portie — uitvoeringsbewijs

Basis: `9fa2004`. Change class: C. Rewrite risk: none.
Dit bewijs sluit uitsluitend de eerste portie af; D6a en D6b zijn niet gereed.

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
  `psql` aan `PATH` worden beide volledige suites opnieuw, na elkaar gemeten.
  De aanvankelijke run (1115,091 s, 25 fouten) gebruikte een onvolledige setup
  en geldt niet als vergelijkbare baseline.
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

- Volledige lokale vóór/na-uitslagen en verhouding worden bij afronding
  toegevoegd. Geen vergelijking met een anders ingerichte omgeving.
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
