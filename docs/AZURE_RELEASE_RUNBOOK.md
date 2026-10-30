# Azure-release van de console (Docling-image)

Dit runbook beschrijft hoe een exacte `main`-commit als container-image naar Azure gaat. Het is dezelfde route als in `docs/change-contracts/zorgmaatje.md`: `az acr build` met `Dockerfile.docling --target runtime` en daarna de app wisselen via de digest. De ZIP-route (`deploy-production.yml`) levert geen Docling-runtime en is hier niet van toepassing.

Elke stap die Azure wijzigt (build, migratie, app settings, image-wissel) gebeurt alleen met GO van William.

## Benodigd

- `az` aangemeld met een identiteit die mag bouwen in de ACR en de web app mag configureren.
- Namen: ACR (`<acr>`), image-repository (`<repo>`), resourcegroep (`<rg>`), web app (`<app>`), app-URL (`<url>`).
- Een checkout van deze repository met `origin/main` bijgewerkt.

## 1. Vooraf

1. Leg de huidige image-referentie vast als rollbackpunt:
   `az webapp config show -g <rg> -n <app> --query linuxFxVersion -o tsv`
   Begint die waarde niet met `DOCKER|` (bijvoorbeeld `PYTHON|3.13`, de ZIP-route), stop dan. Dit runbook wisselt alleen van container naar container; een eerste overstap van ZIP naar container vraagt een eigen plan met een eigen rollback (`az webapp config set --linux-fx-version`) en een capaciteitsproef voor Docling.
2. Controleer de app settings:
   `az webapp config appsettings list -g <rg> -n <app> -o json | python scripts/release_settings_preflight.py`
   Exit 0 is klaar. Exit 2 blokkeert de release. De belangrijkste weigering is `passage_formation_mode_retired`: `METIS_PASSAGE_FORMATION_MODE=deterministic-v1` laat sinds #817 elke nieuwe verwerking falen, ook beslisbomen. Zet de waarde dan op een semantische modus (`semantic-source-bound-v1`, `-v2` of `-v3`) of verwijder haar (leeg betekent `semantic-source-bound-v2`). De uitvoer toont geen geheime waarden.
3. Controleer dat er geen verwerking loopt. Een image-wissel herstart de app; een lopende poging wordt dan afgebroken en telt mee als poging.
4. Controleer dat de app een image uit deze ACR mag trekken en op de goede poort luistert. Begint de referentie uit stap 1.1 al met `DOCKER|` en de login-server van de ACR, dan is dit eerder ingericht; controleer het toch:
   - `az webapp config show -g <rg> -n <app> --query acrUseManagedIdentityCreds` geeft `true`, en de identiteit van de app heeft de rol `AcrPull` op de ACR (`az role assignment list --assignee <principal-id> --scope <acr-resource-id>`). Anders kan de app het nieuwe image niet ophalen.
   - De app setting `WEBSITES_PORT` is `8000`. Gunicorn luistert in het image op `${PORT:-8000}`; App Service gaat zonder deze setting uit van poort 80.
5. Migratie 019 (`workflow.view_checks`, alleen-toevoegen). Let op: `apply_workflow_postgres_migrations.py verify` controleert 019 niet. Controleer daarom als database-beheerder:
   - `SELECT to_regclass('workflow.view_checks');` mag niet leeg zijn. Is hij leeg: `plan`, daarna `apply` met `--confirm-target` en `--confirm-digest`, daarna `verify`.
   - `SELECT bool_and(has_table_privilege('vvn-metis-console', 'workflow.view_checks', p)) FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE']) AS p;` geeft `true` (één lijst in één aanroep zou al `true` geven bij één recht). Anders: `GRANT SELECT, INSERT, UPDATE, DELETE ON workflow.view_checks TO "vvn-metis-console";`
   Zonder tabel of recht start de app niet zodra `METIS_VIEW_CHECK_ORIGIN` gezet is.
6. Weergavecontrole: dit runbook zet haar niet aan. Rapporteert de preflight `"view_check": "enabled"`, controleer dan ook wat de preflight niet kan zien, volgens `docs/change-contracts/zorgmaatje.md`: de private evidence-container bestaat, heeft een lifecycle-regel van 7 dagen, en de app-identiteit heeft daarop `Storage Blob Data Contributor`. Doe na de wissel één weergavecontrole. Aanzetten is een aparte stap met GO.
7. Compacte reviewkaarten: staat `CONSOLE_REVIEW_CARD_READS=compact` aan, en wijzigt de release het `producer_contract` van `review_card_facts_v1`? Dat gebeurt bijvoorbeeld bij een nieuwe `source_containers_v1.VERSION`. Voer dan direct na de wissel `python scripts/prepare_review_cards.py --all` uit, en daarna dezelfde opdracht met `--check`. Zonder die stap tonen de kaarten "Kaartgegevens niet beschikbaar", omdat GET niets opnieuw opbouwt. In de standaardstand (`legacy`) is deze stap niet nodig.

## 2. Image bouwen

```bash
bash scripts/build_azure_release_image.sh --registry <acr> --repository <repo> --dry-run
bash scripts/build_azure_release_image.sh --registry <acr> --repository <repo>
```

Zonder `--commit` neemt het script `origin/main`. Het weigert een commit die niet op `main` staat. De build-context is een schone `git archive` plus `config/deployed_commit.txt`. Het script voegt alleen een tag toe aan de ACR en drukt `release_image_reference=<login-server>/<repo>@sha256:…` af. De login-server komt uit `az acr show --query loginServer`; met een domeinlabel is dat niet `<acr>.azurecr.io` maar bijvoorbeeld `<acr>-<hash>.azurecr.io`. Gebruik altijd de afgedrukte referentie.

## 3. Wisselen

```bash
az webapp config container set -g <rg> -n <app> \
  --container-image-name <release_image_reference>
```

## 4. Controleren

```bash
python scripts/verify_console_deployment.py --health-url <url>/health --expected-commit <sha>
```

Daarna in de console: aanmelden, Raad (het uiltje rechtsonder) openen en bij "Controle na deploy" op "Controleer alle pagina's" klikken. Alle pagina's moeten ✓ tonen; een pagina die je rol niet mag openen staat als "niet gecontroleerd". Open daarna één bekend document in Review.

## Rollback

Wissel terug naar de referentie uit stap 1.1. Die heeft de vorm `DOCKER|<login-server>/<repo>@sha256:…`; `--container-image-name` neemt alleen het deel na `DOCKER|`. Met de waarde uit stap 1.1 in `rollback`:

```bash
rollback='<volledige waarde uit stap 1.1, inclusief DOCKER|>'
az webapp config container set -g <rg> -n <app> \
  --container-image-name "${rollback#DOCKER|}"
python scripts/verify_console_deployment.py --health-url <url>/health --expected-commit <vorige sha>
```

Stond `CONSOLE_REVIEW_CARD_READS=compact` aan, en is bij de release stap 1.7 uitgevoerd? Voer dan na de terugwissel met de herstelde versie opnieuw `python scripts/prepare_review_cards.py --all` uit, en daarna dezelfde opdracht met `--check`. De voorbereide kaarten dragen anders het `producer_contract` van de nieuwere versie, en de oudere code weigert ze ("Kaartgegevens niet beschikbaar").

De PostgreSQL-toestand blijft geldig: 019 is alleen-toevoegen en oudere code negeert de tabel. Een gewijzigde `METIS_PASSAGE_FORMATION_MODE` mag na een rollback blijven staan; een semantische modus wordt door oudere code ook gelezen.
