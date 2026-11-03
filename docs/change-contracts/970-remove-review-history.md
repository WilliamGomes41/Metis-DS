# Verwijder de Review-historiepagina

Change class: B
Promise: Besluiten en historie en Objecthistorie verdwijnen volledig uit Review; oude bookmarks laden geen historische objecten of reviewaudit meer.
Proof: HTTP-redirects vóór document-, passage-, navigatie- en auditcapture, authenticatie behouden, native PostgreSQL-read-only vergelijking en regressies van inventaris/reviewnavigatie.
Touches lifecycle invariants: no
Rewrite risk: none

## Opdracht en grens

GO projectlead, 3 november 2026: verwijder de zware pagina volledig en vervolg
daarna de bestaande performanceopdracht onder #729/MET-36. Deze wijziging is #970.
Zij wijzigt geen opslag-, review-, publicatie- of herstelregels.

## Bestaand mechanisme en wijziging

`install_review_workboard` bezit de publieke Review-GET. De verwijderde
`history`/`decisions`-presentatie vroeg in `_render_review_room` een brede
objectsnapshot inclusief historie en `audit_review_signals` op. Exclusieve
document-/objecthistorierenderers en CSS verdwijnen. Een oude bookmark gaat na
de bestaande toegangscontrole direct naar de gewone documentwerkvoorraad,
vóór eventuele context-/vervolg-/documentcapture.

Werkvoorraadkaarten zonder eigen open reviewtaak verwijzen naar de bestaande
inventaris. Afgehandelde inventarisregels blijven zichtbaar en verwijzen naar
de bestaande bronpassage. Er wordt geen vervangend historiescherm gemaakt.

De PostgreSQL-objecthistorie, bindings, auditevents, Inzicht, exports en
recovery blijven bij hun bestaande owners. Deze wijziging bevat geen durable
write, dataconversie of schemawijziging. Dezelfde objecten en besluiten blijven
herleesbaar door de bestaande kernel en diagnose-eigenaren.

## Verificatie en bewijsgrens

`tests/test_review_history_removed.py` dekt oude document-/objectbookmarks,
authenticatie en het uitblijven van document/source/auditcapture. De native
variant vergelijkt objecten, bindings en ledger vóór en na de redirects.
Dezelfde bookmarktest faalt op de ongewijzigde deploymentbaseline.

Bestaande tests van persoonlijke kaarten, inventaris, gesloten documenten,
bronhergebruik en native reviewroutes blijven gelden. Alleen verwachtingen
en goldens van de expliciet verwijderde UI worden gewijzigd; historische
opslag- en auditproeven blijven behouden.

Deze verwijdering levert geen versnelling van de gewone opslag-/vervolgketen
en geen oplossing voor de open besluitreadback op. Die bewijzen blijven bij
#729, #952 en #953. Geen merge of deployment in deze wijziging.

Uitgevoerd op Python 3.12 en een tijdelijke native PostgreSQL 16-container:

- Bookmarkproef op de ongewijzigde `60e70b25`-baseline: rood door de verboden
  document-/navigatieread, zoals verwacht.
- Geraakte navigatie-, inventaris-, bronhergebruik- en lifecycleprojecties:
  85 passed.
- Koppen, gewone opslag-/heropenketen, actuele dependencies, late-COMMIT
  rollback en weergavecontrolecontract: 33 passed.
- Karakterisatie zonder recordmodus na de laatste wijziging: 35 passed.
  De drie oude historiegevallen zijn verwijderd. De overige HTML-goldens
  wijzigen alleen door de CSS-hash, de verwijderde historie-UI, bestaande
  inventaris/bronlinks en de de-indentatie van de behouden passagerenderer.
- Repositorypreflight, architectuurgrenzen, release-control met de werkelijke
  gewijzigde paden, change-contract, compilatie en diffcontrole: PASS.

Geen volledige suite, browserrender of live acceptatie geclaimd. De
Impeccable-engine kon niet worden geladen; de vendored skill, bestaande
interface en HTML-karakterisatie zijn gebruikt. Exact-head CI blijft vereist.

### Herstel na de eerste CI-run

De eerste CI faalde op beide Python-versies door vier verouderde verwachtingen:
het brede CSS-baselinehash (twee rollen), de inventarislink en de PDF-teruglink.
Deze vier failures zijn lokaal gereproduceerd. De 23 CSS-regelblokken met
`.home-*`-selectors zijn gelijk aan deploymentbaseline `60e70b25`; alleen de
baselinehash voor de bedoelde verwijdering is vernieuwd. De behouden bronproef
gebruikt nu `task=inventory` en controleert nog steeds beide PDF-pagina's en de
markering. De inventarisproef eist de volledige bestaande bron-URL.

De CI-mutatiebaseline verwees bovendien nog naar de drie verwijderde
historietests. Alleen die cases zijn eruit gehaald: 21 van 24 overgebleven
gevallen worden rood door de bestaande tijdelijke mutatie, met exitcode 1;
`check_evidence.py mutation` accepteert de exacte set. Geen goldens opnieuw
opgenomen en geen controle versoepeld.

De review vond ook de oude `/review/bronpassage?task=history|decisions`-route.
De native guardproef faalde vóór herstel op de verboden bronread. Deze route
redirect nu na authenticatie en overzichtstoegang, vóór `open_source_passage`.
Beide oude routes worden getest met verboden document/source/auditreads,
ongewijzigde objecthistorie/bindings/ledger en geweigerde niet-ingelogde toegang.

Hercontrole op Python 3.12/PostgreSQL 16: 66 tests geslaagd (de vier geraakte
regressiebestanden plus alle karakterisatiegevallen), de laatste 8
bookmark-/authenticatieproeven opnieuw geslaagd en de mutatiecontrole PASS.
Repositorypreflight, architectuur, release-control, change-contract, compilatie
en diffcontrole zijn opnieuw PASS. Exact-head GitHub CI blijft vereist.
