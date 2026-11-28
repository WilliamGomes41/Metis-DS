# Azure-release van de console (Docling-image)

Dit runbook beschrijft hoe een exacte `main`-commit als container-image naar Azure gaat. Het is dezelfde route als in `docs/change-contracts/zorgmaatje.md`: `az acr build` met `Dockerfile.docling --target runtime` en daarna de app wisselen via de digest. Een console-ZIP levert geen volledige Docling-runtime.

De bestaande tijdelijke `deploy-production.yml` blijft beschikbaar voor code-updates
zolang de app nog `PYTHON|3.13` gebruikt. De workflow leest de actuele
`linuxFxVersion` en weigert containerhosting, onbekende waarden en leesfouten
vóór app-settingmutaties of ZIP-deployment. Deze route voert geen eerste
containerovergang uit. De ZIP-workflow mag pas definitief verdwijnen nadat de
containerovergang met rollback- en capaciteitsbewijs is geaccepteerd.

Elke stap die Azure wijzigt (build, migratie, app settings, tijdelijke firewalltoegang, image-wissel en rollback) gebeurt alleen met GO van William. Bundeling van alleen-lezen controles volgt het [deploymentprotocol voor agents en Cloud Shell](agents/deployment-protocol.md).

## Benodigd

- `az` aangemeld met een identiteit die mag bouwen in de ACR en de web app mag configureren.
- Namen: ACR (`<acr>`), image-repository (`<repo>`), resourcegroep (`<rg>`), web app (`<app>`), app-URL (`<url>`).
- Een checkout van deze repository met `origin/main` bijgewerkt.
- Zet voor de shellblokken hieronder `azure_subscription` (naam of ID), `resource_group`, `app_name`, `app_url` (de origin zonder pad), `acr_name` en `image_repo` op het cutoverdoel. Zet `release_sha` op de gecontroleerde volledige SHA van `main`. Controleer de waarden opnieuw na een nieuwe Cloud Shell-sessie.

## 1. Vooraf

1. Leg de huidige image-referentie vast als rollbackpunt, samen met de huidige `deployed_commit` uit `<url>/health`. Bewaar de volledige image-referentie in `rollback`:
   `az webapp config show --subscription "$azure_subscription" -g "$resource_group" -n "$app_name" --query linuxFxVersion -o tsv`
   Begint die waarde niet met `DOCKER|` (bijvoorbeeld `PYTHON|3.13`, de ZIP-route), stop dan. Dit runbook wisselt alleen van container naar container; een eerste overstap van ZIP naar container vraagt een eigen plan met een eigen rollback (`az webapp config set --linux-fx-version`) en een capaciteitsproef voor Docling.
2. Controleer de app settings:
   `(set -o pipefail; az webapp config appsettings list --subscription "$azure_subscription" -g "$resource_group" -n "$app_name" -o json | python3 scripts/release_settings_preflight.py)`
   Exit 0 is klaar. Exit 2 blokkeert de release. De belangrijkste weigering is `passage_formation_mode_retired`: `METIS_PASSAGE_FORMATION_MODE=deterministic-v1` laat sinds #817 elke nieuwe verwerking falen, ook beslisbomen. Zet de waarde dan op een semantische modus (`semantic-source-bound-v1`, `-v2` of `-v3`) of verwijder haar (leeg betekent `semantic-source-bound-v2`). De uitvoer toont geen geheime waarden.
3. Tel lopende pogingen, inclusief bronvoorbereiding en handmatige bouw. Neem zowel native pogingen in `workflow.processing_attempts` als inline pogingen van documenten zonder native verwerkingsopslag mee. Herhaal deze alleen-lezen telling vlak vóór de wissel. Een image-wissel herstart de app en breekt lopende pogingen af.
4. Controleer dat de app een image uit deze ACR mag trekken en op de goede poort luistert. Begint de referentie uit stap 1.1 al met `DOCKER|` en de login-server van de ACR, dan is dit eerder ingericht; controleer het toch:
   - `az webapp config show --subscription "$azure_subscription" -g "$resource_group" -n "$app_name" --query acrUseManagedIdentityCreds` geeft `true`, en de identiteit van de app heeft de rol `AcrPull` op de ACR (`az role assignment list --assignee <principal-id> --scope <acr-resource-id>`). Anders kan de app het nieuwe image niet ophalen.
   - De app setting `WEBSITES_PORT` is `8000`. Gunicorn luistert in het image op `${PORT:-8000}`; App Service gaat zonder deze setting uit van poort 80.
5. Migraties en runtime-rechten. Voer als database-beheerder uit:
   `python scripts/apply_workflow_postgres_migrations.py verify --host <host> --database metis --user <beheerder> --runtime-role vvn-metis-console`
   **STOP bij ontbrekend non-workflow-rechtenbewijs.** Een workflow-PASS bewijst
   geen volledige runtime-toegang. Vóór bouwen of wisselen moet het concrete
   rechtenprofiel voor `public` en `api_access` zijn toegepast en met de werkelijke
   runtime-identiteit zijn geverifieerd. Volg de verplichte
   [stopvoorwaarde en bewijsstukken](AZURE_STEP9_CUTOVER_RUNBOOK.md#stop-rechten-buiten-workflow-nog-niet-bewezen).
   Hergebruik bestaand bewijs als het de actuele doeldatabase, runtime-identiteit en het geldende rechtenprofiel dekt. Verwijs naar het bewijs in het cutoververslag.
   Voeg `--view-check` toe als `METIS_VIEW_CHECK_ORIGIN` gezet is, `--compact-cards` bij `CONSOLE_REVIEW_CARD_READS=compact` en `--test-document-deletion` bij `CONSOLE_TEST_DOCUMENT_DELETION=on`. Die opties voegen de schema- en rechtencontroles voor de actieve functies toe.
   - Ontbreekt een tabel of kolom (ook `missing_relations` onder `runtime_privileges`): eerst `plan`, dan `apply` met `--confirm-target` en `--confirm-digest`, dan opnieuw `verify`.
   - Staat onder `runtime_privileges` een `BLOCKED`: voer de regels uit `grants` uit, en draai `verify` opnieuw tot `PASS`. De controle kent zelf niets toe. `GRANT … ON ALL TABLES` uit de eerste inrichting dekt geen tabellen uit latere migraties (zo ging het bij 026 mis, #930).
   - Optioneel: `--strict-runtime-privileges` weigert daarnaast UPDATE op `workflow.publication_refusals` en gevaarlijke workflowrolbevoegdheden. Bij deze weigeringen is een GRANT geen oplossing: inspecteer de effectieve rechten en hun bronnen. De controle wijzigt niets en claimt geen volledige databasebrede least-privilege-audit.
   - `apply` begrenst lockwachten standaard op 5000 ms; pas dit alleen bewust aan met `--lock-timeout-ms`. Na een lockfout eerst de blokkade onderzoeken, dan de bestaande idempotente route herhalen.
   - Azure-verbindingen gebruiken `verify-full` met de systeem-CA of het expliciete PEM-bestand in `PGSSLROOTCERT`. Bewijs vanuit het bedoelde image dat trust, DNS-hostname en Entra-login werken; ontbrekende trust is een fout, geen reden voor automatische fallback.
6. Weergavecontrole: dit runbook zet haar niet aan. Rapporteert de preflight `"view_check": "enabled"`, controleer dan ook wat de preflight niet kan zien, volgens `docs/change-contracts/zorgmaatje.md`: de private evidence-container bestaat, heeft een lifecycle-regel van 7 dagen, en de app-identiteit heeft daarop `Storage Blob Data Contributor`. Doe na de wissel één weergavecontrole. Aanzetten is een aparte stap met GO.
7. Compacte reviewkaarten: staat `CONSOLE_REVIEW_CARD_READS=compact` aan, en wijzigt de release het `producer_contract` van `review_card_facts_v1`? Dat gebeurt bijvoorbeeld bij een nieuwe `source_containers_v1.VERSION`. Voer dan direct na de wissel `python scripts/prepare_review_cards.py --all` uit, en daarna dezelfde opdracht met `--check`. Zonder die stap tonen de kaarten "Kaartgegevens niet beschikbaar", omdat GET niets opnieuw opbouwt. In de standaardstand (`legacy`) is deze stap niet nodig.

### Tijdelijke PostgreSQL-toegang vanuit Cloud Shell

Test eerst de bestaande toegang. Is het actuele Cloud Shell-IP niet toegestaan en ontbreekt een bruikbare bestaande verbinding, vraag dan GO voor één tijdelijke firewallregel met hetzelfde IP als begin- en eindadres. Gebruik een unieke regelnaam en registreer een opruimactie voor afsluiten of fouten. Wacht begrensd op PostgreSQL na het aanmaken. Een verbindingstime-out kan tijdelijk zijn. Stop bij een authenticatie- of SQL-fout en geef die fout terug zonder token of private gegevens.

Voer de alleen-lezen databasecontroles voor dit controlemoment samen uit. Verwijder de regel direct na de controles, ook bij een fout, en bevestig via de firewallregellijst dat de regel weg is. Houd de regel gesloten tijdens de ACR-build. Herhaal vlak vóór de wissel alleen de benodigde telling en gebruik na de wissel een afzonderlijk controlemoment voor `pg_stat_activity`.

Gebruik voor de telling van lopende pogingen deze query op de doeldatabase. Een poging met status `running` waarvan `expires_at` voorbij is, telt net als in de applicatie als verlopen. Een poging zonder `expires_at` telt mee:

```sql
SELECT
    (SELECT count(*) FROM workflow.processing_attempts
     WHERE payload->>'state' = 'running'
       AND (payload->>'expires_at' IS NULL OR (payload->>'expires_at')::timestamptz > now()))
    +
    (SELECT count(*) FROM workflow.documents AS d
     CROSS JOIN LATERAL jsonb_array_elements(
         COALESCE(NULLIF(d.envelope_payload->'processing_attempts', 'null'::jsonb), '[]'::jsonb)
     ) AS a(attempt)
     WHERE d.processing_storage_version IS DISTINCT FROM 1
       AND a.attempt->>'state' = 'running'
       AND (a.attempt->>'expires_at' IS NULL OR (a.attempt->>'expires_at')::timestamptz > now())) AS lopende_pogingen;
```

## 2. Image bouwen

```bash
bash scripts/build_azure_release_image.sh --registry "${acr_name:?}" \
  --repository "${image_repo:?}" --commit "${release_sha:?}" --dry-run
```

Na GO voor de build:

```bash
(
  set -e
  # --subscription accepteert een naam of een ID; vergelijk aan beide kanten het ID.
  release_subscription_id=$(az account show --subscription "${azure_subscription:?}" --query id --output tsv)
  if [[ "$(az account show --query id --output tsv)" != "$release_subscription_id" ]]; then
    printf '%s\n' 'Gestopt. Selecteer de Azure-subscription van de release.' >&2
    exit 1
  fi
  bash scripts/build_azure_release_image.sh --registry "${acr_name:?}" \
    --repository "${image_repo:?}" --commit "${release_sha:?}"
)
```

Het script weigert een commit die niet op `main` staat. De buildcontext is een schone `git archive` plus `config/deployed_commit.txt`. Leg het build-ID, de duur en `release_image_reference=<login-server>/<repo>@sha256:…` vast. Zet `release_image_reference` op die afgedrukte waarde. Het register kan een domeinlabel in de hostnaam hebben, bijvoorbeeld `<acr>-<hash>.azurecr.io`.

## 3. Wisselen

Voer dit blok uit na een nieuwe telling van `0` lopende pogingen en GO voor de wissel. De variabele `rollback` bevat de volledige oude waarde uit stap 1.1.

```bash
(
  set -e
  app_args=(--subscription "${azure_subscription:?}" -g "${resource_group:?}" -n "${app_name:?}")
  current=$(az webapp config show "${app_args[@]}" --query linuxFxVersion -o tsv)
  if [[ ! "${rollback:?}" =~ ^DOCKER\|.+@sha256:[0-9a-f]{64}$ || "$current" != "$rollback" ]]; then
    printf '%s\n' 'Gestopt. Controleer het terugvalpunt en de actieve image.' >&2
    exit 1
  fi
  if [[ ! "${release_image_reference:?}" =~ ^[^[:space:]\|]+@sha256:[0-9a-f]{64}$ ]]; then
    printf '%s\n' 'Gestopt. Gebruik de image-referentie uit de ACR-build.' >&2
    exit 1
  fi
  az webapp config container set "${app_args[@]}" \
    --container-image-name "$release_image_reference" --output none
  printf '%s\n' 'Azure heeft de imagewissel geaccepteerd.'
)
```

## 4. Controleren

```bash
(
  set -e
  app_args=(--subscription "${azure_subscription:?}" -g "${resource_group:?}" -n "${app_name:?}")
  : "${release_image_reference:?}"
  python3 scripts/verify_console_deployment.py --health-url "${app_url:?}/health" \
    --expected-commit "${release_sha:?}" --attempts 18 --retry-delay 10
  state=$(az webapp show "${app_args[@]}" --query state -o tsv)
  image=$(az webapp config show "${app_args[@]}" --query linuxFxVersion -o tsv)
  printf 'App Service: %s\nActieve image: %s\n' "$state" "$image"
  [[ "$state" == Running && "$image" == "DOCKER|$release_image_reference" ]]
)
```

Tijdens de opstart kan `/health` tijdelijk de vorige commit zien. Wacht op de einduitkomst van het begrensde verificatieblok. Controleer ook `pg_stat_activity` volgens het deploymentprotocol.

Meld aan, open Raad en klik onder **Controle na deploy** op **Controleer alle pagina's**. Wacht op de nieuwe uitslag en controleer het tijdstip en de buildreferentie. Registreer rolbeperkingen als **niet gecontroleerd**. Open daarna één bekend document in Review en voer de voor deze release afgesproken gerichte proef uit.

## Rollback

Vraag apart GO voor terugval. Gebruik de volledige referentie uit stap 1.1 in `rollback` en de destijds gemeten commit in `rollback_sha`. `--container-image-name` neemt het deel na `DOCKER|`.

```bash
(
  set -e
  app_args=(--subscription "${azure_subscription:?}" -g "${resource_group:?}" -n "${app_name:?}")
  if [[ ! "${rollback:?}" =~ ^DOCKER\|.+@sha256:[0-9a-f]{64}$ ||
        ! "${rollback_sha:?}" =~ ^[0-9a-f]{40}$ ]]; then
    printf '%s\n' 'Gestopt. Controleer de terugvaldigest en bijbehorende commit.' >&2
    exit 1
  fi
  : "${app_url:?}"
  az webapp config container set "${app_args[@]}" \
    --container-image-name "${rollback#DOCKER|}" --output none
  python3 scripts/verify_console_deployment.py --health-url "$app_url/health" \
    --expected-commit "$rollback_sha" --attempts 18 --retry-delay 10
)
```

Stond `CONSOLE_REVIEW_CARD_READS=compact` aan, en is bij de release stap 1.7 uitgevoerd? Voer dan na de terugwissel met de herstelde versie opnieuw `python scripts/prepare_review_cards.py --all` uit, en daarna dezelfde opdracht met `--check`. De voorbereide kaarten dragen anders het `producer_contract` van de nieuwere versie, en de oudere code weigert ze ("Kaartgegevens niet beschikbaar").

De PostgreSQL-toestand blijft geldig: 019 is alleen-toevoegen en oudere code negeert de tabel. Een gewijzigde `METIS_PASSAGE_FORMATION_MODE` mag na een rollback blijven staan; een semantische modus wordt door oudere code ook gelezen.
