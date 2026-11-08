# HA-2b — bewijs en overdracht

Change class: A. Rewrite risk: high. Basis main
`94e3bf7878cfcda0f752403214ea37480cd7106b`; contract:
[1015-human-annotation-build.md](1015-human-annotation-build.md).
Featurebranch `feat/human-annotation-seal-1015`; geen merge of productieactie.

## Uitgevoerde verticale proeven

PostgreSQL16.4, echte native tabellen/constraints, beide operationele layouts.
Geen native databasetest overgeslagen. De bestaande bronstoretransportfixture
is in de technische publicatieketen een MemorySourceStore; alle workflow-,
review-, proof- en publicatieregistratie is PostgreSQL-productcode.

```sh
env -u METIS_TEST_POSTGRES_DSN PGBIN=/tmp/metis-pg16/bin \
  PATH=/tmp/metis-pg-client/usr/lib/postgresql/17/bin:$PATH \
  /workspace/Metis-DS/.venv/bin/python -m pytest \
  tests/test_human_annotation_build_postgres.py \
  tests/test_human_annotation_preview.py \
  tests/test_human_annotation_materialisation.py -xq
```

**43 passed**, geen skips,35.03s. Omvat durable save/herstart, duplicate core,
concurrent finalize, commandconflict, stale overzicht/metadata/seal, save tijdens
bouw, accountintrekking, claimexpiry/nieuwe worker, beide inputlayouts,
backup pending/built met historische metadata, gedeeltelijke en gewijzigde
archieven, ontbrekende guards, self-consistent vervalst/ingekort producerbewijs,
oude candidatewriter en reservering, oude contexttoevoeging en vervalste human
provenance op modelobjecten. De operationele humanref kan niet worden verwijderd.

De vier publicatiegevallen combineren uploader_sole/one_other met supported_by/
explains: selectie -> save -> verse console -> overzicht -> seal -> bestaande
worker -> enige materialiser -> humanproof -> review volgens ingest -> registry ->
ProductAPI200 met hetzelfde release-ID en essentiële context. Vóór review is
publish BLOCKED zonder registry en API404. Daarna leest de bestaande interne MCP
get_publication_status dezelfde registry na herstart. Dit bewijst geen nieuwe
publieke MCP-zoekroute of externe transportauthenticatie.

De eerste versie van de extra negatieve publicatieassertie verwachtte een
exception; de bestaande publicatieowner retourneert terecht status BLOCKED.
De assertie toetst nu BLOCKED, review_work_incomplete en de lege registry.
Geen productregel hiervoor gewijzigd.

```sh
env -u METIS_TEST_POSTGRES_DSN PGBIN=/tmp/metis-pg16/bin \
  PATH=/tmp/metis-pg-client/usr/lib/postgresql/17/bin:$PATH \
  METIS_BROWSER_EXECUTABLE=/usr/bin/chromium \
  METIS_PLAYWRIGHT_MODULE=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright \
  /workspace/Metis-DS/.venv/bin/python -m pytest \
  tests/test_browser_knowledge_context.py -k 'human_build or human_annotation' -xq
```

**2 passed**,12 deselected,24.10s. Werkelijke browsermultipartupload en
ingestkeuze -> muisselectie/veldankers -> save -> nieuwe browsersessie/login ->
hervatten -> dubbele kern geweigerd/origineellink -> herstelconcept -> overzicht
-> stale-overzicht geweigerd -> expliciet afsluiten -> bestaande dispatcher ->
bouwstatus -> reviewroute. De aanvullende annotatiebrowser toetst Unicode,
meerdere blokken/essentiële koppelingen, bronrollen, foutbehoud en toetsenbord.
Tien bouwcaptures op1440/390px plus drie annotatiecaptures; JSerrors[] en geen
horizontale overflow. Bestaande CI-browsermatrix neemt de nieuwe keten op en
uploadt captures als artefact. Lokale screenshots zijn geen productassets.

## Afzonderlijke adversarial pass

Getoetst vóór de full-suite: alternatieve oude writers/reserve/endpoints,
inline/native inputlayouts, stale context zonder generatieverandering,
bron-/claim-/actoractualiteit bij activatie, valse proofleden, provenance/ref-
vervalsing, gedeeltelijke restore, archiefversies10/11, metadata na activatie,
gewone review met behoud van producerbewijs, publicatie vóór review en registry-
leesroutes. Alle herstelacties blijven binnen dezelfde bestaande transactie.

Deze pass vond de noodzakelijke scheiding tussen actuele eerste activatie en
historische offline restore: objecten worden bij restore vóór hun bewijs geladen.
De globale binding is daarom deferred tot aggregatecommit; verse online
objectinvoeging vereist daarnaast direct de actuele seal. Er is geen GUC-bypass.
Een extra native guard blokkeert humanmarker-forgery op modelobjecten en de
oude inputwriter kan humanrefs niet verwijderen of ombuigen.

## Verificatiestatus

Gerichte eerdere ownerregressies:136 passed (FormationEvidence, operational
inputs, chainrecovery, workerhandover, architecture);90 passed (build, annotation,
preview, inputv2, migrations) vóór de laatste aanscherping. Deze tellingen zijn
geen vervanging voor de komende volledige run op vastgelegde code.
Volledige suite en normale repositorychecks: resultaat volgt na uitvoering.

Impeccable detector op UI/buildstatus en editor:[]; geen nieuwe detector na
reviewfix. Finishreview oorspronkelijke onjuiste incomplete-copy resolved;
mobiele navigatie-overlap opgelost door documentflow, finale verdict/documenter
volgen. Geen nieuw DESIGN.md of redesign van de bestaande consolesurface.

## Open grenzen

HA-3/#1016/MET-60: correcties bij oorspronkelijk bronobject na eerste activatie,
nieuwe versie en gerichte reviewinvalidatie. HA-4/#1017/MET-61: totale
omschakeling/verwijdering oude prozacallers en configuratie plus praktijktoets.
MET-58 blijft formeel geblokkeerd op referentiedocument/selectietaak.
Compositiecatalogusupdate wordt bij HA-4 (#1017) afgerond samen met de globale
routeverwijdering; dit contract legt de huidige additieve humanroute vast.
Geen parent-Done, researcherpraktijkacceptatie, release of productieclaims.
