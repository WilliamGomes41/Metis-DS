# Testomgeving en gecontroleerde releases

## Doel

Golf C herstelt de PR #82-fouten. `deploy-test` blijft **inactief / fail-closed**
tot Azure App Service `vvn-metis-console-test` bestaat. Op grond van Protocol
v2.29 MAG `deploy-production` tijdelijk handmatig zonder test-app worden
gestart. Merge naar `main` deployt nooit automatisch.

Een deployment vervangt applicatiecode in `wwwroot` (`--clean true`);
runtime-data blijft buiten het pakket onder `/home/data` en in Blob Storage.
git-archive-only is niet genoeg: het ZIP-artefact MUST dependencies bevatten.

`publish()` blijft G2-BLOCKED. Deze runbook opent publicatie niet.

## Eenmalige Azure-inrichting (eigenaar, niet deze PR)

Maak in resourcegroep `AI_Dataservice` een tweede Linux App Service met de naam
`vvn-metis-console-test`, in hetzelfde plan als productie. Maak geen slot en
deel geen runtime-data met productie. **MUST NOT** die app in een code-PR
aanmaken.

Zet minimaal deze **app settings** (geen secrets) op de **test-app**:

| Instelling | Waarde |
| --- | --- |
| `CONSOLE_DATA_ROOT` | `/home/data/metis-console-test` |
| `G2_STORAGE_ACCOUNT` | `aidataservice` |
| `G2_BLOB_CONTAINER` | `canonical-sources-test` |
| `WEBSITE_RUN_FROM_PACKAGE` | niet instellen |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `false` (Oryx-during-deploy gaf HTTP_504 op B1) |
| Start-up command | `bash scripts/azure_console_startup.sh` |
| `WEB_CONCURRENCY` | unset or `1` (one Gunicorn worker; >1 is out of bound) |
| `CONSOLE_INSTANCE_COUNT` | unset or `1` (one instance; >1 is out of bound) |

Supported topology is one Gunicorn worker / one instance / sequential
writes. Do not scale out workers or instances. See
[RUNTIME_DATA_RECOVERY.md](RUNTIME_DATA_RECOVERY.md) and
`src/topology_bound_v1.py`.

Zet op **productie**:

| Instelling | Waarde |
| --- | --- |
| `CONSOLE_DATA_ROOT` | `/home/data/metis-console` |
| `G2_STORAGE_ACCOUNT` | `aidataservice` |
| `G2_BLOB_CONTAINER` | `canonical-sources` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `false` |
| Start-up command | `bash scripts/azure_console_startup.sh` |
| `WEB_CONCURRENCY` | unset or `1` (one Gunicorn worker; >1 is out of bound) |
| `CONSOLE_INSTANCE_COUNT` | unset or `1` (one instance; >1 is out of bound) |

Per-omgeving opslag loopt via deze app settings. Er komen geen storage keys,
connection strings of SAS-tokens in Git. `CONSOLE_IMMUTABLE_SOURCE_STORE=azure`
is golf B / G2 en hoort hier niet; die setting opent `publish()` niet.

De testomgeving gebruikt een eigen Blob-container `canonical-sources-test` en
een eigen system-assigned managed identity met uitsluitend
`Storage Blob Data Contributor` op die container. Verander nooit de
productiecontainer of productie-identity voor dit doel.

## GitHub OIDC-inrichting — gescheiden identiteiten

Eén Entra-app is niet genoeg als die naar beide apps kan deployen. Maak
**twee** app registrations / service principals:

| Identiteit | GitHub-subject | Azure-recht |
| --- | --- | --- |
| `metis-deploy-test` | `repo:WilliamGomes41/Metis-DS:environment:test` | `Website Contributor` op uitsluitend `vvn-metis-console-test` |
| `metis-deploy-production` | `repo:WilliamGomes41/Metis-DS:environment:production` | `Website Contributor` op uitsluitend `vvn-metis-console` |

Test cannot production. Production cannot test. Federated credentials op één
principal delen RBAC en omzeilen die grens.

Maak in GitHub de Environments `test` en `production`. Stel voor
`production` minimaal één verplichte reviewer in. De productie-workflow kan
niet door een gewone push worden gestart.

Leg onderstaande waarden vast als GitHub Actions **variables**. Het zijn
identificerende configuratiewaarden, geen secrets; er komen geen Azure-keys
in de repository.

| Variable | Test / productie |
| --- | --- |
| `METIS_TEST_APP_READY` | alleen `true` nadat `vvn-metis-console-test` bestaat; anders leeg |
| `AZURE_TEST_CLIENT_ID` | client ID van `metis-deploy-test` |
| `AZURE_PRODUCTION_CLIENT_ID` | client ID van `metis-deploy-production` |
| `AZURE_TENANT_ID` | V&VN Entra tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | `AI_Dataservice` |
| `AZURE_TEST_WEBAPP_NAME` | `vvn-metis-console-test` |
| `AZURE_TEST_APP_URL` | volledige test-URL zonder afsluitende slash |
| `AZURE_PRODUCTION_WEBAPP_NAME` | `vvn-metis-console` |
| `AZURE_PRODUCTION_APP_URL` | volledige productie-URL zonder afsluitende slash |
| `AZURE_TEST_STORAGE_ACCOUNT` | `aidataservice` |
| `AZURE_TEST_BLOB_CONTAINER` | `canonical-sources-test` |
| `AZURE_PRODUCTION_STORAGE_ACCOUNT` | `aidataservice` |
| `AZURE_PRODUCTION_BLOB_CONTAINER` | `canonical-sources` |

## Werking

1. Een pull request voert de volledige suite uit op Python 3.12 en 3.13,
   verdeeld over vier zelfstandige jobs per versie. De bestaande checks
   `test (3.12)` en `test (3.13)` controleren de volledige verzameling en het
   samengevoegde bewijs. Browserproeven draaien parallel in een eigen job.
2. `deploy-test` en `deploy-production` hebben **geen** `on.push`. Merge naar
   `main` start geen deploy. Zolang `vvn-metis-console-test` niet bestaat blijft
   de testworkflow fail-closed. Productie kan tijdelijk handmatig via v2.29.
3. Alleen een geslaagde push-CI op main bouwt het deploymentpakket met
   `bash scripts/create_azure_deploy_package.sh`. Een Python 3.12-proef importeert
   applicatie en native dependencies uitsluitend uit het uitgepakte ZIP.
   Het ZIP bevat vendored `.python_packages` uit `requirements-console.txt`
   (Protocol v2.24; MUST NOT numpy/sklearn/scipy). `requirements-retrieval.txt`
   blijft de zwaardere extra voor Product API / TF-IDF en gaat niet in het
   console-pakket.
4. `--clean true` wist `wwwroot` en MUST NOT `/home/data` wissen.
5. Deployment blijft handmatig: vul bij `deploy-test` of `deploy-production`
   **commit_sha** (volledige SHA op main) en **ci_run_id** (het nummer uit de
   URL `/actions/runs/<nummer>` van de geslaagde main-ci-run) in. Productie
   behoudt protection/approval en de production-identiteit. De workflow eist
   een voltooide geslaagde main-push van ci.yml voor die exacte repository en
   commit. Daarna downloadt hij het pakket van die CI-poging en controleert
   manifest, SHA-256 en de ingesloten commit vóór Azure-login. Dezelfde ZIP
   wordt voor test en productie gebruikt; er draait geen tweede volledige
   suite of pakketbouw in deployment. Verlopen/ontbrekend bewijs blokkeert;
   er wordt nooit stil naar een andere commit of nieuw gebouwd pakket uitgeweken.
6. Beide workflows en de handmatige ZIP-route gebruiken
   `scripts/verify_console_deployment.py`: `status=ok`,
   `service=operations-console` en `deployed_commit` gelijk aan de volledige
   verwachte SHA zijn verplicht. HTTP 200 alleen is onvoldoende.
   De controle herhaalt maximaal 13 keer met vijf seconden tussenruimte,
   tien seconden per HTTP-call en maximaal 64 KiB antwoord. De afzonderlijke
   geautoriseerde database-/ketenproef blijft nodig.

Een main-CI-run bewaart het pakket 30 dagen onder
`metis-console-<sha>-attempt-<poging>`. Oudere runs zonder dit pakket zijn niet
bruikbaar voor de nieuwe deploymentworkflow. Een herbouw vereist opnieuw
geslaagde CI en pakketcontrole; verander geen manifest om bewijs te omzeilen.

Bij een incidentele infrastructuurfout: **Actions → run → Re-run jobs → Re-run
failed jobs**. Een browserherpoging herhaalt dan geen geslaagde suitedelen.
Een gewijzigd programma vraagt een nieuwe run; eerdere groene jobs van een
andere commit gelden niet als bewijs. Controleer bij langdurige suitejobs de
laatste zichtbare testnaam. Iedere shard bewaart JUnit en timing; de samengevoegde
rapportage noemt totale testkosten en de langzaamste shard afzonderlijk.
Wachtrij- en installatietijd tellen mee voor de uiteindelijke GitHub-doorlooptijd.

## Herstel

Zie [RUNTIME_DATA_RECOVERY.md](RUNTIME_DATA_RECOVERY.md). Herstel geen data
door een code-deployment: `/home/data` en de Blob-container zijn geen
onderdeel van het ZIP-pakket.

## Eerste ingebruikname

Voer na inrichting én nadat `METIS_TEST_APP_READY=true` is gezet één
niet-productieve ingest op test uit en verifieer:

- de bron krijgt een Azure locator in de **test**container;
- de SHA-256 readback klopt;
- een herstart/deployment van de test-app de testdata behoudt;
- productie geen nieuwe documenten of accounts heeft gekregen.

## Migratie 018 (publication_refusals) en deploy-checklist

- Migratie `018_publication_refusal_audit.sql` MOET vóór de code worden toegepast die de tabel gebruikt, en alleen met GO van William (`scripts/apply_workflow_postgres_migrations.py plan` → `apply` met `--confirm-target` en `--confirm-digest`, daarna `verify`). Code die de tabel gebruikt MAG NIET live gaan voordat `verify` de tabel en de constraint `publication_refusals_dedup_key_uniq` toont.
- Na `apply` van 018 en vóór `verify` MOET de Entra-databasebeheerder de runtime-identity (test: de test-app-identity; productie: `vvn-metis-console`) rechten geven op de nieuwe tabel en sequence; `GRANT ... ON ALL TABLES` uit de eerste inrichting dekt 018 NIET:
  `GRANT SELECT, INSERT, DELETE ON workflow.publication_refusals TO "<runtime-identity>";`
  `GRANT USAGE, SELECT ON SEQUENCE workflow.publication_refusals_refusal_id_seq TO "<runtime-identity>";`
- 018 is idempotent: veilig om twee keer te draaien en bovenop de oude 018 zonder UNIQUE. 018 wijzigt NOOIT bestaande rijen.
- Faalt 018 met `publication_refusals_duplicate_dedup_keys count=N more=M keys=…` (maximaal 20 keys; haal de volledige lijst op met `SELECT dedup_key, count(*) FROM workflow.publication_refusals GROUP BY 1 HAVING count(*) > 1`), dan heeft de oude 018 dubbele dedup_keys achtergelaten. 018 heeft dan niets gewijzigd (transactie teruggedraaid). Een mens beslist: (1) exporteer eerst de genoemde rijen (`SELECT * FROM workflow.publication_refusals WHERE dedup_key IN (…)`) naar het evidence-archief; (2) leg de keuze vast met GO van William (bijvoorbeeld de latere dubbele rijen na export verwijderen); (3) draai daarna `plan` → `apply` → `verify` opnieuw. De code MAG NIET live gaan zolang 018 niet geslaagd is.
- Deploy-checklist, retentie: plan `scripts/publication_refusal_retention.py` (standaard 400 dagen / 200000 rijen; `--max-rows` en `--retention-days` MOETEN > 0 zijn) als expliciet onderhoud. Retentie MAG NIET per weigering draaien. De planning zelf is niet gebouwd; dit is een checklistpunt.
- Tests: de PostgreSQL-tests draaien `DROP SCHEMA workflow CASCADE`. METIS_TEST_POSTGRES_DSN MOET only point at a disposable database (CI-service of een lokale wegwerpdatabase), NOOIT naar test-, acceptatie- of productiedata.

## Deploynotitie: verwerkingsconfiguratie tijdens een deploy (RESV-1 F3)

- Een poging die vóór een deploy is gereserveerd en na de deploy onder een andere verwerkingsconfiguratie zou draaien, MOET stoppen met `processing_configuration_changed`; er MAG NIET werk onder de nieuwe configuratie starten. De gebruiker start daarna een nieuwe poging.
- Ingest-, Bronselectie-, hervat- en re-extract-pogingen pinnen de configuratie al op de poging. Sinds #639 pint ook de retry-route (`retry_pre_review`) de configuratie op een nieuwe poging. Zolang #639 niet gemerged is MOET een deploy die `METIS_*`-verwerkingsinstellingen wijzigt pas gebeuren als er geen retry-poging `running` is.
- Ook bij hergebruik van een opgeslagen `prepared_source_extraction` (zelfde bron) MOET de configuratiecontrole vóór het providerwerk gebeuren; hergebruik MAG NIET de controle overslaan (#639, Codex P1).
- Een poging zonder vastgepinde configuratie MOET geweigerd worden met `processing_configuration_unpinned`; er is NOOIT een uitzondering.
- Deploynotitie (#639): een poging die al liep vóór de deploy en geen vastgepinde configuratie heeft (bijvoorbeeld een retry-poging van vóór #639), MOET na de deploy stoppen met `processing_configuration_unpinned`. De gebruiker start daarna een nieuwe poging; die pint de configuratie. Dit is verwacht gedrag en MAG NIET als incident gelden.
- `METIS_PROCESSING_ADMISSION=closed` sluit alleen de toelating van pogingen (`reserve()`). Een deterministische re-extract en een niet-LLM-ingest reserveren geen poging en draaien door. Wie alle schrijfacties wil stoppen, MOET de console stoppen.
- Rollback voorbij #628: eerst `METIS_PROCESSING_ADMISSION=closed` zetten, lopende pogingen laten uitlopen en dan `scripts/processing_rollback_precheck.py` draaien (exit 0 is de enige uitkomst die rollback voorbij #628 toestaat); zie `docs/change-contracts/a3-incomplete-budget-rollback.md`.
- Is de configuratie bij een retry niet leesbaar, dan MOET de retry geweigerd worden met `processing_configuration_unavailable` zonder nieuwe poging.

## Log redaction: known over-redaction (#638, accepted by Metis)
Structured logging redacts every word after an auth scheme word (bearer, basic, digest, negotiate; any casing). Prose is redacted too: 'use the basic flow' is logged as 'use the [REDACTED]'. This is intended (fail-closed) and MAG NIET be treated as a log defect; a change to it MOET go through Metis.
