# Metis uitgelegd — verificatie van de eerste versie

Issue [#936](https://github.com/WilliamGomes41/Metis-DS/issues/936).
Class B; rewrite risk: none. Basis: `3ea406b` met de bijbehorende #936-wijziging.

## Aangetoond

- De bestaande PostgreSQL/ASGI-route vereist login, ook voor zoekresultaten,
  modeldossiers en de kennisbasispagina. De domeintoestand blijft gelijk.
- Zoektermen en aliassen leveren vaste begrips- en modellinks op. Onbekende
  inhouds-ID's worden afgewezen; HTML in de zoekterm wordt ontsmet. Een lege
  resultatenlijst geeft een vervolgactie.
- Alle verwijzingen naar gerelateerde begrippen en alle bronbestanden bestaan.
- Chromium verifieert 1440px en 390px, toetsenbordbediening, ontbreken van
  horizontale overloop, laden van de paginastijl, licht/donker en een echte
  zoek- en navigatieroute met JavaScript uitgeschakeld. Acht screenshots zijn
  gemaakt; drie representatieve beelden staan hieronder.
- De Impeccable-detectiescan van de gewijzigde renderer, inhoud en eigen CSS
  levert geen bevindingen op: `impeccable-detector.json` bevat `[]`.
- De zoekhint is in licht en donker gemeten op minimaal 4.5:1 contrast.
- De eigen stylesheet laat de gedeelde console-CSS en haar versie intact.
  Een eerder falende karakterisatietest van de reviewpagina slaagt daarmee weer.

De browserfixture gebruikt uitsluitend een synthetisch account en een eigen
wegwerpdatabase op PostgreSQL 16.2. Geen modelaanroep, echte bron, productie-
database, Azure-deployment of wijziging van de publicatieketen is uitgevoerd.

Volledige suite op Python 3.12.14: **6438 passed, 40 skipped, 3 xfailed,
24 subtests passed**, 16 waarschuwingen. Uitvoering met pytest-xdist, vier
workers en per worker een eigen PostgreSQL-server; geen gedeelde mutabele
testdatabase. De expliciete browserproef op Chromium 151.0.7922.173 slaagt
afzonderlijk (**1 passed**). De default suite activeert optionele browserproeven
niet; dit resultaat vervangt geen ontbrekende externe integratieproeven.

## Beelden

- [Overzicht op desktop](desktop.png)
- [Modelverantwoording op desktop](model.png)
- [Modelverantwoording op mobiel](mobile.png)

## Reproductie

Gebruik de bestaande dev-dependencies en een PostgreSQL 16-testserver volgens
`scripts/test_postgres.sh`. De engine- en browsertools horen bij de testomgeving,
niet bij productdependencies.

```sh
python -m pytest -q tests/test_console_metis_dictionary.py tests/test_metis_explained_content.py
METIS_BROWSER_EXECUTABLE=/path/to/chromium \
  METIS_PLAYWRIGHT_MODULE=/path/to/playwright \
  python -m pytest -q tests/test_browser_metis_explained.py
IMPECCABLE_HOME=/path/to/writable/cache \
  .agents/skills/impeccable/scripts/impeccable detect --json \
  src/settings/metis_dictionary_ui.py src/settings/metis_explained_content.py \
  assets/brand/metis-explained.css
```

## Bewijsgrenzen

Dit is technische verificatie van de uitlegpagina met inhoudelijke conceptteksten.
De bronverwijzingen onderbouwen de beschreven systeemaanpak; zij bewijzen geen
klinische juistheid of actuele productieconfiguratie. Eigenaarsnamen, actuele
collectieaantallen en model-evaluaties worden niet ingevuld zonder bewijs.
Mobiel is een Chromium-viewport; een fysiek toestel en een volledige
ondersteunende-technologietest zijn niet onderzocht. De bredere repo-checks
worden in het change contract en de PR gerapporteerd.
