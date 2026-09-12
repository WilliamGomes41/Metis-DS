# Runtime-data en publicatieketen: backup, restore en integriteitscontrole

De productie-authority is niet langer `/home/data/metis-console`.

Na de volledige workflow-cut-over bestaat de authority uit:

1. Azure Blob voor immutable canonical source bytes;
2. PostgreSQL publicatieschema voor canonical object versions, bronlineage, releases, release-items, publication registry en publication audit-events;
3. PostgreSQL `workflow`-schema voor accounts, sessies, documenten/envelopes, work objects, review-events, publish authorizations, Audit-records en versleutelde Audit-secretpayloads.

`/home/data/metis-console` bevat daarna alleen rebuildable compatibility mirrors, caches, lokale bronkopieën en afgeleide artefacten. Het is dan **geen workflow-authority** en geen authority voor gepubliceerde kennis.

## Authority-matrix

| Gegeven | Authority na volledige cut-over | Lokale `/home/data`-kopie |
| --- | --- | --- |
| accounts / rollen / sessies | PostgreSQL `workflow` | compatibility mirror waar nog aanwezig |
| documenten / envelopes | PostgreSQL `workflow` | `envelopes.json` is mirror |
| work objects | PostgreSQL `workflow` | `objects/*.jsonl` is mirror |
| review ledger | PostgreSQL `workflow` | `review_ledger.jsonl` is mirror |
| publish authorizations | PostgreSQL `workflow` | `publish_authorizations.json` is mirror |
| klassewijzigingshistorie | document-envelope in PostgreSQL `workflow` | oude `class_change_history/*.jsonl` alleen migratiebron |
| Audit-records | PostgreSQL `workflow` | oude `audits/*.json` alleen migratiebron |
| versleutelde Audit LLM-key | PostgreSQL `workflow` | oude `audit_secrets/llm_api_key.json` alleen migratiebron |
| canonical kennis + releases + registry | PostgreSQL publicatieschema | geen authority-kopie |
| immutable bronbytes | Azure Blob | lokale freeze is cache/werkexemplaar |
| release manifests | PostgreSQL releasegegevens zijn authority | lokale manifests zijn rebuildable release mirrors |
| Product API projectie | canonical/publication PostgreSQL | `published_projection.jsonl` is rebuildable derived output |

De deployment-secret `METIS_AUDIT_SECRET_KEY` blijft buiten de database. PostgreSQL bewaart alleen de reeds versleutelde Audit-secretpayload.

## Expliciete workflow-migratie

Startup importeert nooit stil lokale state. De migratievolgorde blijft expliciet:

1. `002_workflow_schema.sql`;
2. `003_workflow_document_envelope_payload.sql`;
3. `004_workflow_review_authority.sql`;
4. `005_workflow_remaining_authority.sql`;
5. identity/accounts/sessions migreren;
6. documents/objects migreren en document-cut-over voorbereiden;
7. review ledger + publish authorizations migreren;
8. `scripts/migrate_workflow_remaining_postgres.py` uitvoeren voor Auditstate, Audit-secretpayload en klassewijzigingshistorie;
9. pas na verificatie de bijbehorende `METIS_WORKFLOW_*`-schakelaars activeren.

Een ontbrekend klassehistoriebestand, afwijkende object-ID-volgorde of conflicterende bestaande PostgreSQL-state blokkeert de migratie fail-closed.

De migratie verplaatst workflow-authority naar een **managed database**. Dat betekent niet dat meerdere App Service-instances al ondersteund zijn; die topologie wordt pas in stap 6 geopend na expliciet concurrencybewijs.

## Lokale runtime-inventaris

`inventory_runtime_data()` in `src/runtime_data_inventory_v1.py` blijft beschikbaar voor bestaande lokale bestanden. Die inventaris is na de volledige cut-over nadrukkelijk geen authority-map. De bestanden zijn bruikbaar voor diagnostiek, rollback tijdens migratie en het reconstrueren/controleren van rebuildable lokale kopieën.

Historisch rapporteert de inventaris onder meer:

- `accounts.json`;
- `envelopes.json` en lokale source freezes;
- `review_ledger.jsonl`;
- `objects/*.jsonl`;
- `publish_authorizations.json`;
- `release_manifests/*.json`;
- `published_projection.jsonl`.

Na volledige cut-over mogen deze bestanden niet worden gebruikt als fallback wanneer PostgreSQL leeg, onbereikbaar of afwijkend is.

## Publicatieketen

Voor gepubliceerde kennis blijft de kern dezelfde:

- PostgreSQL publicatiegegevens worden transactioneel vastgelegd;
- Azure Blob bevat de exacte immutable bronbytes;
- release manifests en Product API projecties zijn afgeleide lokale kopieën en kunnen uit de authority worden opgebouwd;
- lokale kopieën mogen nooit een nieuwere of afwijkende PostgreSQL-publicatie terugdraaien.

`DurablePublicationConsole` reconcilieert release manifests en de Product API-projectie vanuit PostgreSQL. In de volledige workflowmodus wordt ook de gepubliceerde envelope-status teruggeschreven naar de PostgreSQL workflow-authority. De lokale `envelopes.json` blijft daarbij alleen mirror.

## Publicatieketen-backup

`src/publication_chain_recovery_v1.py` maakt een verifieerbare backup van de gepubliceerde keten met:

- canonical/publication PostgreSQL-tabellen;
- iedere vanuit `source_snapshots` bereikbare Azure Blob;
- optioneel de lokale runtimekopieën;
- `chain_manifest.json` met hashes.

De database-export gebeurt in een `REPEATABLE READ, READ ONLY`-transactie. Integriteitscontrole valideert onder meer objecthashes, source lineage, release-items, registry, Blob-locators en Blob read-back.

Release manifests kunnen aanvullend worden gecontroleerd wanneer zij lokaal aanwezig zijn, maar zijn geen zelfstandige authority en mogen niet nodig zijn om een geldige PostgreSQL-publicatie te bewijzen.

## Belangrijke recovery-grens voor de workflow-cut-over

De bestaande `publication_chain_recovery_v1.py` dekt het canonical/publication PostgreSQL-schema, Blob en lokale runtimekopieën. De nieuw gedeelde `workflow`-tabellen vallen nog niet onder die production recovery-adapter.

Daarom geldt vóór Azure-activatie van de volledige workflow-cut-over nog een aparte releasevoorwaarde: workflow PostgreSQL backup/restore en restore-integriteit moeten expliciet worden toegevoegd en getest. Totdat dat bewijs bestaat, is de nieuwe code wel mergeable/opt-in, maar is de volledige production cut-over nog niet operationeel herstelbewezen.

## `--clean true`

`az webapp deploy --clean true` wist de deployment-managed `wwwroot`, niet `/home/data`. Dat blijft nuttig omdat lokale caches/mirrors niet bij iedere deployment hoeven te verdwijnen. Hun voortbestaan is echter niet meer vereist voor correctness wanneer alle workflow stores zijn geactiveerd.

## Topologie

De één-worker/één-instance-beperking blijft voorlopig actief:

- one Gunicorn worker;
- one instance;
- sequential writes.

Elke andere multi-writerconfiguratie, waaronder meerdere App Service-instances die tegelijk schrijven, blijft **out of bound** totdat stap 6 die beperking expliciet vervangt met bewezen PostgreSQL-concurrencygedrag.

Dat is nu geen gevolg meer van een gewenste lokale workflow-authority, maar een expliciete veiligheidsgrens totdat stap 6 multi-instance/concurrencybewijs levert voor de nieuwe PostgreSQL-paden. De beperking mag pas worden verwijderd nadat gelijktijdige document-, review-, authorization-, Audit- en sessiemutaties aantoonbaar geen lost updates, dubbele ledgerketens of stille overschrijvingen veroorzaken.

## Herstelbewijs

De bestaande deterministische publicatieketentests blijven bewijs voor canonical/publication + Blob-recovery. Zij zijn geen bewijs voor volledige workflow recovery en ook geen echte production recovery drill.

Voor production readiness blijven daarom twee afzonderlijke bewijzen nodig:

1. workflow PostgreSQL backup/restore inclusief de nieuwe `workflow`-tabellen;
2. een echte recovery drill tegen Azure PostgreSQL en Azure Blob.
