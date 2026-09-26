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
| legacy versleutelde Audit LLM-payload | inert rollback-/recoverydata in PostgreSQL `workflow` | oude `audit_secrets/llm_api_key.json` alleen migratiebron; geen actieve providerauthority |
| canonical kennis + releases + registry | PostgreSQL publicatieschema | geen authority-kopie |
| immutable bronbytes | Azure Blob | lokale freeze is cache/werkexemplaar |
| release manifests | PostgreSQL releasegegevens zijn authority | lokale manifests zijn rebuildable release mirrors |
| Product API projectie | canonical/publication PostgreSQL | `published_projection.jsonl` is rebuildable derived output |

De actieve LLM-providerconfig (`METIS_LLM_API_KEY` en `METIS_LLM_MODEL`) blijft deployment-owned en buiten de database. Bestaande versleutelde Audit-secretpayloads kunnen voor rollback/recovery bewaard blijven, maar worden niet meer als runtime-providerauthority gelezen.

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

De database-export bevat drie delen in dezelfde `database.json`:

- `tables`: canonical/publication PostgreSQL;
- `workflow_tables`: accounts, sessies, documenten, reviewers, objects, review-events, authorizations, audits en Audit-secretpayloads.
- `api_access_tables`: consumers, applicaties, scopes/resources, credentialhashes,
  lifecycle-/policyversies en toegangs-audit uit alle acht migratie-010-tabellen.

De export gebeurt in één `REPEATABLE READ, READ ONLY` PostgreSQL-transactie. Daardoor horen workflow- en publicatiestate bij exact dezelfde databasesnapshot.

Workflow recovery v3 bewaart `logical_document_id`, `working_revision_id` en
`working_revision_number` expliciet uit de authority-kolommen. De verifier
controleert hun overeenkomst met de envelope, unieke revisies en acyclische
voorgangerrelaties. Revisienummergaten en oorspronkelijke werk-ID's blijven bij
restore behouden. Een v1-archive zonder deze authority-identiteiten wordt voor
volledig herstel afgewezen met `workflow_backup_lifecycle_identity_missing`;
maak een nieuwe export uit de oorspronkelijke authority.
Een v2-archive mist de expliciete toegangsdekking en wordt met
`workflow_backup_api_access_missing` afgewezen voor volledig herstel. De nieuwe
export neemt toegang mee in dezelfde repeatable-read snapshot. Herstel schrijft
de drie onderdelen in één transactie terug en vergelijkt ze exact. Ook een doel
met uitsluitend bestaande `api_access`-gegevens geldt als niet leeg. Er worden
geen nieuwe credentials of grants gegenereerd; ingetrokken/geschorste toegang
blijft geweigerd. Archives bevatten credentialhashes en moeten als gevoelige
hersteldata worden behandeld.

Een archive bewijst de toestand op haar herstelpunt. Latere intrekkingen,
revocations en verwijderingen staan niet vanzelf in een oudere backup. Houd een
herstelbestemming geïsoleerd totdat relevante latere besluiten uit een geldige
duurzame bron zijn meegenomen; geef bij ontbrekend bewijs geen productie-serving
of toegang vrij. Deze procedure belooft geen nul dataverlies/PITR zonder bewezen
operationele backupconfiguratie.

Restore vereist een lege, geïsoleerde doelomgeving en database-ownerrechten.
De import neemt exclusieve locks op de doeltabellen en controleert daarna opnieuw
dat ze leeg zijn. Alleen de identiteitstoekenningstrigger op `workflow.documents`
wordt binnen die transactie tijdelijk opgeschort, omdat nieuwe nummeruitgifte geen
herstel van een bestaande identiteit is. Voorgangers worden vóór opvolgers
ingevoegd; FK's, unieke constraints en alle overige triggers blijven actief.
De allocator wordt vóór commit weer ingeschakeld. Bij een fout rolt PostgreSQL
zowel de rows als deze trigger-DDL terug; er blijft geen herstelmodus achter.
Normale ingest en UPDATE-immutability veranderen niet. Een niet-lege bestemming
of een vooraf al uitgeschakelde allocator wordt geweigerd.

De restorevolgorde blijft fail-closed:

1. backup-archive en hashes controleren;
2. immutable Blob-bytes herstellen en teruglezen;
3. optionele lokale mirrors herstellen;
4. workflow + canonical/publication PostgreSQL in **één database-transactie** herstellen;
5. database opnieuw exporteren en roundtrip vergelijken;
6. canonical/publication-integriteit én workflow-integriteit opnieuw bewijzen.

PostgreSQL wordt dus pas authoritative nadat de bronbytes aanwezig en gecontroleerd zijn.

Het Blobmanifest omvat zowel canonical `source_snapshots` als de immutable
bronverwijzingen uit alle `workflow.documents`. Dat geldt ook voor ongepubliceerd
werk, opvolgversies in review en geblokkeerde documenten zonder objecten. Gelijke
locator/hash-verwijzingen worden gededupliceerd. Een ontbrekende/verkeerde bron
of ontbrekend manifestitem blokkeert volledig herstel; lokale freezes zijn geen
vervanging voor deze dekking. De bestaande G2-account/containercoördinaten moeten
bij het herstel overeenkomen; deze route verhuist historische locators niet.

## Workflow-integriteitsbewijs

`src/workflows/workflow_chain_recovery_v1.py` controleert aanvullend:

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

De ondersteunde productiegrens is:

- één Gunicorn-worker standaard, of twee Gunicorn-workers wanneer alle durable authorities actief zijn;
- one instance;
- sequential writes.

Twee workers vereisen canonical/publication plus alle vier workflowstores in PostgreSQL en immutable bronbytes in Azure Blob. Iedere commit ververst de gedeelde PostgreSQL-state nadat de procesoverschrijdende `/home/data`-storelock is verkregen; objectrevisies blokkeren een stale write. Lokale envelopes, bindings, ledger en projectie blijven mirrors. Startupmigratie en reconciliation gebruiken dezelfde lock.

Dit ondersteunt gelijktijdige multi-reviewer toegang via twee processen, maar
verandert de bestaande review-, autorisatie- en four-eyesregels niet.

Meer dan twee workers, meerdere instances, ontbrekende durable authorities, tegenstrijdige workerinstellingen of een andere write-mode blijven **buiten de topologie** en falen bij startup. Schaal dus niet horizontaal: de procesoverschrijdende lock is alleen gegarandeerd op dezelfde App Service-instance.

## Herstelbewijs en resterende productiegrens

De CI bevat nu echte PostgreSQL backup/restore-roundtriptests voor zowel canonical/publication als de volledige workflowstate. Die tests wissen de database na backup, herstellen uit het archive en vergelijken de herstelde authority opnieuw met de oorspronkelijke state. Ook workflow-tampering wordt getest.

Dit is herstelbewijs op CI/PostgreSQL 16, maar nog **geen echte production recovery drill**. Voor volledige production readiness blijft daarom nog vereist:

1. dezelfde recoveryprocedure uitvoeren tegen de echte Azure PostgreSQL-omgeving;
2. Blob restore/read-back tegen de echte Azure Storage authority bewijzen;
3. pas daarna de volledige Azure workflow-cut-over operationeel activeren.
