# Runtime-data en publicatieketen: backup, restore en integriteitscontrole

De herstelgrens voor het eindproduct is niet langer alleen `/home/data/metis-console`. De gepubliceerde keten bestaat uit drie samenhangende delen:

1. Azure Blob bevat de immutable canonical source bytes;
2. PostgreSQL bevat canonical object versions, bronlineage, releases, release-items, publication registry en audit-events;
3. `/home/data/metis-console` bevat lokale console-/workflowstate en afgeleide herstelartefacten, waaronder publish authorizations en release manifests.

Een backup of restore is pas geldig wanneer deze drie delen samen aantoonbaar consistent zijn.

## Runtime-inventaris van `/home/data/metis-console`

De lokale console-runtime (Azure default `CONSOLE_DATA_ROOT=/home/data/metis-console`) bevat deze categorieën:

| Categorie | Pad onder de data-root |
| --- | --- |
| accounts / roles | `output/runtime/operations-console/accounts.json` |
| document snapshots | `output/runtime/operations-console/envelopes.json` plus `sources/private` |
| review decisions and audit ledger | `output/runtime/operations-console/review_ledger.jsonl` |
| canonical work objects | `output/runtime/operations-console/objects/*.jsonl` |
| publication authorizations | `output/runtime/operations-console/publish_authorizations.json` |
| release manifests | `output/runtime/operations-console/release_manifests/*.json` |
| derived projections | `output/runtime/operations-console/published_projection.jsonl` |

Functie: `inventory_runtime_data()` in `src/runtime_data_inventory_v1.py`.

Deze runtimebestanden zijn niet de authority voor gepubliceerde kennis. PostgreSQL en Azure Blob zijn dat wel. De runtimebackup blijft nodig om de console-/reviewstaat en lokale releasebewijzen gecontroleerd te kunnen herstellen.

## Volledige publicatieketen-backup

`src/publication_chain_recovery_v1.py` voegt de eindproduct-backup toe. `backup_publication_chain()` maakt één controleerbaar archief met:

- een transactioneel consistente, logische PostgreSQL-snapshot van:
  - `canonical_object_versions`;
  - `source_snapshots`;
  - `canonical_object_sources`;
  - `publication_releases`;
  - `publication_release_items`;
  - `publication_registry`;
  - `audit_events`;
- iedere Blob die vanuit `source_snapshots` bereikbaar is, met de originele content-addressed locator en SHA-256;
- de runtimebackup, inclusief publish authorizations en release manifests;
- `chain_manifest.json` met SHA-256 van de database-export, iedere Blob en het runtime-archief.

De database-export gebeurt in een `REPEATABLE READ, READ ONLY`-transactie. Daarmee worden objectversies, releases, registry en audit-events uit één consistente database-snapshot gelezen.

Voor het archief wordt geschreven, voert de ketenbackup een live integriteitscontrole uit. Een ontbrekende Blob, afwijkende SHA-256, inconsistente release-itemhash, ontbrekende source lineage of inconsistente registry blokkeert de backup.

## Gecontroleerde restore

`restore_publication_chain()` herstelt alleen naar een lege database en, wanneer runtime-state wordt teruggezet, naar een lege runtime-root.

De volgorde is bewust:

1. valideer het volledige backup-archief en alle opgenomen hashes;
2. herstel iedere immutable Blob en laat de Blob-adapter de bytes opnieuw teruglezen/verifiëren;
3. herstel de lokale runtimebackup;
4. herstel PostgreSQL in één transactie;
5. exporteer de herstelde database opnieuw en vergelijk de volledige tabelinhoud met de backup;
6. voer opnieuw de ketenintegriteitscontrole uit tegen PostgreSQL + Blob + release manifests.

PostgreSQL wordt dus als laatste authority hersteld. Als Blob-restore faalt, wordt de publication registry niet teruggezet en kan er geen half herstelde actieve publicatie ontstaan.

## Integriteitscontrole

`live_publication_chain_integrity()` / `check_chain_integrity()` controleert onder andere:

- canonical JSON ↔ canonical content hash;
- canonical object version ↔ source snapshot;
- source snapshot SHA-256 ↔ Azure Blob locator;
- Blob read-back ↔ SHA-256;
- release item ↔ exacte object ID + versie + content hash;
- publication registry ↔ bestaande gepubliceerde release + release item;
- `release_published` audit-event ↔ snapshot ID + bronhash + Blob locator;
- release manifest ↔ dezelfde releaseversie, snapshot ID, bronhash en immutable locator.

De controle is fail-closed: ieder verschil levert `ok: false` op en een restore wordt niet succesvol verklaard.

## Lokale runtimebackup

Voor uitsluitend lokale console-/workflowstate blijft `export_runtime_data()` beschikbaar:

```bash
python -c "from pathlib import Path; from src.runtime_data_inventory_v1 import export_runtime_data; export_runtime_data(Path('/home/data/metis-console'), Path('/tmp/metis-console-runtime.zip'))"
```

Het archief bevat alleen allowlisted relatieve paden en een `inventory_manifest.json` met SHA-256 per bestand. Restore controleert nu ook vóór schrijven dat de leden exact overeenkomen met het manifest en dat iedere memberhash klopt; na restore wordt `integrity_check()` automatisch uitgevoerd.

Dit lokale archief alleen is geen volledige productiebackup. Voor disaster recovery van gepubliceerde kennis moet de publicatieketen-backup worden gebruikt.

## `--clean true` wist wwwroot, niet runtime-data

`az webapp deploy --clean true` wist `wwwroot` (`/home/web_sierra/wwwroot`). Runtime-data leeft onder `/home/data` (inclusief `/home/data/metis-console`). `apply_clean_wwwroot()` bewaakt die grens: wwwroot-inhoud weg, `/home/data` onaangeroerd. Deployment packaging schrijft niet naar `/home/data` en neemt runtime-data niet op in de applicatie-ZIP.

## Topologie en authority-grens

De lokale console-write state blijft vooralsnog gebonden aan één ondersteunde writer-topologie:

- one Gunicorn worker (`scripts/azure_console_startup.sh` pins `gunicorn -w 1`);
- one instance (`CONSOLE_INSTANCE_COUNT=1` or unset);
- sequential writes (`CONSOLE_WRITE_MODE=sequential` or unset).

Runtime assert: `src/topology_bound_v1.py` / `assert_supported_topology()`.

Deze beperking geldt niet meer als opslagmodel voor gepubliceerde kennis: canonical publicatie, releases en publication registry zijn PostgreSQL-authority; immutable bronbytes zijn Azure Blob-authority. `/home/data` is alleen console work state/cache/derived recovery state.

Meerdere gelijktijdige consolewriters vereisen nog steeds verdere migratie van de resterende mutable workflowstate (accounts/envelopes/bindings/sessions/review writes) naar een gedeelde transactionele store.

## Aantoonbaar herstelbewijs

`tests/test_publication_chain_recovery_v1.py` bevat een end-to-end roundtrip met geïsoleerde test-adapters:

- start met één gepubliceerde canonical object version, source snapshot, release, release item, active registry entry en release audit-event;
- backup van database + Blob + runtime/release manifest;
- restore naar lege Blob-store + lege database + lege runtime-root;
- vergelijking van herstelde registry en release-items met de oorspronkelijke staat;
- nieuwe Blob read-back/SHA-256-controle na restore;
- nieuwe release-manifestcontrole na restore;
- bewijs dat een Blob-writefout de database-restore niet laat committen;
- detectie van gemanipuleerde release hashes, Blob-bytes en backup-archiveleden.

Dit test het herstelprotocol deterministisch zonder afhankelijk te zijn van live Azure-resources. Daarnaast blijft een echte production recovery drill tegen Azure PostgreSQL en Azure Blob vereist voordat disaster recovery operationeel als bewezen kan worden beschouwd.
