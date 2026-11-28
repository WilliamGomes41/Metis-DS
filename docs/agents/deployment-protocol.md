# Deploymentprotocol voor agents en Cloud Shell

Promise: containerreleases volgen één route: een exacte `main`-commit als image, gewisseld op digest, met een vastgelegd rollbackpunt en gemeten verificatie. Een bestaande Python-installatie behoudt de technisch begrensde legacy-route totdat de eerste containerovergang bewezen is. Change class: C (agent workflow). Rewrite risk: none.

De technische stappen staan in [`docs/AZURE_RELEASE_RUNBOOK.md`](../AZURE_RELEASE_RUNBOOK.md). Dit protocol bepaalt hoe een agent die stappen aanbiedt, bewaakt en afsluit. Bij verschil wint het runbook voor de commando's en dit protocol voor de werkwijze.

## Grondregels

1. **Containerreleases: container op digest.** Bouw met `scripts/build_azure_release_image.sh` (`az acr build`) en wissel met de afgedrukte `release_image_reference=…@sha256:…`. De ZIP-route (`deploy-production.yml`) is technisch begrensd tot `PYTHON|3.13`; de workflow weigert containerhosting en onbekende/ontbrekende runtimewaarden vóór settings of deployment. Stel de actuele hosting eerst read-only vast. Bij `PYTHON|3.13` blijft de tijdelijke code-updateroute behouden, maar stopt de eerste containerovergang totdat een eigen rollbackplan en capaciteitsproef zijn geaccepteerd (runbook 1.1). Verwijder de legacy-route pas na die bewezen overgang. Wissel nooit op een tag.
2. **Alleen een exacte `main`-commit.** Deploy een SHA die op `main` staat en waarvan de PR gemerged is met groene CI. Nooit een featurebranch, nooit een lokale wijziging.
3. **GO van de projectlead per stap die Azure wijzigt:** build, migratie, app settings, tijdelijke firewalltoegang, image-wissel en rollback. De projectlead geeft die GO per mutatie. De agent levert het commandoblok en verwerkt de uitvoer. De operator voert het uit.
4. **Eén blok per fase of afzonderlijk goedgekeurde mutatie.** Bundel samenhangende alleen-lezen controles met één resultaat en behoud de stopcriteria. Geef in chat één uitvoerbaar blok per bericht. Verwerk de uitvoer voordat je de volgende afhankelijke opdracht geeft. Zet het rollbackcommando nooit in hetzelfde blok als de wissel. Lever rollback apart op verzoek of bij een gefaalde verificatie.
5. **Geen geheimen of private inhoud** in GitHub, Linear of chat-samenvattingen: alleen SHA's, image-digests, versienummers, foutcodes, tellingen en duur.

## Volgorde

Elke stap heeft een stopcriterium. Faalt het, stop dan bij die stap en geef de laatst bevestigde productiestatus en de eerstvolgende controle. Houd de fase-uitvoer kort en bewaar het bewijs onder de releasecommit in het cutoververslag.

| # | Stap | Doorgaan alleen als |
|---|---|---|
| 0 | Sessie voorbereiden. Herstel zo nodig de checkout en venv in vluchtige Cloud Shell. Leg de GitHub-verwijzing naar deze cutover vast en open de registratie in Linear. | Doel-SHA, afkomst van `main`, groene CI en doelomgeving zijn bevestigd. |
| 1 | Rollbackpunt vastleggen (runbook 1.1) | De huidige commit uit `/health` en de volledige `DOCKER\|…@sha256:…`-referentie staan samen in de registratie. |
| 2 | App settings preflight (runbook 1.2) | `release_settings_preflight.py` exit 0 |
| 3 | Geen lopende verwerking (runbook 1.3) | geen poging in uitvoering |
| 4 | Migraties en rechten (runbook 1.5) met `--runtime-role vvn-metis-console` | `verify` geeft `PASS`, geen `BLOCKED`; ook het rechtenprofiel voor `public` en `api_access` is toegepast en geverifieerd met de runtime-identiteit; ontbrekend bewijs = STOP |
| 5 | Image bouwen (runbook 2). Pin dezelfde SHA bij de dry-run en bij de goedgekeurde ACR-build. | De build drukt `release_image_reference=…@sha256:…` af. Leg ook het build-ID en de duur vast als ze beschikbaar zijn. |
| 6 | Wisselen op digest (runbook 3). Bevestig vlak vóór de wissel opnieuw `0` lopende pogingen, inclusief bronvoorbereiding en handmatige bouw. | De actieve image komt overeen met het vastgelegde terugvalpunt, de nieuwe digest is bekend en de GO voor deze wissel is vastgelegd. Het wisselcommando slaagt. |
| 7 | Verifiëren (zie hieronder) | alle vier de controles slagen |
| 8 | Proef in de console | één kleine actie werkt binnen redelijke tijd |
| 9 | Vastleggen in Linear met de handoff | bewijsverwijzing aanwezig |

Bundel de alleen-lezen controles van hosting, rollback, app-instellingen en ACR-toegang. Bundel de databasetellingen en `verify` die in hetzelfde controlemoment passen. Als tijdelijk PostgreSQL-firewalltoegang nodig is, volg dan het runbook voor begrensde verbindingspogingen en gecontroleerde opruiming. Plan de hertelling vlak vóór de wissel en gebruik het eerdere resultaat voor de voorbereiding. Geef het Azure-wisselcommando apart.

Controleer ACR-toegang en de poort ook bij een bestaande inrichting. De aanvullende checks voor weergavecontrole en compacte reviewkaarten gelden wanneer die opties actief zijn, zoals beschreven in het runbook. Zoek eerder toegepast rechtenbewijs vóór de build op in de registratie en controleer of het dezelfde database, runtime-identiteit en het geldende profiel dekt. Leg de bewijsverwijzing vast bij deze release.

## Verificatie

Een deployment is pas geverifieerd met alle vier:

1. `scripts/verify_console_deployment.py` drukt `deployment_verified commit=<sha>` af. Gebruik de begrensde retry uit het runbook tijdens de opstart. Een commitmismatch binnen die pogingreeks houdt de verificatie open.
2. De app staat op `Running` en de geconfigureerde image komt exact overeen met de nieuwe digest.
3. De database toont geen hangende transacties van de app in `pg_stat_activity`. Leg de aantallen zichtbare appsessies, open transacties en actieve queries ouder dan één minuut vast. Bij nul appsessies beschrijft de uitslag alleen het meetmoment.
4. De versie in de console (`generatie.release.build`, zie `config/console_release.json`) hoort bij de SHA.

Start in Raad bewust een nieuwe **Controle na deploy** en leg tijdstip, versie, buildreferentie en uitkomsten vast. Raad kan de vorige uitslag per browsertabblad tonen. Gebruik voor de registratie de nieuw gestarte meting met de verwachte commit. Open ook één bekend document in Review. Voor een gewijzigde schrijf- of leesroute op grote documenten voer je één kleine handeling uit op een geschikt testdocument en noteer je de duur van `request_finished` in de logs.

## Als het misgaat

- **Verificatie faalt of de console blokkeert:** lever het rollbackblok uit het runbook met de digest uit stap 1, na GO. Daarna opnieuw verifiëren tegen de vorige SHA.
- **Een transactie blokkeert aanmelden of andere gebruikers:** zoek de backend in `pg_stat_activity`, en beëindig hem alleen met GO via `pg_terminate_backend(<pid>)`. Leg pid, duur en query-soort vast, zonder inhoud.
- **Per ongeluk rollback uitgevoerd:** wissel opnieuw naar de nieuwe digest en verifieer opnieuw.
- **Incident:** leg oorzaak en herstel vast in het change contract en in de PR van de fix (zie [linear-github-handoff](linear-github-handoff.md)).

## Afsluiten

Vul de bestaande cutoverregistratie tijdens de uitrol aan, met een verwijzing vanuit het gekoppelde GitHub-issue. Werk Linear bij vóór de volgende stap volgens de [GitHub–Linear-overdracht](linear-github-handoff.md). Noteer onder `production_state` de commit, de actieve digest en de terugvaldigest. Voeg de verificatieregel, de Raad-meting en de gerichte proef toe. Noteer ontbrekende praktijkchecks als open, ook als de nieuwe commit al draait.

Done = gemerged op main (met `Closes #N` + `Fixes MET-N`). Forge zet het label `live` op het issue en het Linear-ticket na deze verificatie.
