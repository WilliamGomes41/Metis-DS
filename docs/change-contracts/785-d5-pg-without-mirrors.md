# D5 — Schijfspiegels uit de volledige PostgreSQL-topologie (onder #730)

Part of #730.

**Status: implementatie in uitvoering op expliciete opdracht van William. D4b voltooid in commit `8f3d1fa`; merge en deploy volgen de bestaande gates.**

Basis: `main` op `629d63c` (D2, D3 en D4 gemergd). De lezerskaart hieronder komt uit een lokale run van `tests/test_pg_console_without_disk_mirrors.py` op PostgreSQL 16, aangevuld met statische analyse voor alles wat buiten het D4-scenario valt. De ruwe lokale D4-uitvoer is niet in deze sessie ontvangen; de aangeleverde lokale samenvatting is vergeleken met de definitieve D4-CI. Zie de bronprecisering onderaan.

Change class: A
Promise: In de volledige PostgreSQL-topologie leest en schrijft de console geen workflowspiegels, publicatieprojectie of releasemanifests op schijf; PostgreSQL en Blob zijn de enige toestand, ook na herstart en na code-rollback.
Proof: De D4-proef zonder xfail, met alle vijftien fases voltooid in de weigerrun, plus een gifrun met aanwezige, afwijkende spiegelbestanden en nul geregistreerde toegang; beide met de Durable- én de Azure-consoleklasse; native lifecycle-, concurrency-, herstart- en rollbackproeven groen.
Touches lifecycle invariants: yes
Rewrite risk: high

## Besluiten (William, vastgelegd bij aanmaken op basis van de aangeleverde issuebron)

**B-D5-1 Startvoorwaarde en eindbewijs.** Implementatie start wanneer D4 een vastgepinde baseline heeft: de exacte set (eigenaar, bestand, toegang, fase) uit de controlerun staat als verwachting in de test, en elke afwijking faalt. Het D5-eindbewijs is dezelfde proef zonder xfail, met alle fases voltooid in de weigerrun, plus de gifrun hieronder. "D4 groen zonder spiegeltoegang vóór D5" vervalt als formulering, want die was circulair.

**B-D5-2 Publicatiescope.** Publicatieprojectie en releasemanifests vallen binnen D5. `_apply_local_release_copy` wordt gesplitst: het bestandsdeel verdwijnt, het autoriteitsdeel blijft (zie *Gekoppelde autoriteit*). De Blob-verificatie in Azure wordt een expliciete stap en blijft niet meer impliciet afhangen van de projectiebouw.

**B-D5-3 Herstelcontract.** Voor de volledige PG-topologie vervallen workflowspiegels, publicatieprojectie en releasemanifests als herstelbron. Herstel loopt via `backup_workflow_chain` en `restore_workflow_chain` (PostgreSQL plus Blob), zonder runtime-bestanden. Een code-rollback vereist dat de vorige commit zijn toestand aantoonbaar uit PostgreSQL herbouwt; dat wordt in deze issue bewezen en niet aangenomen. De diagnose-export (`processing_evidence_export_v1`) is geen backup.

## Startvoorwaarde: D4b (Class C, vóór D5)

D4 controleert nu alleen of een toegang een bekende eigenaar heeft. Een nieuwe toegang door een bekende eigenaar, in een andere fase, glipt erdoor. D4b voegt drie dingen toe, alleen in de test:

1. Pin de set uit de tabel hieronder als exacte verwachting voor de controlerun.
2. Breid de guard uit met `os.replace`, `os.rename`, `os.unlink`, `os.remove` en `shutil.rmtree`. Nu ziet hij alleen `open`, `io.open` en `os.open`; atomische hernoemingen en verwijderingen blijven onzichtbaar.
3. Voeg fases toe die D4 nu niet doorloopt (zie *Statische aanvulling*): opstarten via `console_asgi.build_app()` (inclusief `reconcile_durable_publications` en `migrate_legacy_revise_to_review`), verwijderen van een ongepubliceerd document, en de Azure-consoleklasse naast de Durable-klasse.

## Lezerskaart: dynamisch (D4-controlerun, `629d63c`)

| Eigenaar | Bestand | Toegang | Fases (controlerun) |
|---|---|---|---|
| `_apply_local_release_copy` | `envelopes.json` | schrijven | pub1, pub2, wd |
| `_apply_local_release_copy` | `published_projection.jsonl` | schrijven | pub1, pub2, wd |
| `_apply_local_release_copy` | `release_manifests/*` | schrijven | pub1, pub2, wd |
| `_ledger_mirror_tail_hash` | `review_ledger.jsonl` | lezen | rv1, rv2, rv3 |
| `_mirror_bindings` | `publish_authorizations.json` | schrijven | start, in1, rv1, pub1, in2, rv2, pub2, in3, wd, herst, rv3 |
| `_mirror_envelopes` | `envelopes.json` | schrijven | start, in1, rv1, in2, rv2, in3, herst, rv3 |
| `_mirror_events` | `review_ledger.jsonl` | schrijven | rv1, pub1, rv2, pub2, rv3 |
| `_mirror_objects` | `objects/*` | schrijven | in1, rv1, in2, rv2, in3, rv3 |
| `_read_optional` | `envelopes.json` | lezen | pub1, pub2, wd |
| `_read_optional` | `published_projection.jsonl` | lezen | pub2, wd |
| `_read_optional` | `release_manifests/*` | lezen | wd |
| `_read_optional` | `review_ledger.jsonl` | lezen | pub1, pub2, wd |
| `_remirror_review_runtime` | `review_ledger.jsonl` | schrijven | start, rv1, rv2, herst, rv3 |

"Schrijven" omvat hier ook openen met lees- en schrijfrechten. Fase `acc` (accounts en sessies) heeft geen toegang: identiteit is al schoon.

De weigerrun stopt bij `publish-v1` met `durable_publication_local_copy_failed`. Acht van de twaalf fases zijn met weigering nooit uitgevoerd. De controlerun dekt ze wel; daarom is die run de kaart en de weigerrun het bewijs.

## Lezerskaart: statische aanvulling (buiten het D4-scenario)

| Pad | Wat het met bestanden doet | Gevolg voor D5 |
|---|---|---|
| `_PostgresWorkflowDocumentsMixin._delete_unpublished_snapshot_locked` | leest objects, envelopes, bindings en ledger als terugvalkopie (`read_bytes`, alleen als het bestand bestaat); `_delete_unpublished_snapshot_authority` doet `unlink` op het objectbestand | in scope; zit niet in D4 en is onzichtbaar als het bestand ontbreekt |
| `OperationsConsole._commit_prepared_store` (basis) | leest ledger-`exists/stat`; objectbestand wordt alleen gelezen als `objects` niet `None` is | wordt via `super()` bereikt als `envelopes` en `objects` beide `None` zijn: juist die tak doet dus geen objectbestand-read; ledger-metadata-I/O blijft in scope |
| `OperationsConsole._objects_write_lock`, `_durable_receipt` | alleen in de basisklasse | vaststellen of ze in PG bereikt worden; de gifrun beslist |
| `_PostgresWorkflowDocumentsMixin._reload_store_locked` | `_load_map(_bindings_path)`, dat door de review-mixin `{}` oplevert, waarna PG wordt gelezen | overbodige aanroep; verwijderen |
| `DurablePublicationConsole.reconcile_durable_publications` (start, `console_asgi`) | herschrijft projectie en manifests voor elke release | in scope; zit niet in D4 |
| `OperationsConsole._snapshot_in_published_projection` | leest de projectie | in PG overschreven door `DurablePublicationConsole.snapshot_is_published` (store gezet); geen PG-lezer |
| MCP (`metis_mcp_queries_v1`), kwaliteit (`quality_metrics_app_v1`), workboard (`review_workboard_v1`), herstelpaden in `source_context_review_v1`, `review_participation_v1`, `decision_review_commands_v1`, `closed_review_loop_v1` | `read_events(_ledger_path)` en `append_event(_ledger_path)` | gaan via `register_backend` naar PG; **`_ledger_path` blijft als sleutel bestaan** (non-goal: de ledger-API vervangen) |
| Product API (`product_api_v1`) | real-modus leest canonical PG en verifieert bronnen; fixture-modus leest eigen fixturebestanden; geen consoleprojectie | implementatie buiten scope; relevante gelijkheidsproeven blijven eindbewijs |
| `publication_chain_recovery_v1.check_chain_integrity` | controleert `release_manifests/*.json` tegen PG als `runtime_root` is meegegeven | aanpassen: in de PG-topologie geen runtime-root meer meegeven; oude manifests worden niet meer als bewijs gelezen |
| `backup_workflow_chain` en `restore_workflow_chain` | nemen runtime-data mee (`export_runtime_data`, `restore_runtime_data`) als `runtime_root` of `runtime_dest` is meegegeven | volgens B-D5-3 zonder runtime-bestanden; zie *Afstemming met #695* |
| `runtime_data_inventory_v1`, `azure_deploy_package` | noemen de bestanden als runtime-data of uitsluiting | documentair bijwerken; uitsluiting in de deploy-ZIP blijft |
| telemetrie (`request_diagnostics_v1`, `telemetry/playbook.py`) | fase `store_remirror`, waarschuwing `store_command_ledger_divergence` | verdwijnen |

## Gekoppelde autoriteit: niet weggooien met het bestandsdeel

1. **Publicatiestatus van de envelope.** `_PostgresWorkflowDocumentsMixin._apply_local_release_copy` roept eerst het bestandsdeel aan en schrijft daarna de envelope met `state`, `published`, `release_id` en verwante velden via `write_bundle` naar PostgreSQL. Dat laatste is autoriteit en blijft.
2. **Auditevent `release_published`.** Dit wordt via `append_event(_ledger_path)` naar PG geschreven; de dubbelcheck `_local_ledger_has_release` leest via `read_events` uit PG. Dit blijft.
3. **Blob-verificatie in Azure.** `AzureAuthoritativePublicationConsole._projection_from_authority` roept `_verify_active_authority_sources` aan: bronbytes van elke actieve publicatie worden opnieuw uit Blob gelezen en op SHA-256 gecontroleerd. Dat gebeurt nu alleen omdat de projectie gebouwd wordt, bij publiceren, intrekken en starten. Verdwijnt de projectiebouw, dan verdwijnt deze fail-closed-controle stil. Hij wordt een expliciete stap op dezelfde drie momenten. D4 gebruikt de Durable-klasse en ziet deze controle dus niet.
4. **Projectievalidatie.** `_projection_from_authority` geeft `durable_publication_projection_invalid` of `…_incomplete` als `build_projection` blokkeert. Na de commit is dat geen poort meer, maar bij het starten wel een consistentiecheck. Beslis in de implementatie of die check expliciet blijft. Voorstel: ja, als controle bij het starten, zonder iets weg te schrijven.

## Bestaande deeltoestand na publicatie: gedrag behouden, niet oplossen

De canonical release wordt eerst gecommit. Daarna volgen, los daarvan, de envelope-status en het auditevent. Als die tweede stap faalt, geeft `publish` nu `durable_publication_local_copy_failed` terug terwijl de release al bestaat, en herstelt `reconcile_durable_publications` dat bij de volgende start. D5 houdt die herstelroute intact, zonder bestanden. Release en envelope in één transactie zetten is een lifecyclewijziging en valt buiten D5. Daarvoor komt een opvolgissue.

## Uitvoering in volgorde (één PR, aparte commits)

1. `_apply_local_release_copy` splitsen in een autoriteitsdeel (envelope en auditevent in PG) en een bestandsdeel. In de PG-topologie wordt alleen het autoriteitsdeel aangeroepen; de basistopologie blijft ongewijzigd tot D6.
2. De Blob-verificatie expliciet maken bij publiceren, intrekken en starten (Azure-klasse).
3. Schrijvers en lezers uit de tabellen hierboven weghalen uit de PG-mixins: `_mirror_*`, `_remirror_review_runtime`, `_project_committed_events` (alleen het spiegeldeel), `_ledger_mirror_tail_hash`, `bind_ledger_mirror`/`_mirror_events`, de terugvalkopieën in delete en commit, en de `_load_map`-aanroep in reload.
4. `StoreCommand` beperken tot transactie-eigenaarschap (`owner`, `fresh`, `poisoned`); de velden `snapshot_ids`, `bindings`, `envelopes`, `objects` en `events` en `defer_mirror_events` vervallen.
5. Herstel- en backuppaden aanpassen volgens B-D5-3.
6. D4: xfail weg, gifrun toevoegen, beide consoleklassen.

## Eindbewijs (Definition of Done)

- **Weigerrun:** runtime-map alleen-lezen en leeg, alle twaalf fases plus de D4b-fases voltooid, PG-toestand per fase gelijk aan de controlerun.
- **Gifrun:** runtime-map bevat alle spiegelbestanden van een eerdere run, bewust afwijkend gemaakt en leesbaar. Nul geregistreerde toegang, en de PG-toestand is gelijk aan de controlerun. Dit vangt lezers achter `exists()` of `is_file()`, die de weigerrun met lege map niet kan zien. Het delete-pad is daar het concrete voorbeeld van.
- Beide runs met `FastBadgePostgresCompleteWorkflowDurablePublicationConsole` én `FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole`, plus een Azure-negatieve case: een gewijzigde Blob-byte laat publiceren en starten falen.
- **Concurrency:** twee workers op dezelfde PG en dezelfde runtime-map, gelijktijdige review op één document; uitkomst gelijk aan `main`.
- **Herstart:** in de volgorde commit, crash, start mag geen half commando zichtbaar zijn.
- **Rollback (bewezen, niet aangenomen):** draai de D5-code door het lifecyclescenario, start daarna commit `629d63c` op dezelfde PG met de oude, verouderde runtime-map, en doorloop review, publish en withdraw. De PG-toestand en het Product API-antwoord moeten gelijk zijn aan een run zonder rollback. Aandachtspunt: de oude code bouwt envelopes, bindings en het ledger bij de constructor opnieuw op, en projectie en manifests via `reconcile_durable_publications`. `objects/*.jsonl` bouwt hij níet opnieuw op. De native rollbackproef registreert nul objectreads voor review/publish/withdraw. Het oude delete-pad leest ze wel als opaque bestandsbackup; dit is geen PG-authority en wordt niet als algemene nul-leesgarantie afgevinkt.
- **Herstel:** `backup_workflow_chain` gevolgd door `restore_workflow_chain` in een lege database, zonder runtime-bestanden, gevolgd door een consolestart en een lifecyclevervolg. Groen.
- Lex (aanvalsronde), Sherlock (begrensde review) en het gate-rapport van Argos vóór de merge.

## Rewrite-risk

Rewrite target: alle schrijvers en lezers van workflowspiegels, publicatieprojectie en releasemanifests in de volledige PG-topologie, volgens de dynamische en statische kaart hierboven.
Why local patching is insufficient: #667, #708 en #709 repareerden dezelfde foutklasse (kopie loopt uit de pas met PG); de weigerrun laat zien dat publiceren zonder bestanden nu faalt.
Current authority/writer/reader map: zie beide kaarten hierboven; authority is PostgreSQL (workflow en canonical) plus Blob (bronbytes).
Supported runtime topologies: Azure (Azure-klasse, 1–2 workers, 1 instance); lokaal en CI met volledig PG (Durable-klasse); de bestandsopstelling blijft ongewijzigd tot D6.
Persisted-state impact: geen wijziging in PostgreSQL-schema of -data; bestanden onder `/home/data/metis-console` blijven staan en worden niet meer gelezen of bijgewerkt.
Compatibility/migration plan: expand–contract; D5 stopt alleen met lezen en schrijven; bestanden opruimen is een aparte handmatige stap na backup en op Williams GO.
Rollback/recovery plan: B-D5-3; code-rollback naar `629d63c` bewezen in het eindbewijs; herstel via `backup_workflow_chain`/`restore_workflow_chain` zonder runtime-bestanden.
Cutover trigger: merge na het volledige eindbewijs en de reviewronde; uitrol alleen na afvinken van #695.
Cleanup/decommission criteria: geen spiegel- of projectiecode meer in de PG-mixins; `StoreCommand` zonder spiegelvelden; `store_remirror` en `store_command_ledger_divergence` verdwenen; herstel- en inventarisdocumentatie noemen de bestanden niet meer voor de PG-topologie.
Failure blast radius: alle consolecommando's in de PG-topologie, publiceren en intrekken inbegrepen, en de Blob-controle bij het starten in Azure; Product API niet.
Adversarial proof matrix: zie onder.

| Aanval | Verwacht |
|---|---|
| Afwijkende spiegel aanwezig en leesbaar (gifrun) | geen toegang; console toont PG-toestand |
| Runtime-map leeg en alleen-lezen (weigerrun) | alle fases voltooid |
| Lezer achter `exists()` (delete ongepubliceerd document) | gevangen door de gifrun |
| Hernoemen of verwijderen zonder `open()` | gevangen door de uitgebreide guard (D4b) |
| Gewijzigde Blob-byte in Azure-klasse | publiceren en starten falen fail-closed |
| Envelope-write faalt na release-commit | gedrag als `main`; herstel bij volgende start |
| Override of `getattr`-route in een van de 19 klassen | gevangen door de gifrun en de vastgepinde baseline |
| Twee workers, gelijktijdige review | uitkomst gelijk aan `main` |
| Rollback naar `629d63c` met verouderde map | PG-toestand en API-antwoord ongewijzigd |
| Herstel uit backup zonder runtime-bestanden | console start en lifecycle loopt door |

## Lifecycle

Lifecycle entity: WorkingRevision-opslag, review-ledger, bindings en de lokale publicatieweergave van een document (opslag, niet semantiek).
Lifecycle transition: geen nieuwe of gewijzigde transitie; publish, withdraw, successor en review lezen en schrijven alleen nog PG en Blob.
Initial durable state: PG en Blob als autoriteit, met parallelle kopieën op schijf (spiegels, projectie, manifests).
Trigger: elk consolecommando en elke start die nu een kopie bijwerkt of leest.
Authorization: ongewijzigd.
Validation: ongewijzigd; de Blob-verificatie blijft fail-closed en wordt een expliciete stap; geen validatie hangt nog van een schijfbestand af.
Mutable entities: ongewijzigd ten opzichte van `main`.
Immutable entities: gepubliceerde releases, bronsnapshots, het publicatieregister.
Workflow state before: in PG, met kopie op schijf.
Workflow state after: in PG, zonder kopie.
Release state before: in PG; envelope-status in PG en op schijf.
Release state after: in PG; envelope-status alleen in PG.
Serving state before: publicatieregister; projectiebestand als afgeleide kopie.
Serving state after: publicatieregister; geen projectiebestand.
Expected API result: Product API-antwoorden gelijk voor dezelfde PG-toestand.
Expected UI result: geen zichtbare wijziging; bestaande `local_projection`-waarden blijven behouden voor antwoordcompatibiliteit. Ze zijn geen bestands- of authoritygarantie.
Failure result: een PG- of Blob-fout faalt het commando zoals nu; er bestaat geen faalpad meer via workflowspiegels, publicatieprojectie of releasemanifests. Bestaande niet-spiegel-I/O zoals locks en broncache valt buiten deze verwijdering.
Restart result: start leest of schrijft geen workflowspiegels, publicatieprojectie of releasemanifests, voert de Blob-verificatie uit (Azure) en herstelt een deeltoestand na publicatie uit PG.
Recovery result: herstel via PG- en Blob-backup; bestanden zijn geen herstelbron.
Legacy-data result: bestaande bestanden blijven onaangeroerd en ongebruikt; oude manifests worden niet meer als bewijs gecontroleerd.
Required black-box scenario: ingest → review met four-eyes → publish → successor → publish → successor → withdraw → herstart → review opvolger, plus verwijderen van een ongepubliceerd document en starten via `build_app`; als weigerrun en als gifrun, met beide consoleklassen.
Explicit non-goals: bestandsopstelling (D6); release en envelope in één transactie (opvolgissue); de ledger-API zonder pad-sleutel; het opsplitsen van de 19 consoleklassen; het verwijderen van bestanden op `/home/data`.

## Afstemming met #695

#695 eist een backup met bewezen herstel vóór elke deploy. Als dat bewijs met de huidige code en `runtime_root` wordt geleverd, verandert D5 daarna de inhoud van de backup. Kies één van twee:

- #695-herstelbewijs opnieuw draaien op de D5-code vóór de eerste deploy; of
- D5 pas mergen nadat #695 is afgevinkt, en het herstelbewijs in D5 meenemen.

Mijn advies is het eerste. D5 verkleint wat er hersteld moet worden, en één herstelbewijs op de code die je uitrolt is sterker dan twee op verschillende codes.


## Verificatie en preciseringen bij aanmaken

Deze issueversie gebruikt de door William aangeleverde tekst als bron. B-D5-1,
B-D5-2 en B-D5-3 worden hiermee vastgelegd; de open bewijs- en ontwerpvragen
hieronder zijn bij het aanmaken niet als opgelost aangemerkt. D4b is inmiddels uitgevoerd op PostgreSQL 16, Python 3.12 en 3.13: per versie 8 groen en 2 verwachte xfails vóór D5. De historische exacte baseline blijft vastgelegd in `tests/fixtures/pg_mirror_baseline_629d63c.json`.

**Lokale kaart tegenover CI.** De lokale kaart is als samenvatting aangeleverd;
het genoemde ruwe lokale JSON is in deze sessie niet ontvangen. Vergelijking
met de definitieve D4-CI op head `3deb468fa0cd919a14e36ed7d3b83ffe5fdd6176`,
[run 39428489451](https://github.com/WilliamGomes41/Metis-DS/actions/runs/39428489451),
geeft op Python 3.12 en 3.13 dezelfde 56 combinaties van eigenaar,
spiegelfamilie en fase. Alle lokale toegangstuples komen terug in CI; CI
registreert daarnaast 36 read+write-tuples voor tijdelijke bestanden bij
atomische writes. Die vallen onder de hier expliciet gegeven betekenis van
“schrijven”; het zijn geen extra waargenomen lezers van bestaande inhoud.
Concrete lokale bestandsnamen, stacks en aantallen zijn zonder het ruwe lokale
bestand niet vergeleken. CI bevestigt dezelfde blokkade en acht onbereikte fases.

De ruwe definitieve CI-kaarten staan in de JUnit-artefacten
[Python 3.12](https://github.com/WilliamGomes41/Metis-DS/actions/runs/39428489451/artifacts/12266722849)
en [Python 3.13](https://github.com/WilliamGomes41/Metis-DS/actions/runs/39428489451/artifacts/12265874964).
Deze CI-bron wordt niet als de lokale run op `629d63c` gepresenteerd.
Fase-aliases: start=startup, acc=accounts-and-session, in1=ingest-v1,
rv1=review-v1-four-eyes, pub1=publish-v1, in2=successor-v2,
rv2=review-v2-four-eyes, pub2=publish-v2, in3=successor-v3,
wd=withdraw, herst=restart en rv3=resume-successor.

**Exacte D4b-baseline.** De tabel is een gegroepeerde weergave. De test moet
óf ruwe toegangsmodi afzonderlijk vastpinnen, óf de omzetting van read+write
naar schrijven expliciet maken en de ruwe feiten behouden. Nieuwe guardoperaties
en toegevoegde fases krijgen eveneens een exact gemeten verwachting op een
vastgepinde productie-SHA. Een naam van een bekende eigenaar is geen vrijstelling.
Voor letterlijk nul spiegeltoegang moet ook `exists/stat/is_file` worden
geïnstrumenteerd: de beschreven basiscommit doet ledger-stat zonder open.
Locks en broncache worden afzonderlijk geclassificeerd; “geen bestanden” is
in de lifecyclevelden daarom gepreciseerd tot de drie te verwijderen kopieën.

**Rollback: vastgestelde bewijsgrens.** De native proef op de echte checkout
`629d63c` doorloopt review/publish/withdraw op dezelfde PG-begintoestand met
verouderde spiegels. Beide consoleklassen leveren dezelfde genormaliseerde
PG-tabellen en gedecodeerde Product API-antwoorden als D5; geen objectread in
deze route. Dit is geen bewijs van byte-identieke HTTP-antwoorden of identieke
klok-/hashvelden tussen onafhankelijke vervolgruns.

De oude delete leest aanwezige objectbytes uitsluitend als opaque backup voor
bestandsherstel na PG-rollback. De bytes worden niet geparsed en bepalen geen
PG-write of procesobjecten. Een onleesbaar bestand kan oude delete blokkeren;
er is langs dit pad geen workflowverlies aangetoond. De algemene eis 'oude code
leest nooit objects' is weerlegd en wordt niet groen afgevinkt. De nul-toegangseis
voor D5 zelf blijft volledig gelden, inclusief delete. Deze expliciete oude
rollbackbeperking hoort bij Williams uiteindelijke mergereview; zij blokkeert
geen onafhankelijke implementatie of native bewijs op D5.

**Projectievalidatie: behouden bij implementatie.** Het voorstel bij
Gekoppelde autoriteit 4 is uitgevoerd zonder bestaande validatie te
verwijderen. Ook een projectiefout ná een canonical commit kan de huidige
publish-opdracht laten falen; hij kan de releasecommit dan niet meer terugdraaien.
De pure consistentiecheck blijft behouden op publish, withdraw/sync en startup,
zonder bestandsschrijven in PG. De bestaande failure-/restartsemantiek en
`local_projection`-antwoordwaarden blijven behouden.

**Broncorrecties.** De statische basiscommitrij is gecorrigeerd voor de
`objects=None`-tak; de Product API-rij onderscheidt real- en fixturemodus.
De ledger-dubbelcheck is bevestigd: de override in
`_PostgresRemainingWorkflowMixin` gebruikt `read_events` en daarmee PG.

`validate_change_contract.py` controleert aanwezigheid en consistentie van
velden. Een PASS daarvan bewijst geen complete runtimekaart, rollback of
herstel. Lex, Sherlock, Argos, William-GO en #695 blijven onverkort gelden.


## Vastgelegde implementatiekeuzes

- De pure projectievalidatie blijft op dezelfde grenzen als vóór D5 behouden:
  publish, withdraw/sync en startup. Zij schrijft in PG geen projectiebestand.
- Azure-bronverificatie is expliciet op die grenzen. De bestaande
  `azure_blob_source_sha256_mismatch` blijft fail-closed.
- `local_projection` behoudt de bestaande antwoordwaarden. Het bestaande
  `durable_publication_local_copy_failed` blijft voor de al bestaande
  release-commit/envelope-foutsplit behouden; atomair maken valt buiten D5.
- Native PG-transacties, savepoints en eventbuffers blijven eigenaar van
  rollback. Alleen de procesweergave wordt na een fout uit PG ververst.
- Alleen PG-recoverywrappers negeren `runtime_root`/`runtime_dest`. De generieke
  bestandsrecovery blijft beschikbaar voor de bestandsopstelling.
- De historische #708-projectie/tail-herbouwproeven zijn vervangen door
  PG-ledgerproeven met corrupte aanwezige kopieën en controle van de PG-keten.
  De bestaande savepoint-, concurrency-, auth- en foutproeven blijven bestaan.

De actuele verificatie en de begrensde reviewrapporten komen in
`docs/change-contracts/785-d5-verification.md`. Een groene native proef wordt
niet als productieherstelbewijs voor #695 aangemerkt.
