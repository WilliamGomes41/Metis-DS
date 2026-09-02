# Testomgeving en gecontroleerde releases

## Doel

Golf C herstelt de PR #82-fouten. `deploy-test` en `deploy-production` blijven
**inactief / fail-closed** tot Azure App Service `vvn-metis-console-test`
bestaat. Merge naar `main` deployt **niet** automatisch naar een ontbrekende
test-app. Zet GitHub Actions-variable `METIS_TEST_APP_READY=true` pas nadat
die benoemde test-app bestaat. Deze repository maakt die App Service niet.

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

Zet op **productie**:

| Instelling | Waarde |
| --- | --- |
| `CONSOLE_DATA_ROOT` | `/home/data/metis-console` |
| `G2_STORAGE_ACCOUNT` | `aidataservice` |
| `G2_BLOB_CONTAINER` | `canonical-sources` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `false` |
| Start-up command | `bash scripts/azure_console_startup.sh` |

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

1. Een pull request voert CI uit op Python 3.12 en 3.13.
2. Een merge naar `main` start `deploy-test` alleen als `METIS_TEST_APP_READY=true`.
   Zolang die variable ontbreekt, blijft de deploy-job inactief; er is geen
   auto-deploy naar een ontbrekende test-app.
3. Packaging: `bash scripts/create_azure_deploy_package.sh` (executable of via
   bash). Het ZIP bevat vendored `.python_packages` uit `requirements.txt`.
4. `--clean true` wist `wwwroot` en MUST NOT `/home/data` wissen.
5. Production is handmatig: `deploy-production` met een volledige SHA die al
   op `main` ligt, na protection/approval, met de production-identiteit.

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
