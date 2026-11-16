# Azure stap 9 — PostgreSQL workflow cut-over

Datum: 2026-09-12

## Doel en harde grens

Deze route activeert de bestaande Metis-productieomgeving gefaseerd op dezelfde PostgreSQL-authority die canonical/publication gebruikt. Azure Blob blijft de immutable bron-authority. De route maakt geen Web App, PostgreSQL-server, storage account of container aan; wijzigt geen bronbytes of `/home/data`; schrijft geen secrets naar Git; en voert geen GitHub Actions-deployment uit.

De productie-selectie moet expliciet worden bevestigd. Voor de bekende productieomgeving zijn de verwachte waarden:

```bash
export METIS_SUBSCRIPTION_ID="8c829c96-1784-4947-8a2b-92027c51fec9"
export METIS_RESOURCE_GROUP="AI_Dataservice"
export METIS_WEBAPP="vvn-metis-console"
```

Als één waarde afwijkt of PostgreSQL niet eenduidig uit de bestaande App Settings kan worden afgeleid: stop. Pas geen setting aan en maak geen server aan.

## 0. Exacte geteste main-container voorbereiden

Stel eerst de huidige hosting vast met een read-only controle:

```bash
az webapp config show \
  --subscription "$METIS_SUBSCRIPTION_ID" \
  --resource-group "$METIS_RESOURCE_GROUP" \
  --name "$METIS_WEBAPP" --query linuxFxVersion --output tsv
```

- `DOCKER|…`: volg [AZURE_RELEASE_RUNBOOK.md](AZURE_RELEASE_RUNBOOK.md) en het
  [deploymentprotocol](agents/deployment-protocol.md): een exacte geteste,
  gemergde main-SHA, wisselen op digest en eerst het rollbackpunt vastleggen.
- `PYTHON|3.13`: **STOP met de container-cutover**. De bestaande tijdelijke
  `deploy-production.yml` blijft voor legacy-code-updates beschikbaar en
  controleert zelf de actuele hosting vóór iedere reeks Azure-mutaties.
  Zij bouwt of activeert geen container. De eerste overgang vereist een eigen
  geaccepteerd rollbackplan en capaciteitsproef; ontbrekend bewijs blijft open
  onder [#695](https://github.com/WilliamGomes41/Metis-DS/issues/695) en
  [#696](https://github.com/WilliamGomes41/Metis-DS/issues/696).
- Een andere of ontbrekende waarde, of een leesfout: **STOP**, geen deployment.

De definitieve ZIP-uitfasering wacht op bewijs van de eerste containerovergang.
Dit cutoverrunbook biedt geen onbewaakt handmatig ZIP-deploycommando.

Voer de image-wissel pas uit nadat de database-/rechtenvoorwaarden hieronder en
de releasepreflight zijn bewezen. Elke Azure-mutatie vereist afzonderlijk GO.
Repository voorbereiden voor de preflight en migratieplanning:

```bash
git fetch origin main
git switch --detach origin/main
METIS_MAIN_SHA="$(git rev-parse HEAD)"
```

Verifieer na de afzonderlijk goedgekeurde container-imagewissel de exacte SHA:

```bash
python scripts/verify_console_deployment.py \
  --health-url "https://${METIS_WEBAPP}.azurewebsites.net/health" \
  --expected-commit "$METIS_MAIN_SHA"
```

Alleen `status=ok`,
`service=operations-console` en exact de verwachte volledige SHA geven exit 0.
Een afsluitende slash in de app-origin wordt naar één `/health` genormaliseerd.
Een oude SHA, `not_recorded`, ontbrekende velden of een onleesbaar antwoord
geven na maximaal 13 pogingen exit 1. Tussen pogingen zit vijf seconden;
iedere HTTP-call heeft maximaal tien seconden en 64 KiB antwoordruimte.
Dit bewijst de gedeployde versie; een geautoriseerde database-/ketenproef
blijft een afzonderlijke vrijgavevoorwaarde.

De versiecontrole wijzigt geen `/home/data`, Blob, PostgreSQL-inhoud of App Settings.

## 1. Read-only Azure-preflight

```bash
python scripts/azure_step9_cutover.py preflight \
  --subscription-id "$METIS_SUBSCRIPTION_ID" \
  --resource-group "$METIS_RESOURCE_GROUP" \
  --webapp "$METIS_WEBAPP"
```

De preflight controleert zonder mutatie:

- de actieve subscription, resource group en Web App;
- system-assigned managed identity;
- één worker en één instance;
- bestaande canonical PostgreSQL-coördinaten en een unieke bestaande Flexible Server-match;
- `Microsoft.DBforPostgreSQL=Registered`;
- Azure Blob-account/container;
- `Storage Blob Data Contributor` voor de Web App-identity op exact de containerscope;
- bestaande authority-settings en de dependencyvolgorde van workflowflags.

De JSON-uitvoer bevat alleen allowlisted instellingen; overige App Settings en secrets worden niet gerapporteerd. `BLOCKED` is een stopconditie.

## 2. Alleen ontbrekende beheeractie uitvoeren

De preflight voert deze acties bewust niet zelf uit.

Als uitsluitend Blob-RBAC ontbreekt, laat een Azure-beheerder exact één assignment op containerscope maken. Geef de uitvoerende gebruiker geen tijdelijke brede rol als dat niet nodig is:

```bash
APP_PRINCIPAL_ID="$(az webapp show --subscription "$METIS_SUBSCRIPTION_ID" --resource-group "$METIS_RESOURCE_GROUP" --name "$METIS_WEBAPP" --query identity.principalId --output tsv)"
STORAGE_ID="$(az storage account show --subscription "$METIS_SUBSCRIPTION_ID" --name aidataservice --query id --output tsv)"
CONTAINER_SCOPE="${STORAGE_ID}/blobServices/default/containers/canonical-sources"

az role assignment create \
  --subscription "$METIS_SUBSCRIPTION_ID" \
  --assignee-object-id "$APP_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" \
  --scope "$CONTAINER_SCOPE"
```

Als de PostgreSQL-provider niet geregistreerd is of geen bestaande server eenduidig matcht, stop en laat de Azure-beheerder eerst de bedoelde productiearchitectuur bevestigen. Deze runbookroute registreert niets en provisiont niets.

De Web App-identity moet als Microsoft Entra-principal in de bestaande PostgreSQL-server bestaan. Een Entra-databasebeheerder controleert of maakt die principal gericht aan. Gebruik geen wachtwoord, connection string of SAS-token. De officiële Azure-functie voor een ontbrekende managed-identity-principal is op database `postgres`:

```sql
select * from pgaadauth_create_principal('vvn-metis-console', false, false);
```

Voer dit alleen uit als de principal aantoonbaar ontbreekt. Rechten worden pas na het toepassen van het workflowschema in de bedoelde applicatiedatabase toegekend; niet op andere databases.

## 3. Migraties 002–006 plannen, toepassen en verifiëren

Gebruik de host en databasenaam uit de geslaagde preflight. `$METIS_DB_ADMIN_USER` is de bestaande Entra databasebeheerder waarmee Cloud Shell inlogt.

```bash
python scripts/apply_workflow_postgres_migrations.py plan \
  --host "$METIS_DB_HOST" \
  --database "$METIS_DB_NAME"
```

Neem `target` en `digest` exact uit de planuitvoer over. Alleen daarna:

```bash
python scripts/apply_workflow_postgres_migrations.py apply \
  --host "$METIS_DB_HOST" \
  --database "$METIS_DB_NAME" \
  --user "$METIS_DB_ADMIN_USER" \
  --confirm-target "$METIS_DB_HOST/$METIS_DB_NAME" \
  --confirm-digest "$METIS_MIGRATION_DIGEST"

python scripts/apply_workflow_postgres_migrations.py verify \
  --host "$METIS_DB_HOST" \
  --database "$METIS_DB_NAME" \
  --user "$METIS_DB_ADMIN_USER"
```

Elke SQL-file draait in een eigen transactie. De runner stopt bij de eerste fout, voert geen herstel-DDL uit en rapporteert alleen schema-aanwezigheid en aantallen, nooit rij-inhoud.

Laat de Entra-databasebeheerder vervolgens alleen de gerichte runtime-rechten in de bevestigde applicatiedatabase toekennen:

```sql
GRANT CONNECT ON DATABASE metis TO "vvn-metis-console";
GRANT USAGE ON SCHEMA public, workflow TO "vvn-metis-console";
```

Gebruik daarna de bestaande `verify --runtime-role vvn-metis-console`-controle
en laat de beheerder de gerapporteerde gerichte `grants` beoordelen en uitvoeren.
De controle betreft benodigde workflowrechten; beoordeel de bestaande noodzakelijke
canonical/public- en API-access-rechten afzonderlijk. Geef geen algemene
UPDATE/DELETE op alle tabellen: onder meer `publication_refusals` verbiedt UPDATE.
Een beperktere GRANT trekt eerder toegekende rechten niet in.

### STOP: rechten buiten workflow nog niet bewezen

**Een workflow-PASS is geen toestemming om de cutover voort te zetten.**
Vóór stap 4 en vóór iedere activatie moeten ook de noodzakelijke rechten op
`public` en `api_access` zijn toegepast en geverifieerd. Dit geldt in het
bijzonder voor een nieuwe database of een nieuwe runtime-rol: CONNECT en
schema-USAGE geven op zichzelf geen toegang tot tabellen of sequences.

Doorgaan mag alleen met beide bewijsstukken in het cutoververslag:

1. Een door de databasebeheerder beoordeeld **rechtenprofiel**, met concrete
   GRANT-regels per benodigde tabel en sequence in `public` en `api_access`,
   de doel-database en de werkelijk gebruikte runtime-identiteit. De beheerder
   bevestigt dat dit profiel is toegepast; ook de benodigde schema-USAGE telt mee.
2. Verificatie met die runtime-identiteit dat het profiel alle noodzakelijke
   lees- en schrijfbewerkingen toestaat. Gebruik een geïsoleerde database met
   hetzelfde schema en rechtenprofiel voor muterende proeven. Bewijs ten minste
   de canonical/public-opstart- en publicatiepaden en de API-access-paden; alleen
   een geslaagde controle als databasebeheerder is geen bewijs voor de runtime-rol.

**Ontbreekt het rechtenprofiel of het verificatiebewijs: STOP.** Pas geen
workflowflag aan en voer geen image-wissel uit. Het hier beschreven script
controleert die volledige non-workflow-scope niet. Het vervolg voor automatische
canonical/public-controle staat in [#940](https://github.com/WilliamGomes41/Metis-DS/issues/940);
dat issue is geen vervanging voor uitgevoerd bewijs en omvat `api_access` niet.
Leg bij een bestaande installatie het al toegepaste profiel en zijn verificatie
vast; de voorbeelden hieronder trekken geen bestaande grants in.

Is de database al ingericht vóór migratie 018, dan MOET de beheerder na 018 ook deze rechten toekennen (DELETE alleen voor het expliciete retentiecommando; geen UPDATE, de tabel is append-only):

```sql
-- Na migratie 018 (#636): GRANT ... ON ALL TABLES dekt geen later aangemaakte tabellen.
GRANT SELECT, INSERT, DELETE ON workflow.publication_refusals TO "vvn-metis-console";
GRANT USAGE, SELECT ON SEQUENCE workflow.publication_refusals_refusal_id_seq TO "vvn-metis-console";
```

Vervang `metis` alleen door de reeds bevestigde bestaande databasenaam. Geef geen eigenaarschap, DDL-recht of brede serverrol aan de runtime-identity.

Met `verify --runtime-role vvn-metis-console --strict-runtime-privileges` controleer
je aanvullend het verbod op UPDATE (ook kolomrechten) op `publication_refusals`
en gevaarlijke workflowrolbevoegdheden. De rapportagescope is expliciet; dit is
geen volledige least-privilege-audit. Herstel overtollige rechten alleen na
inspectie van PUBLIC, overerving en bereikbare SET ROLE-rollen; de controle trekt
zelf niets in. Controleer de effectieve rechten daarna opnieuw.

De migratierunner begrenst lockwachten standaard op 5000 ms per statement, binnen
de bestaande bestandstransactie. `--lock-timeout-ms` accepteert een positieve
waarde; een fout stopt zonder automatische retry. Onderzoek de blokkade vóór
herhaling. Een expliciete outer transactie blijft eigendom van de aanroeper;
de runner herstelt daar ook na succes de eerdere lock-timeout.

Azure-verbindingen vereisen TLS-serveridentiteitscontrole (`verify-full`). Gebruik
de CA-bundel van het deploymentimage of een leesbaar PEM-bestand via
`PGSSLROOTCERT`. Een onbruikbaar expliciet bestand geeft een fout, zonder fallback.
Controleer dit vanuit het werkelijke image vóór een release. Azure-DSN-detectie
herkent expliciete Azure-hostnames en PGHOST; verborgen service-file-hosts en
private DNS-aliassen vereisen afzonderlijke configuratiecontrole.

## 4. Bestaande `/home/data` exact migreren

Deze stap moet in de draaiende Linux Web App worden uitgevoerd, omdat alleen daar zowel de system-assigned managed identity als `/home/data/metis-console` beschikbaar zijn. Open een Azure App Service SSH-sessie, ga naar `/home/site/wwwroot` en plan eerst:

```bash
python scripts/migrate_workflow_cutover_postgres.py \
  --runtime /home/data/metis-console/output/runtime/operations-console
```

Voer daarna exact de gerapporteerde runtimebevestiging uit:

```bash
python scripts/migrate_workflow_cutover_postgres.py \
  --runtime /home/data/metis-console/output/runtime/operations-console \
  --execute \
  --confirm-runtime /home/data/metis-console/output/runtime/operations-console
```

De wrapper hergebruikt de bestaande idempotente migratielogica in deze vaste volgorde: identity → documenten → volledige envelope/objectvolgorde → review → remaining. Hij vergelijkt na identity-migratie accounts, wachtwoordhashes en gehashte sessietokens exact zonder de waarden te rapporteren. Hij verwijdert of wijzigt geen lokale runtimebestanden. Een fout stopt de keten; corrigeer de oorzaak en herhaal idempotent, zonder cleanup of delete.

## 5. Gefaseerd activeren

Herhaal vóór iedere fase de read-only preflight. Activeer nooit meerdere flags in één opdracht.

```bash
python scripts/azure_step9_cutover.py activate \
  --subscription-id "$METIS_SUBSCRIPTION_ID" \
  --resource-group "$METIS_RESOURCE_GROUP" \
  --webapp "$METIS_WEBAPP" \
  --phase identity \
  --confirm "$METIS_SUBSCRIPTION_ID/$METIS_RESOURCE_GROUP/$METIS_WEBAPP/identity" \
  --database-user "$METIS_DB_ADMIN_USER" \
  --confirm-data-migrated "$METIS_DB_HOST/$METIS_DB_NAME"
```

Daarna volgen, elk als afzonderlijke opdracht en alleen na succesvolle smokecontrole:

| Fase | Flag | Voorwaarde |
|---|---|---|
| `identity` | `METIS_WORKFLOW_STORE=postgres` | schema + data exact gemigreerd |
| `documents` | `METIS_WORKFLOW_DOCUMENT_STORE=postgres` | identity gezond |
| `review` | `METIS_WORKFLOW_REVIEW_STORE=postgres` | documenten gezond |
| `remaining` | `METIS_WORKFLOW_REMAINING_STORE=postgres` | review gezond |

De activator verifieert het workflowschema opnieuw via de bestaande Entra-databasegebruiker, wijzigt alleen de ene genoemde App Setting, herstart de bestaande Web App en wacht op `https://<defaultHostName>/health`. Bij een fout voert hij geen automatische rollback uit en mag de volgende fase niet worden gestart.

## 6. Smokecontrole per fase

Naast `/health` controleert een bevoegde onderzoeker na iedere fase dat de bestaande gegevens exact terugkomen. Voer alleen passende read-/write-smokes uit voor de zojuist geactiveerde authority:

1. identity: bestaande accounts zichtbaar; login en logout/revoke werken;
2. documenten: bestaande documenten, envelopes, objectvolgorde en bronlocators gelijk;
3. review: bestaande reviewevents/hash-chain en authorizations gelijk; één gecontroleerde reviewactie werkt;
4. remaining: Audit-records en bestaande versleutelde Audit-secretpayload beschikbaar; plaintext secret nergens tonen;
5. eindcontrole: Inleveren → Review → Publiceren → Documenten en Audit, plus canonical PostgreSQL en Azure Blob read-back.

Houd `WEB_CONCURRENCY=1` en `CONSOLE_INSTANCE_COUNT=1`. Stap 10 (restart/failure/recovery-drill) is een aparte productiehandeling en valt niet binnen deze cut-over.

Na succesvolle stap 10 mag een latere, afzonderlijk gereviewde release
`WEB_CONCURRENCY=2` activeren, uitsluitend wanneer canonical/publication, alle
vier workflowstores en Azure Blob authority actief en gezond zijn. Houd
`CONSOLE_INSTANCE_COUNT=1`; meer dan twee workers of meer dan één instance
blijven fail-closed.

## Stopcondities

Stop zonder automatische herstelactie bij een Azure CLI-fout, ontbrekende of ambigue PostgreSQL-server, onverwachte App Setting, ontbrekende RBAC/Entra-principal, schema- of migratieconflict, `503`, dataverschil of mislukte smoke. Verwijder geen blobs, database-rijen, releases of `/home/data`-bestanden. Een rollback van een workflowflag is een afzonderlijke eigenaarbeslissing na foutanalyse.
