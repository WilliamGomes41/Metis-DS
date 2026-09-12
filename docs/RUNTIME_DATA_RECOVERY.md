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

Startup importeert geen lokale authority-state meer stil in PostgreSQL. De migratievolgorde is expliciet:

1. `002_workflow_schema.sql`;
2. `003_workflow_document_envelope_payload.sql`;
3. `004_workflow_review_authority.sql`;
4. `005_workflow_remaining_authority.sql`;
5. `scripts/migrate_workflow_identity_postgres.py --runtime <runtime>` voor accounts/sessies;
6. `scripts/migrate_workflow_documents_postgres.py --runtime <runtime>` en daarna document-cut-over voorbereiden;
7. review ledger + publish authorizations expliciet migreren;
8. `scripts/migrate_workflow_remaining_postgres.py` uitvoeren voor Auditstate, Audit-secretpayload en klassewijzigingshistorie;
9. pas na verificatie de bijbehorende `METIS_WORKFLOW_*`-schakelaars activeren.

Een ontbrekend klassehistoriebestand, afwijkende object-ID-volgorde of conflicterende bestaande PostgreSQL-state blokkeert de migratie fail-closed.

De migratie verplaatst workflow-authority naar een **managed database**. Dit is bewust een reeks kleine, omkeerbare stappen en **geen grote databasemigratie**. Het doel hiervan is uiteindelijk meerdere App Service-instances veilig dezelfde gedeelde authority te laten gebruiken; het aanzetten van meerdere instances is echter een aparte topology-wijziging.

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

## Volledige recoveryketen

De operator-CLI `scripts/publication_chain_recovery.py` gebruikt de bestaande publication-chain archive en Blob restore-guard, uitgebreid met de volledige `workflow`-authority.

De database-export bevat nu twee delen in dezelfde `database.json`:

- `tables`: canonical/publication PostgreSQL;
- `workflow_tables`: accounts, sessies, documenten, reviewers, objects, review-events, authorizations, audits en Audit-secretpayloads.

De export gebeurt in één `REPEATABLE READ, READ ONLY` PostgreSQL-transactie. Daardoor horen workflow- en publicatiestate bij exact dezelfde databasesnapshot.

De restorevolgorde blijft fail-closed:

1. backup-archive en hashes controleren;
2. immutable Blob-bytes herstellen en teruglezen;
3. optionele lokale mirrors herstellen;
4. workflow + canonical/publication PostgreSQL in **één database-transactie** herstellen;
5. database opnieuw exporteren en roundtrip vergelijken;
6. canonical/publication-integriteit én workflow-integriteit opnieuw bewijzen.

PostgreSQL wordt dus pas authoritative nadat de bronbytes aanwezig en gecontroleerd zijn.

## Workflow-integriteitsbewijs

`src/workflow_chain_recovery_v1.py` controleert aanvullend:

- referentiële identiteit van accounts, sessies, documenten en reviewers;
- dat ieder document een volledige `envelope_payload` heeft;
- objectvolgorde (`position`) en authorization-volgorde;
- snapshot- en reviewerreferenties;
- de volledige review-ledger hash-chain, inclusief exacte `event_payload`-hash;
- Audit-record creator-relaties en JSON payloads;
- aanwezigheid en vorm van versleutelde Audit-secretpayloads.

Een checksum-geldige archive waarin een reviewevent inhoudelijk is aangepast en waarvan `database.json` opnieuw is gehasht, wordt daardoor alsnog afgewezen.

## Publicatieketen

Voor gepubliceerde kennis blijft de kern dezelfde:

- PostgreSQL publicatiegegevens worden transactioneel vastgelegd;
- Azure Blob bevat de exacte immutable bronbytes;
- release manifests en Product API projecties zijn afgeleide lokale kopieën en kunnen uit de authority worden opgebouwd;
- lokale kopieën mogen nooit een nieuwere of afwijkende PostgreSQL-publicatie terugdraaien.

`DurablePublicationConsole` reconcilieert release manifests en de Product API-projectie vanuit PostgreSQL. In de volledige workflowmodus wordt ook de gepubliceerde envelope-status teruggeschreven naar de PostgreSQL workflow-authority. De lokale `envelopes.json` blijft daarbij alleen mirror.

## `--clean true`

`az webapp deploy --clean true` wist de deployment-managed `wwwroot`, niet `/home/data`. Dat blijft nuttig omdat lokale caches/mirrors niet bij iedere deployment hoeven te verdwijnen. Hun voortbestaan is echter niet meer vereist voor correctness wanneer alle workflow stores zijn geactiveerd.

## Topologie

De één-worker/één-instance-beperking blijft voorlopig actief:

- one Gunicorn worker;
- one instance;
- sequential writes.

Een configuratie met meerdere workers, meerdere instances of een andere write-mode blijft **buiten de topologie** en faalt via de bestaande guard. Multi-writer activering is dus niet impliciet onderdeel van stap 7. Ook multi-reviewer gedrag verandert hier niet.

Stap 6 heeft PostgreSQL-concurrencygedrag inmiddels met echte PostgreSQL-tests bewezen en de drie eerder gevonden blockers zijn opgelost. Het versoepelen van de topology-guard blijft echter een aparte expliciete wijziging; stap 7 verandert die deploymentgrens niet.

## Herstelbewijs en resterende productiegrens

De CI bevat nu echte PostgreSQL backup/restore-roundtriptests voor zowel canonical/publication als de volledige workflowstate. Die tests wissen de database na backup, herstellen uit het archive en vergelijken de herstelde authority opnieuw met de oorspronkelijke state. Ook workflow-tampering wordt getest.

Dit is herstelbewijs op CI/PostgreSQL 16, maar nog **geen echte production recovery drill**. Voor volledige production readiness blijft daarom nog vereist:

1. dezelfde recoveryprocedure uitvoeren tegen de echte Azure PostgreSQL-omgeving;
2. Blob restore/read-back tegen de echte Azure Storage authority bewijzen;
3. pas daarna de volledige Azure workflow-cut-over operationeel activeren.
