# HA-2a herstel van annotaties uit de workflowback-up

Change class: A
Promise: Na offline herstel van de bestaande workflowback-up hervat de researcher exact dezelfde opgeslagen annotatieversies en commandresultaten.
Proof: `tests/test_human_annotation_postgres.py`, echte PostgreSQL-bron en lege onafhankelijke doeldatabase.
Touches lifecycle invariants: yes
Rewrite risk: high

Onderdeel van de expliciete implementatieopdracht #1015/MET-59. Gevonden bij
werkstap A op `c23933d2`, main `e0a3b09a`: procesherstart leest annotaties uit
PostgreSQL, maar `formation_recovery_v1.TABLES` exporteert de vier tabellen uit
migratie 034 niet. Een back-up/restore zou daardoor werk én de ownership-fence
verliezen. Dit is geen hypothese over productiedata; de regressie gebruikt een
synthetische bron en de echte recovery-adapter.

## Lifecyclecontract vóór de reparatie

Lifecycle entity: ongepubliceerde WorkingRevision met gepinde annotatieset.
Lifecycle transition: opgeslagen werk -> offline lege-doelrestore -> identiek opgeslagen werk.
Initial durable state: bronpin, meerdere entryversies, actuele heads en commandreceipts in workflow PostgreSQL.
Trigger: bestaande `PostgresWorkflowRecoveryAdapter.export_state/restore_state`.
Authorization: bestaande offline beheerprocedure; geen nieuw HTTP-herstelendpoint of annotatierecht.
Validation: archiefversie, volledige tabelset, kolommen, FK's, oorspronkelijke bron-/extractiepin, payloadhashes en verband tussen versies, heads, generatie en receipts.
Mutable entities: uitsluitend lege onafhankelijke doeldatabase, binnen de bestaande restoretransactie.
Immutable entities: brondatabase, bronbytes, entryversies, commanduitkomsten, historische publicaties.
Workflow state before: processing.
Workflow state after: processing, zonder nieuw oordeel of bouwopdracht.
Release state before: ongewijzigde historische releases.
Release state after: identiek.
Serving state before: registrybepaald.
Serving state after: identiek; restore activeert geen nieuw object.
Expected API result: bestaande recovery-operatie slaagt met exacte annotatietabellen of rolt geheel terug.
Expected UI result: na verse productiecompositie dezelfde concepten, rollen, pending-range en volgorde; opnieuw opslaan kan verder.
Failure result: lege doel blijft leeg; onvolledig archief krijgt geen verzonnen annotaties.
Restart result: dezelfde heads, generatie en receipts; oude AI-schrijfroute blijft geweigerd.
Recovery result: bestaand archief herstelt exact, duplicate save geeft het oorspronkelijke resultaat.
Legacy-data result: oudere archiefversies zonder deze capaciteit blijven leesbaar; afwezige annotaties worden nooit gereconstrueerd.
Required black-box scenario: bron ontvangen -> meerdere bereiken en pending-range bewaren -> versie wijzigen -> export -> lege andere PostgreSQL-database herstellen -> verse console -> overzicht vergelijken -> duplicate herhalen -> nieuwe versie bewaren; corrupt herstel laat doel leeg.
Explicit non-goals: seal, materialisatie, reviewintegratie, cutover en praktijkacceptatie.

## Herschrijfrisico

Rewrite target: volledigheid van de bestaande offline herstelgrens, geen nieuwe back-upautoriteit.
Why local patching is insufficient: alleen editor- of restarttests zien de weggelaten tabellen niet.
Current authority/writer/reader map: `human_annotation_v1.prepare/save/overview` schrijft/leest migratie 034; `formation_recovery_v1.export/restore/assert_empty/validate/upgrade_legacy` beheert producerstate; `workflow_chain_recovery_v1` beheert archiefversie, repeatable-read export en exclusieve lege-doelrestore; `FormationTaskStore.read_formation_evidence` blijft eigenaar van historisch modelbewijs.
Supported runtime topologies: document-input legacy/v1; bestaande productiecompositie; beide databases echte PostgreSQL. Blobbytes blijven onder de bestaande ketenback-up, niet in de annotatietabellen.
Persisted-state impact: geen databasemigratie; workflowarchiefversie 10, formation-sectie versie 3 met annotatietabellen in FK-volgorde en deterministische rijvolgorde.
Compatibility/migration plan: v9/formation-v2 en eerdere ondersteunde archieven upgraden alleen met lege ontbrekende tabellen. Nieuwe versie weigert ontbrekende tabellen. Een pre-fix archief van een reeds geannoteerde bron kan zijn weggelaten werk niet teruggeven: opnieuw exporteren uit de oorspronkelijke database vereist; niet als volledige annotatieback-up gebruiken.
Rollback/recovery plan: huidige brondatabase blijft intact; mislukte import rolt terug inclusief exclusieve locks en bestaande trigger-DDL. Oudere software mag v10 niet als v9 interpreteren. Geen triggeruitschakeling voor annotaties, geen destructieve migratie.
Cutover trigger: nieuwe exports gebruiken v10; herstelbewijs moet voor beide opslaglayouts slagen voordat deze stap gereed heet.
Cleanup/decommission criteria: geen tijdelijke tweede exporter; versie-upgrade blijft alleen historische readercompatibiliteit.
Failure blast radius: lege offline doeldatabase; bron en serving blijven intact.
Adversarial proof matrix: ontbrekende annotatietabel, ontbrekende geschiedenis/receipt/head, payload-/bronpincorruptie, omgekeerde archiefrijvolgorde, legacy archief, vervolg-save na restore en oude AI-fence na restore.

## Vergeleken vormen

Beide opties zijn door dezelfde agent onderzocht, geen onafhankelijke review.
Een losse annotatie-export naast de ketenback-up heeft twee snapshots en kan
een head zonder bijbehorende bron/versie terugzetten. Afgewezen. Uitbreiding van
de bestaande repeatable-read export en één restoretransactie behoudt één
snapshot en de bestaande rechten-/FK-/lege-doelgrens. Gekozen. Geen nieuwe
store, service, queue of provider nodig.

## Aanroepers en datavorm

De beheerder blijft `PostgresWorkflowRecoveryAdapter(store).export_state()`
en `restore_state(state)` gebruiken. De eerste levert een consistente snapshot;
de tweede weigert een niet-lege doelstore en importeert atomair. Een client met
archief v9 krijgt geen v10-reader door een versienummer te negeren. Bestaande
`backup_workflow_chain`/`restore_workflow_chain` gebruiken dezelfde adapter;
er komt geen apart annotatiebestand dat later moet worden samengevoegd.

`annotation_sets` bevat één bronpin per snapshot; `annotation_versions` bewaart
append-only payload/hash/auteur/status; `annotation_heads` bepaalt actuele entry
en positie; `annotation_commands` bewaart exacte verzoekhash en uitkomst. Alle
vier exporteren in dezelfde repeatable-readtransactie. Restore plaatst ze na
bron/extractie en bestaande pogingen in FK-volgorde, met alle bestaande fences
actief. Validatie controleert ook oude versies, pending-ranges, heads, receipts
en generatie; niet alleen de huidig zichtbare selectie. Historische auteurrechten
worden niet opnieuw geïnterpreteerd als actuele goedkeuring.

Een oudere archiefvariant zonder formation-sectie behoudt expliciet die
afwezige capaciteit (`null`) bij de interne upgrade. Geen bron-/annotatierijen worden
verzonnen. Een nieuwe export bevat de volledige versie-3-sectie; weglaten van
die sectie, `null` in plaats van de sectie of een ontbrekende vereiste tabel
wordt geweigerd. De legacycheck gebruikt de oorspronkelijke archiefversie,
niet een intern al genormaliseerde drager. Er is geen claim dat een
eigenhandig herschreven, opnieuw gehasht archief authentiek is: de bestaande
ketenback-up/checksum- en beheergrens blijven van toepassing.

## Werkelijk uitgevoerd bewijs

- Regressie vóór reparatie: `pytest -q tests/test_human_annotation_postgres.py
  -k annotation_backup --tb=short`: **2 failed**, beide `KeyError:
  annotation_versions`, op echte PostgreSQL 16.4 met legacy/v1 documentinputs.
- Na tabel-/versie-uitbreiding en importvalidatie: beide restore/hervatproeven
  **2 passed**. Zelfde historie/overzicht/receipts na een verse productieconsole;
  daarna originele duplicate en nieuwe save; oude modelstart blijft geweigerd.
- Gerichte suite `tests/test_human_annotation_postgres.py
  tests/test_workflow_recovery_refusals_v1.py tests/test_workflow_chain_recovery_v1.py
  tests/test_formation_evidence_postgres.py tests/test_operational_document_inputs_postgres.py`:
  **126 passed**, inclusief corrupte import en rollback. Daarna extra legacy
  upgradevarianten toegevoegd; hun definitieve resultaat volgt uit de brede run.
- Verplichte architectuur-/governancechecks plus refusal-compatibiliteit:
  **19 passed**. Repositorypreflight, compileall, architectuurchecker en
  diff-check slagen. Releasecontrol wordt na de commit nogmaals uitgevoerd.
- De daadwerkelijke vorige v9-reader uit commit `c23933d2` afzonderlijk geladen
  en een v10-header aangeboden: **PASS**, weigert met
  `workflow_backup_version_invalid`. Dit is een formatcompatibiliteitsproef,
  geen productie-rollback of herstel van al eerder weggelaten annotaties.
- Afzonderlijke adversariële pass: in een geïsoleerd testproces alleen de nieuwe
  `_validate_annotations`-controle uitgezet. De proef met een onjuiste quotehash
  in een oudere entryversie, ondanks bijgewerkte payloadhash, faalt dan op
  **DID NOT RAISE**. Zonder mutatie wordt die import atomair geweigerd. Alleen
  de testproceshook was gewijzigd; tijdelijke hook verwijderd.
- Eerste brede run gestopt na **762 passed, 2 failed, 21 skipped**: beide fouten
  waren oude rollbacktestverwachtingen `9`, bij de nieuwe archiefversie `10`.
  Verwachtingen bijgewerkt met extra controle dat legacy werk geen annotatie-
  ownership krijgt; overige durable/API-vergelijking behouden. Ook de bestaande
  topic-upgradetest volgt de nieuwe versie. Deze gestopte run telt niet als
  complete regressiecontrole. Volledige herhaling loopt; geen PASS geclaimd.
- Aanvullende adversariële proef vond een echt verschil tussen ontbrekende en
  `null`-formation-sectie bij een nieuw v10-archief. Repro **1 failed: DID NOT
  RAISE**. Current-formatvalidatie weigert nu beide; herstel van echte oudere
  versies toetst de oorspronkelijke drager. **50 passed** voor annotaties,
  native recovery, v7/v8/v9-upgrades, topics, refusals en beide pinned-runtime
  rollbackgevallen. De tussentijdse brede run is gestopt vóór deze codewijziging
  (**4939 passed, 44 skipped, 3 xfailed, 21 subtests**), en telt niet als compleet.
  De definitieve brede herhaling toetst de gerepareerde grens.
- Brede herhaling met acht workers: **8364 passed, 3 failed, 46 skipped,
  3 xfailed, 32 geslaagde subtests**. Twee bestaande timinggrenzen werden net
  overschreden (0,256 s bij grens 0,25 s; 3,061 s bij grens 3 s); één bestaande
  serialized-writerproef kreeg een generieke writefout. Deze drie gevallen
  afzonderlijk, zonder code- of drempelwijziging: **3 passed**. De omgeving heeft
  een CPU-quota van vier CPU's; volledige herhaling met vier workers loopt,
  zonder gelijktijdige andere PG-proeven. Geen compleet groen resultaat uit
  deze acht-worker-run afgeleid.

Voor native tests: `env -u METIS_TEST_POSTGRES_DSN PGBIN=/tmp/metis-pg16/bin
PATH="/tmp/metis-pg-client/usr/lib/postgresql/17/bin:$PATH" .venv/bin/python -m pytest …`.
De repositoryfixture start en ruimt echte tijdelijke PG16-servers op. De
psql17-binmap levert alleen de client voor bestaande SQL-tests. Geen database-
skip telt als bewijs. Geen nieuwe browser- of praktijkacceptatie geclaimd voor
deze backendherstelwijziging.

### Definitieve volledige herhaling

`pytest -q -n 4 -rs --tb=short --show-capture=no`, met bovenstaande PG16- en
psql-configuratie: **8367 passed, 46 skipped, 3 xfailed, 16 warnings en 32
geslaagde subtests; exit 0**, 1530,32 s. Code gelijk aan `8d1d63b7`; de
daaropvolgende vastlegging wijzigt alleen dit bewijsdocument. Alle native
databasegevallen uitgevoerd, geen PG-skip. De 46 skips zijn 23 opt-in-browsers,
12 echte Docling/PDF-acceptatiegevallen en 11 optionele Bend-proeven. De
23 browsers waren eerder daadwerkelijk groen op HA-2a `c23933d2`; deze
backendherstelwijziging heeft geen UI gewijzigd. Geen nieuwe browserrun,
PDF-/Azure-productieacceptatie of onderzoekerpraktijk uit deze brede run afgeleid.

De afzonderlijke controlepass omvatte huidige en historische entryversies,
ontbrekende heads/receipts/tabellen/sectie, null-sectie, corrupte bron/getuige,
andere fysieke rijvolgorde, oorspronkelijke v7/v8/v9-archieven en oude writers
na restore. De mutatieproef hierboven toont dat de quotegetuigeproef rood kan
worden. Dit is een pass door dezelfde agent, geen onafhankelijke reviewclaim.

Vervolg: menselijke seal/job/FormationEvidence en materialisatie onder #1015.
De aparte werkboom voor dat vervolg is nog onvoltooid en valt buiten deze
herstel-PR. Geen merge, deployment, nieuwe publicatie of parent-Done.
