# MET-42: begrensde leesproeven en open ketenbewijs

Dit is lokaal synthetisch PostgreSQL 16-bewijs. Geen productieherstel,
Azure-SLO, merge- of deploymentacceptatie. Alle bestaande budgets blijven staan.

De oorspronkelijke dependencylookup faalde bij 1100 rijen / 18.6 MB en 150
object- plus blocktargets na 5.0103 seconden met SQLSTATE 57014. De ANY-variant
faalde ook (5.0134 seconden). De gegenereerde compacte dependencywaarde levert
met dezelfde targets en uitkomst 0.1309 seconden voor zowel reader als command.
De native regressie forceert ook een sequential scan om toevallige indexkeuze
niet als bewijs van isolatie van grote payloads te gebruiken.

De aparte HTTP-proef met 1100 actuele kandidaten doorloopt GET, bestaand
reviewcommand, echte redirect en heropenen. Eerste meting: 0.1695 / 0.8385 /
1.6378 / 0.2208 seconden. Overige objecten blijven exact gelijk en ongereviewd
werk blijft publicatie blokkeren. De test assert de bestaande lokale doelen
(detail maximaal 5 seconden, POST maximaal 3 seconden); dit zijn geen SLO's.

## Het gecombineerde ketenbewijs is nog rood

`combined_probe.py` is expliciet uitvoerbaar en behoudt de oorspronkelijke
3/5-secondenassertions. Het combineert echte gedeeltelijke vorming (twee geldige
brononderdelen, negen met ongeldig modelbewijs), 1100 opgeslagen objectversies,
meer dan 25 MB bewaarde verwerkingshistorie en een bestaand menselijk besluit.
De 1100-versiesproef belast historische lineage; hij is niet gelijk aan de
aparte 1100-actuele-kandidatenproef.

| Opslag | GET | POST | Redirect GET | Heropenen | Verouderde POST |
|---|---:|---:|---:|---:|---:|
| Legacy | 1.617 s | **21.873 s** | 3.251 s | 1.339 s | 0.312 s |
| Compact | 1.561 s | **23.027 s** | 3.446 s | 1.393 s | 0.083 s |

Beide proeven bewaren het bestaande goedgekeurde object en zijn binding,
weigeren de verouderde POST met 409 zonder nieuwe mutatie/audit, en maken geen
release zolang vorming onvolledig is. Beide falen op de POST-budgetassertion.
De compacte opslagovergang alleen lost deze schrijfvertraging dus niet op.
De oorzaak van deze aanvullende schrijftijd moet in het bestaande commandpad
worden vastgesteld onder [#952 / MET-43](https://github.com/WilliamGomes41/Metis-DS/issues/952).
Deze rode probe is geen vrijstelling van het totale publicatiedoel onder #948.

Uitvoeren, met een eigen disposable PostgreSQL 16-server en repositoryvenv:

```bash
PYTHON=.venv/bin/python scripts/test_postgres.sh
PYTHONPATH=. .venv/bin/python -m pytest -q -s -p tests.conftest \
  evidence/review-scoped-951/combined_probe.py
```

Verwachte huidige uitkomst: twee functioneel geldige ketens, twee rode
POST-budgetassertions. Geen xfail, skip, timeoutverhoging of ruimer budget.
Deze relatief dure releaseprobe staat apart van de routineleesregressies;
groene routinetests zijn geen bewijs dat deze keten groen is.

Resterend: commandlatency en atomaire command-/publicatieraces onder MET-43,
behoud van originele Smetten-besluiten en echte live review/publicatie onder
MET-44. MET-42 en het parentissue worden hiermee niet automatisch gesloten.

## Uitgevoerde aanvullende verificatie

- Native gerichte checks: dependencytypes/containment, directe SQL-writers,
  gegenereerde waarde niet vervalsbaar, rollback/herstel, ontbrekend/vervalst
  schema, coherente documentpoging bij gelijktijdige reserve, en gewone
  passage-GET zonder globale archiefread. Beide bestaande broncomposities.
- Zes pickerchecks groen, inclusief noodzakelijke context buiten de pagina,
  een aangeboden keuze die geen ongerelateerde dependencycomponent inlaadt,
  en hergebruik van een al gekoppelde contextbron voor een extra passage.
- Werkelijke Chromium-broncontextketen op desktop/mobiel groen: navigeren,
  kiezen, bewaren en heropenen via de bestaande form-/commandowners.
- Nieuwe niet-geëvalueerde documentmelding gerenderd en visueel bekeken op
  1440 en 390 pixels: 16px tekst, echte stylesheet, geen horizontale overflow
  of geneste formulieren. De broncontextlink blijft bereikbaar.
- Impeccable regexdetector op gewijzigde UI-bestanden: geen meldingen;
  elementregels voor contrast/layout liepen niet op Pythonbestanden.
- Repositorypreflight, architectuurgrenzen, zes architectuurinvarianten en
  het volledige Class-A/high-risk-PR-contract zijn gecontroleerd.

De volledige lokale collectie is uitgevoerd: 6754 cases, 6709 geslaagd,
2 falende oude formulierasserties, 43 bestaande optionele skips, nul
PostgreSQL-skips. De twee tests eisten de oude volledige objectsettoken op
het foutscherm; de begrensde foutread gebruikt dezelfde bestaande generatie-
preconditie als gewone passage-GET. Hun modules zijn daarna aangepast en
afzonderlijk groen (4 + 6 tests), inclusief werkelijk indienen van het
herstelde formulier. Een aanvullende echte formuliercontrole bewaart ook alle
bestaande contextdoelen buiten de 25-rijenkeuzepagina (2 cases groen).

De rode volledige-runresultaten worden niet als groen samengevoegd.
`local-results.json` bewaart de aantallen en de status. Definitieve GitHub CI
op de laatste commit moet nog afronden. Deze controles vervangen het expliciet
rode gecombineerde ketenbewijs niet.

## Herstel van de CI-testomgeving

Class C, rewrite risk none: uitsluitend testvoorzieningen; geen wijziging van
productcode, testselectie, vereiste controles of publicatievoorwaarden.

De CI-run op `f91aa130` strandde in beide browserjobs vóór de tests:
`Playwright does not support chromium on ubuntu26.04-x64`. De jobs gebruikten
`ubuntu-latest` bij de vastgepinde Playwright 1.58.2. Beide browserjobs gebruiken
nu expliciet de ondersteunde Ubuntu 24.04-image. De Bend/consolevergelijking
strandde op ontbrekend PostgreSQL 16; die job krijgt dezelfde expliciete
PostgreSQL 16-service en Unixsocket als de andere native CI-proeven, plus de
bestaande databasepreflight vóór de consolevergelijking.

Een gerichte configuratieprobe was rood op de oorspronkelijke workflowbestanden
en groen na deze wijziging. Vijf workflowcontracttests zijn groen; ze behouden
ook de onafhankelijkheid van browserjobs, verplichte gates en weigering van
overgeslagen native bewijschecks. De echte browserinstallatie en uitvoering
moeten vervolgens in GitHub Actions slagen; een YAML-test bewijst dat niet.
