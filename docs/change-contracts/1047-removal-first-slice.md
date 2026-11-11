# Eerste opschoonstap na annotatie en reviewkaart

Change class: C
Promise: Een gekoppeld verwijderplan en uitsluitend vier ongebruikte functiedefinities verwijderen, met behoud van al het aangeroepen gedrag.
Proof: Naam-/dispatchinspectie, AST-equivalentie van behouden code, bestaande regressietests en verplichte repositorychecks; meetuitkomsten hieronder.
Touches lifecycle invariants: no
Rewrite risk: none

Opdracht William, 11 november 2026. Uitvoering [#1047](https://github.com/WilliamGomes41/Metis-DS/issues/1047) /
[MET-69](https://linear.app/metis-phoenix/issue/MET-69), kind van MET-11.
Basis: `d5715e61ca47554b89853f190202ad388c30ed07`.
Plan: [verwijderplan](../plans/verwijderplan-na-annotatie-en-reviewkaart.md).

## Scope en bewijs vóór wijzigen

De zoekronde over `src`, `scripts`, `tests`, `.github`, `db`, `examples` en `config`
vond voor elk van de vier identifiers uitsluitend de definitie. Geen decorator,
gelijknamige override of letterlijke dispatchnaam gevonden. De bestaande dynamische
consoletoegang gebruikt expliciete strategy-/store-/authoritynamen, niet deze functies.

- `integrity_kernel.validate_source_integrity`: ongebruikte losse bronvalidator;
  gebruikte bronfragment-, object- en hashvalidatie blijft gelijk.
- `operations_console_v1.session_is_expired`: ongebruikte hulpfunctie; daadwerkelijke
  sessievalidatie en autorisatie blijven gelijk.
- `operations_console_app.knowledge_open_count`: ongebruikte contextual/batch-teller;
  huidige persoonlijke werkprojecties en tweede-reviewtelling blijven gelijk.
- `PostgresWorkflowDocumentRuntimeStore.list_processing_history_inputs`: ongebruikte
  lijstbewerking; gerichte historielezers en alle opslagcommando's blijven gelijk.

Geen runtime-invoer of -uitvoer verandert. Geen duurzame toestand wijzigt door deze
cleanup; kandidaatvorming, reviewbeleid, publicatie en serving blijven bij hun owners.
`storage_prepare`, audit/herstel, historische lezers, alle routes en consolebasisklassen
blijven behouden. De bestaande tests krijgen alleen bewijsannotaties, geen gewijzigde
assertions. De verouderde verwijzing naar de teller in `domain-workplaces.md` vervalt;
het inhoudelijke telcontract blijft staan. Het levenscyclusregister krijgt vier
symboolregels en het bestaande sync-register koppelt #1047 aan MET-69.

## Verificatie

Codecommit: `e3a5d41a71ac3f383bb02d06c930ffe6c19c0bdc`. Python 3.13.5,
geïsoleerde PostgreSQL 16.15, synthetische testdata. Het
[verificatierapport](../../evidence/1047/verification.json) bevat commit,
collectiedigest, uitkomsten per testdeel en AST-bewijs.

- Volledige standaardcollectie: **8.558 geslaagd, 51 optionele omgevingsproeven
  overgeslagen, 3 verwachte xfails; 0 failures/errors en 0 PostgreSQL-skips**.
  De strikte samenvoeging bevestigt dezelfde commit/collectiedigest/PostgreSQL 16
  en exact één uitvoering van alle 8.612 verzamelde gevallen over vier delen.
- De 61 gerichte bestaande sessie-, integriteits-, opslag-, architectuur-,
  documentreferentie- en sync-controles zijn uit die volledige uitvoering
  hergebruikt: alle geslaagd, geen skips. Geen aanvullende herhaling als vervanging
  van een volledige uitslag.
- AST-gelijkheid van de vier behouden productmodules na uitsluitend de genoemde
  definities weg te laten: PASS. De twee gewijzigde testbestanden hebben een
  identieke AST; alleen bewijscommentaar is toegevoegd.
- Repositorypreflight, release-control-preflight tegen `origin/main`, compileall,
  architectuurgrenzen, change-contractvalidatie en diffcontrole: PASS.
- Naamzoekronde na verwijderen: nul verwijzingen in `src`, `scripts`, `tests`,
  `.github`, `db` en `examples`; documentatie en register vermelden de historie.

De eerste omgevingspoging ontbrak de gepinde `regex`-dependency. De daaropvolgende
vroege sharded run is onderbroken omdat de uitgepakte `psql` niet in PATH stond.
Na installatie via `requirements-dev.lock` en correctie van uitsluitend PATH is
de volledige bovenstaande run opnieuw gestart en afgerond. Dezelfde gerichte
herstelproef ging met die PATH-correctie van rood naar groen, zonder codewijziging.
De onvolledige pogingen tellen niet als geslaagd bewijs.

De 51 optionele skips betreffen Chromium (28), Docling/modellen (12) en Bend (11).
Er is geen nieuwe browser-, provider-, deployment- of productieacceptatieclaim.
De bewijsdocumentatie na de codecommit verandert geen broncode, testcode of config.

Vervolgwerk blijft open bij de bestaande issues uit het plan; deze deelslice sluit
MET-11, HA-4 en KO-6 niet. Geen operationele cutover of betaald modelgebruik.
