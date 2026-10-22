# D6b — PostgreSQL als enige runtime-autoriteit

**Status: geïmplementeerd op branch `claude/project-thread-zw16ht` op expliciete opdracht van William. Gepusht en als PR geopend met Williams akkoord (2026-10-22); niet mergen zonder zijn GO. Lex, Sherlock en Argos zijn nog niet uitgevoerd.**

Basis: `main` op `afcb37c` (D6a portie 19 gemergd).

Change class: A
Promise: De console start lokaal, in tests en in Azure uitsluitend op de volledige PostgreSQL-compositie; geen configuratie, CLI-commando of consoleklasse kan nog een bestandsopslag voor workflow- of canonical state kiezen of gebruiken.
Proof: Iedere combinatie van de oude selectors zonder PostgreSQL-configuratie wordt vóór opslagtoegang geweigerd; elke consoleklasse onder de volledige PG-compositie weigert te construeren zonder runtimebestanden te maken; `serve-console` en `console-account` starten de productieklasse en schrijven geen workflowbestanden; de volledige suite slaagt tegen PostgreSQL zonder PG-skips.
Touches lifecycle invariants: yes
Rewrite risk: high

## Besluiten

**B-D6b-1 Selectors.** De vijf `METIS_*_STORE`-variabelen kiezen niets meer. Leeg of `postgres` wordt geaccepteerd, zodat bestaande Azure-instellingen en een code-rollback blijven werken; iedere andere waarde (zoals `file`) weigert de start met `unsupported_<naam>`. Zonder `METIS_CANONICAL_DB_DSN` of de volledige managed-identity-set (`HOST`, `NAME`, `USER`) weigert de start met `postgres_authority_configuration_required`, ook buiten Azure.

**B-D6b-2 Eén compositie.** `console_asgi.build_app()` is de enige consolecompositie. `serve-console` en `console-account` roepen haar aan; `--source-store` en `--runtime` kiezen alleen lokale mappen (bronbytes, locks, telemetrie). `operations_console_app.create_app()` en de standaardconsole in `create_console_app()` zijn verwijderd.

**B-D6b-3 Productieguard.** `OperationsConsole.__init__` weigert iedere klasse zonder `_metis_complete_postgres_authority` (`postgres_workflow_authority_required`), en `DurablePublicationConsole` weigert een ontbrekende canonical store. Alleen de twee volledige PG-klassen (en hun FastBadge-varianten) zijn daarmee constructeerbaar.

**B-D6b-4 Contractstap.** Code die alleen in de bestandsopstelling bereikbaar was, is verwijderd in plaats van uitgeschakeld (zie kaart). De PG-mixins blijven de eigenaar; het opsplitsen van de consoleklassen blijft een non-goal, zoals in D5.

**B-D6b-5 Bestaande bestanden.** Er wordt niets op schijf verwijderd. Oude `accounts.json`, `envelopes.json`, `objects/*.jsonl`, ledger, projectie en manifests worden genegeerd. Lokale data gaat naar PostgreSQL met de bestaande expliciete scripts (`scripts/migrate_workflow_*_postgres.py`, `scripts/migrate_workflow_cutover_postgres.py`); die scripts lezen bestanden als eenmalige migratiebron en blijven bestaan.

## Autoriteits-, schrijver- en lezerskaart

Authority: PostgreSQL (workflow en canonical), Azure Blob (bronbytes in Azure), de lokale bronmap (bronbytes lokaal). Ongewijzigd ten opzichte van de PG-topologie op `main`.

| Pad op `main` | Bereikbaar in PG-topologie op `main` | D6b |
|---|---|---|
| `validate_workflow_store_configuration()` → `False` en `DurablePublicationConsole(**common)` in `build_app` | nee (alleen zonder selectors) | verwijderd; PG onvoorwaardelijk |
| `cli serve-console` / `console-account` met `OperationsConsole` op JSON | nee (geweigerd bij PG-selectors) | via `build_app` |
| `operations_console_app.create_app()` / `create_console_app(None)` | nee | verwijderd |
| `OperationsConsole.__init__` leest `accounts.json`, `sessions.json`, `envelopes.json`, `publish_authorizations.json` via `_load_map` | nee (`_startup_local_mirror_is_authority` → `False` in PG-mixins; cutover-identity) | verwijderd; lege procesweergaven die de mixins verversen |
| Identity-mixin `migrate_legacy_if_empty` bij start | nee (cutover-store; alleen met de niet-cutover store) | startimport verwijderd; expliciet script blijft |
| Basismethoden voor accounts/sessies (`create_account`, `authenticate`, `session_account`, `logout`, `list_accounts`, `list_reviewer_accounts`, `assign_roles`, `_account`, sessie-locks/`_with_sessions`, `_save_accounts/_save_sessions`) | nee (PG-identity-mixin overschrijft zonder `super()`) | verwijderd |
| Basismethoden voor envelopes/bindings/objecten (`_save_envelopes`, `_save_bindings`, `_reload_store_locked`, `_load_objects`, `_save_objects`, `objects_revision`, `refresh_objects_expected_revision`, `snapshot_objects_and_revision`, `_objects_path`, objectlocks, `_commit_prepared_store`, `_rollback_store_files`) | nee (documents-/reviewmixins overschrijven zonder `super()`) | verwijderd |
| Basis-`_heading_batch_mutation` legt object-/envelope-/bindingbestanden vast en herstelt ze bij een fout via `_rollback_store_files` | **ja**: via `super()` vanuit de documentsmixin; bij een fout schreef het oude `envelopes.json`/`publish_authorizations.json` en verwijderde het een objectbestand | alleen nog lock, mutabiliteitscontrole en batchmarkering; de native PG-transactie is de enige rollback |
| Basis-`_delete_unpublished_snapshot_locked` verwijdert `objects/<id>.jsonl` | nee (spiegelvlag `False`) | tak verwijderd; PG-delete ongewijzigd |
| Basis-`_atomic_snapshot_mutation` en de `ReviewClosureConsole`-variant | nee (reviewmixin overschrijft zonder `super()`) | verwijderd |
| Basis-`_publish_locked` (projectie, manifest, envelope op schijf) en de `store is None`-terugval in `DurablePublicationConsole` | nee (canonical store altijd gezet) | verwijderd; canonical store verplicht |
| `DurablePublicationConsole._apply_local_release_copy`, `_read_optional`, `_restore_optional`, `_manifest_from_release`, bestandsprojectie bij reconciliatie | nee (documentsmixin overschrijft `_apply_release_state`) | verwijderd |
| Basis-`snapshot_is_published` met projectiebestand | nee (canonical store is exclusieve autoriteit) | verwijderd |
| Basis-`_archive_prior_objects`/`prior_object_audit_history` met `class_change_history/*.jsonl` | nee (remaining-mixin) | verwijderd |
| `_durable_receipt` fsync van `objects/*.jsonl` en `envelopes.json` | nee | tak verwijderd; fsync van lokale bronbytes blijft zonder Blob |
| `correct_object` herlaadt `accounts.json` zonder identity store | nee | verwijderd |
| Refusal-audit: JSONL-store met `file_store_allowed()` en `append_refusal` | nee (PG-tabel) | verwijderd; zonder PG `RefusalStoreUnavailable` |
| Evidence-export leest refusal-JSONL zonder PG | nee | alleen PG |
| Topologiegrens: twee workers vereisen de vijf selectors = `postgres` | ja | alleen nog Blob = `azure`; PG is altijd vereist |
| `azure_console_startup.sh` eist selectors = `postgres` | ja | vervallen; de Python-start weigert zonder PG |

Blijft bewust bestaan: het proces-gedeelde `store.lock`, de lokale bronmap, telemetrie in de runtime-map, `_ledger_path` als sleutel voor de geregistreerde PG-eventbackend (D5-non-goal), `runtime_data_inventory_v1` en de generieke bestandsonderdelen van `publication_chain_recovery_v1` (alleen offline export/herstel van oude bestanden; het operationele script gebruikt al uitsluitend `backup_workflow_chain`/`restore_workflow_chain`), en `AuditRegistry` (geen runtime-schrijver sinds de Audit-kamer is gesloten).

## Rewrite-risk

Rewrite target: alle code en configuratie waarmee de console een bestandsopslag voor workflow- of canonical state kan kiezen of gebruiken, volgens de kaart hierboven.
Why local patching is insufficient: D6a heeft alle tests naar de productiecompositie gebracht; zolang de bestandsopstelling bestaat, blijven er twee runtimetopologieën met eigen startpaden, terugvallen en testmarkeringen, en kan een lege configuratie stil op bestanden starten.
Current authority/writer/reader map: zie de kaart; autoriteit is PostgreSQL plus Blob, ongewijzigd.
Supported runtime topologies: Azure (Azure-klasse, 1–2 workers, 1 instance), lokaal en CI met volledig PG (Durable-klasse). De bestandsopstelling bestaat niet meer.
Persisted-state impact: geen schema- of datawijziging in PostgreSQL of Blob. Bestanden op schijf blijven onaangeroerd en ongebruikt.
Compatibility/migration plan: expand–migrate–contract; D2–D5 en D6a waren expand/migrate, D6b is de contractstap. Lokale bestandsdata gaat expliciet via de bestaande migratiescripts. Azure-instellingen blijven ongewijzigd geldig.
Rollback/recovery plan: code-rollback naar `afcb37c` vereist geen datawijziging: de PG-toestand is dezelfde en de selectors in Azure blijven `postgres`. Verwijder de selectors daarom niet uit Azure-instellingen zolang rollback mogelijk moet blijven. Herstel blijft `backup_workflow_chain`/`restore_workflow_chain`.
Cutover trigger: merge na groene volledige suite zonder PG-skips, CI op beide Python-versies en de reviewronde (Lex, Sherlock, Argos) met Williams GO.
Cleanup/decommission criteria: geen `file_topology`-marker of -test meer; geen `_startup_local_mirror_is_authority`, `_load_map`, bestandsrefusal-store of standaardconsole; de enige constructeerbare consoleklassen zijn de volledige PG-klassen; docs noemen geen lokale bestandsopstelling meer als ondersteunde start.
Failure blast radius: iedere consolestart en de twee lokale CLI-commando's. Een lokale ontwikkelaar zonder PostgreSQL kan de console niet meer starten. Product API (`serve-api`) en `serve` vallen erbuiten.
Adversarial proof matrix: zie onder.

| Aanval | Verwacht | Bewijs |
|---|---|---|
| Lege configuratie lokaal of in Azure | start geweigerd vóór credentials, opslag of mapcreatie | `test_no_selector_combination_starts_without_postgres` (alle 32 combinaties × lokaal/Azure) |
| Oude selector op `file` of een tikfout | start geweigerd | `test_retired_selector_with_another_value_is_refused` |
| Onvolledige managed-identity-configuratie | start geweigerd | `test_incomplete_managed_identity_configuration_refused` |
| `serve-console`/`console-account` zonder PG | geweigerd, niets geserveerd | `test_local_cli_refuses_without_postgres` |
| `serve-console`/`console-account` met PG | productieklasse, geen workflow-JSON in de runtime-map | `test_local_cli_uses_the_production_composition` |
| Directe constructie van basis-, Durable-, Azure- of tussenliggende PG-klassen | `postgres_workflow_authority_required` / `canonical_publication_store_required`, geen runtimebestanden | `test_no_console_class_without_complete_postgres_authority_constructs` (subprocess, zonder testguard) |
| Afwijkende spiegelbestanden aanwezig (gifrun) | geen toegang | bestaande D4/D5-proef `test_pg_console_without_disk_mirrors.py`, beide klassen |
| Mislukte heading-batch | alleen PG-rollback, geen bestandscompensatie | bestaande A08-proeven op PG |
| Refusal zonder PG-store | `RefusalStoreUnavailable`, geen JSONL | refusal-audit-proeven |
| Rollback naar `afcb37c` | ongewijzigde PG-toestand; oude code start met dezelfde selectors | geen schemawijziging; niet apart uitgevoerd (zie open punten) |

## Lifecycle

Lifecycle entity: de opslaggrens van WorkingRevision, review, bindings, identiteit en publicatie (opslag, niet semantiek).
Lifecycle transition: geen nieuwe of gewijzigde transitie; alleen de bestandsopstelling waarin dezelfde transities op JSON liepen, verdwijnt.
Initial durable state: PostgreSQL en Blob als autoriteit in de PG-topologie; daarnaast een lokale bestandsopstelling die bij lege configuratie startte.
Trigger: consolestart, `serve-console`, `console-account`.
Authorization: ongewijzigd.
Validation: ongewijzigd, plus de configuratie- en constructieweigering hierboven.
Mutable entities: ongewijzigd ten opzichte van `main` (PG-topologie).
Immutable entities: gepubliceerde releases, bronsnapshots, het publicatieregister.
Workflow state before: PostgreSQL, of JSON-bestanden in de bestandsopstelling.
Workflow state after: alleen PostgreSQL.
Release state before: canonical PostgreSQL; in de bestandsopstelling ook manifests/projectie op schijf.
Release state after: alleen canonical PostgreSQL.
Serving state before: publicatieregister; in de bestandsopstelling een projectiebestand.
Serving state after: publicatieregister.
Expected API result: ongewijzigd voor dezelfde PG-toestand.
Expected UI result: ongewijzigd in de PG-topologie; zonder PG start de console niet.
Failure result: zonder PG-configuratie een expliciete startweigering; een PG-fout faalt het commando zoals op `main`; een mislukte heading-batch schrijft geen bestanden meer.
Restart result: start leest of schrijft geen workflowbestanden, ook niet de identiteit.
Recovery result: herstel via PG- en Blob-backup; bestanden zijn geen herstelbron.
Legacy-data result: bestaande bestanden blijven onaangeroerd; migratie alleen via de expliciete scripts.
Required black-box scenario: de bestaande D4/D5-weiger- en gifrun en de lifecycleproeven (ingest → review → publish → successor → withdraw → herstart) op beide klassen, plus de nieuwe start- en CLI-proeven.
Explicit non-goals: de consoleklassen opsplitsen; `runtime_data_inventory_v1`, generieke bestandsexport in `publication_chain_recovery_v1` en `AuditRegistry` verwijderen; bestanden op `/home/data` of lokaal verwijderen; selectors uit Azure-instellingen halen; de ingest-characterization op PostgreSQL herbouwen.

## Testwijzigingen

- 46 `file_topology`-gevallen in 23 modules verwijderd, plus de marker en de afhandeling in `tests/conftest.py`.
- `tests/characterization/test_ingest.py` en `test_ingest_boundaries.py` (84 goldens) legden de JSON-boom van de bestandsopstelling vast en zijn verwijderd, met hun goldens, de CI-mutatiestap voor ingest en de bijbehorende baseline-run. De reviewruimte-characterization blijft op PostgreSQL. **Open:** ingest-characterization op PostgreSQL herbouwen is een aparte portie.
- `tests/test_718_workflow_topology.py` toetst nu de nieuwe weigering, de CLI via de productiecompositie en de productieguard.
- `scripts/probes/probe_source_repair_mapping.py` (A09) bouwde een losse `ReviewClosureConsole` op bestanden; hij draait nu via `build_app` op een eigen PostgreSQL-database (`METIS_PROBE_ADMIN_DSN`) en slaagt met dezelfde uitkomst.

## Open punten vóór merge

- CI op Python 3.12 en 3.13. Lokaal (Python 3.13, PostgreSQL 16) gaf de volledige suite 5528 geslaagd, 6 gefaald, 29 overgeslagen, nul PostgreSQL-skips. Vier fouten waren verouderde verwijzingen naar verwijderde bestandscode en zijn hersteld. `test_security_sandbox::test_tested_code_cannot_overwrite_control_files` faalt ook op main omdat de container als root draait. `test_native_stall_reserves_before_call_and_recovers_same_source` was een eenmalige timingfout en slaagt bij herhaling.
- Rollback-proef naar `afcb37c` op dezelfde PG-toestand niet apart uitgevoerd; er is geen schemawijziging.
- Lex (aanvalsronde), Sherlock (begrensde review) en Argos (gate) vóór de merge; Williams GO.
