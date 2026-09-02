# Testomgeving en gecontroleerde releases

## Doel

`main` wordt automatisch uitgerold naar een geïsoleerde Metis-testomgeving.
Productie krijgt alleen een handmatige uitrol van een volledige, eerder geteste
commit-SHA. Een deployment vervangt applicatiecode in `wwwroot`; runtime-data
blijft buiten het pakket onder `/home/data` en in Blob Storage.

## Eenmalige Azure-inrichting

Maak in resourcegroep `AI_Dataservice` een tweede Linux App Service met de naam
`vvn-metis-console-test`, in hetzelfde plan als productie. Maak geen slot en
deel geen runtime-data met productie.

Zet minimaal deze instellingen op de **test-app**:

| Instelling | Waarde |
| --- | --- |
| `CONSOLE_DATA_ROOT` | `/home/data/metis-console-test` |
| `CONSOLE_IMMUTABLE_SOURCE_STORE` | `azure` |
| `WEBSITE_RUN_FROM_PACKAGE` | niet instellen |
| Start-up command | `bash scripts/azure_console_startup.sh` |

De testomgeving gebruikt een eigen Blob-container, bijvoorbeeld
`canonical-sources-test`, en een eigen system-assigned managed identity met
uitsluitend `Storage Blob Data Contributor` op die container. Verander nooit de
productiecontainer of productie-identity voor dit doel.

## GitHub OIDC-inrichting

Maak één Microsoft Entra app registration voor GitHub deployments. Voeg twee
federated credentials toe, beide beperkt tot repository
`WilliamGomes41/Metis-DS`:

| GitHub-subject | Azure-recht |
| --- | --- |
| `repo:WilliamGomes41/Metis-DS:environment:test` | `Website Contributor` op uitsluitend `vvn-metis-console-test` |
| `repo:WilliamGomes41/Metis-DS:environment:production` | `Website Contributor` op uitsluitend `vvn-metis-console` |

Maak in GitHub de Environments `test` en `production`. Stel voor
`production` minimaal één verplichte reviewer in. De productie-workflow kan dan
niet door een gewone push worden gestart.

Leg onderstaande waarden vast als GitHub Actions variables. Het zijn
identificerende configuratiewaarden, geen secrets; er komen geen Azure-keys in
de repository.

| Variable | Test / productie |
| --- | --- |
| `AZURE_CLIENT_ID` | OIDC app registration client ID |
| `AZURE_TENANT_ID` | V&VN Entra tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | `AI_Dataservice` |
| `AZURE_TEST_WEBAPP_NAME` | `vvn-metis-console-test` |
| `AZURE_TEST_APP_URL` | volledige test-URL zonder afsluitende slash |
| `AZURE_PRODUCTION_WEBAPP_NAME` | `vvn-metis-console` |
| `AZURE_PRODUCTION_APP_URL` | volledige productie-URL zonder afsluitende slash |

## Werking

1. Een pull request voert CI uit op Python 3.12 en 3.13.
2. Een merge naar `main` start `deploy-test`: een volledige test op Python 3.13,
   gevolgd door de uitrol van exact die commit naar test en `GET /health`.
3. Test de ingest-, review-, account- en bronopslagflow uitsluitend op testdata.
4. Start daarna in GitHub Actions `deploy-production`, plak de volledige SHA van
   de geteste `main`-commit en keur de production-environment goed.
5. De workflow controleert dat de SHA werkelijk op `main` ligt, draait opnieuw
   de tests, rolt precies die broncode uit en controleert `/health`.

## Herstel

Als productie na de healthcheck of functionele controle niet goed werkt,
start dan opnieuw `deploy-production` met de vorige bekende goede SHA. Herstel
geen data door een code-deployment: `/home/data` en de Blob-container zijn geen
onderdeel van het ZIP-pakket.

## Eerste ingebruikname

Voer na inrichting één niet-productieve ingest op test uit en verifieer:

- de bron krijgt een Azure locator in de **test**container;
- de SHA-256 readback klopt;
- een herstart/deployment van de test-app de testdata behoudt;
- productie geen nieuwe documenten of accounts heeft gekregen.
