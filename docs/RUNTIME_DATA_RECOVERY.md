# Runtime-data: inventaris, backup, restore en `--clean true`

Protocol v2.22 golf D. Geen grote databasemigratie. `publish()` blijft
G2-BLOCKED. MUST NOT SSH-wipe van `/home/data` als productpad.

## Inventaris van `/home/data/metis-console`

De console-runtime (Azure default `CONSOLE_DATA_ROOT=/home/data/metis-console`)
bevat deze categorieën:

| Categorie | Pad onder de data-root |
| --- | --- |
| accounts / roles | `output/runtime/operations-console/accounts.json` |
| document snapshots | `output/runtime/operations-console/envelopes.json` plus `sources/private` |
| review decisions and audit ledger | `output/runtime/operations-console/review_ledger.jsonl` |
| canonical objects | `output/runtime/operations-console/objects/*.jsonl` |
| derived projections | `output/runtime/operations-console/published_projection.jsonl` |

Functie: `inventory_runtime_data()` in `src/runtime_data_inventory_v1.py`.

## Export / backup

```bash
python -c "from pathlib import Path; from src.runtime_data_inventory_v1 import export_runtime_data; export_runtime_data(Path('/home/data/metis-console'), Path('/tmp/metis-console-backup.zip'))"
```

Het archief bevat alleen allowlisted relatieve paden en een
`inventory_manifest.json` met SHA-256 per bestand. `..` en extra slashes
worden geweigerd vóór iedere filesystem-join.

## Gecontroleerde restore

Restore MUST naar een schone omgeving. Een niet-lege doelmap wordt geweigerd.

```bash
python -c "from pathlib import Path; from src.runtime_data_inventory_v1 import restore_runtime_data; restore_runtime_data(Path('/tmp/metis-console-backup.zip'), Path('/home/data/metis-console-restore'))"
```

Daarna `integrity_check()` tegen het manifest. Afwijkende of ontbrekende
bytes falen fail-closed.

## `--clean true` wist wwwroot, niet runtime-data

`az webapp deploy --clean true` wist `wwwroot` (`/home/web_sierra/wwwroot`).
Runtime-data leeft onder `/home/data` (inclusief `/home/data/metis-console`).
`apply_clean_wwwroot()` bewijst die grens: wwwroot-inhoud weg, `/home/data`
onaangeroerd. MUST NOT SSH-wipe van `/home/data`. Packaging schrijft niet
naar `/home/data` en stopt runtime-data uit de ZIP.

## Migratiegrens (geen grote databasemigratie)

De huidige store is één-instance filesystem JSON/JSONL onder
`/home/data/metis-console`. Dat is voldoende voor één App Service-instance
en sequentiële reviewer-writes.

Een **managed database** wordt vereist vóór:

- meerdere App Service-instances (geen gedeelde lokale schijf);
- gelijktijdige multi-reviewer-writes (accounts, ledger, objecten, projectie).

Deze golf migreert die store niet. Geen grote databasemigratie.
