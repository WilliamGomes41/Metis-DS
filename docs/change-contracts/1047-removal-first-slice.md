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

Uitvoering loopt. Nog geen volledige-suite-, merge-, deployment- of productieclaim.
De controles gebruiken Python 3.13 en een geïsoleerde PostgreSQL 16.15-server met
synthetische testdata. AST-gelijkheid wordt gecontroleerd na uitsluitend de vier
genoemde definities uit de basis-AST weg te laten. De echte systeempaden worden
getoetst met bestaande sessie-, integriteits-, review-/opslag- en architectuurtests.

Vervolgwerk blijft open bij de bestaande issues uit het plan; deze deelslice sluit
MET-11, HA-4 en KO-6 niet. Geen operationele cutover of betaald modelgebruik.
