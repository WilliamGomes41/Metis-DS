# Deploymentprotocol voor agents

Promise: elke deployment van de console volgt één route: een exacte `main`-commit als container-image, gewisseld op digest, met een vastgelegd rollbackpunt, en pas klaar na gemeten verificatie. Change class: C (agent workflow). Rewrite risk: none.

De technische stappen staan in [`docs/AZURE_RELEASE_RUNBOOK.md`](../AZURE_RELEASE_RUNBOOK.md). Dit protocol bepaalt hoe een agent die stappen aanbiedt, bewaakt en afsluit. Bij verschil wint het runbook voor de commando's en dit protocol voor de werkwijze.

## Grondregels

1. **Eén route: container op digest.** Bouw met `scripts/build_azure_release_image.sh` (`az acr build`) en wissel met de afgedrukte `release_image_reference=…@sha256:…`. De ZIP-route (`deploy-production.yml`) is niet van toepassing. Wissel nooit op een tag.
2. **Alleen een exacte `main`-commit.** Deploy een SHA die op `main` staat en waarvan de PR gemerged is met groene CI. Nooit een featurebranch, nooit een lokale wijziging.
3. **GO van de projectlead per stap die Azure wijzigt:** build, migratie, app settings, image-wissel en rollback. De agent voert die stappen niet zelf uit, maar levert de commando's en leest de uitvoer.
4. **Eén blok per stap.** Geef per bericht één commandoblok en wacht op de uitvoer. Zet het rollbackcommando nooit in hetzelfde blok als de wissel; lever het alleen apart en alleen op verzoek of bij een gefaalde verificatie.
5. **Geen geheimen of private inhoud** in GitHub, Linear of chat-samenvattingen: alleen SHA's, image-digests, versienummers, foutcodes, tellingen en duur.

## Volgorde

Elke stap heeft een stopcriterium. Faalt het, dan stopt de route; de agent meldt wat er faalde en wat het advies is.

| # | Stap | Doorgaan alleen als |
|---|---|---|
| 0 | Sessie voorbereiden (Cloud Shell is vluchtig): repository opnieuw klonen of `git fetch origin main`, venv met de requirements | `git rev-parse origin/main` geeft de te deployen SHA |
| 1 | Rollbackpunt vastleggen (runbook 1.1) | de waarde begint met `DOCKER|` en staat genoteerd |
| 2 | App settings preflight (runbook 1.2) | `release_settings_preflight.py` exit 0 |
| 3 | Geen lopende verwerking (runbook 1.3) | geen poging in uitvoering |
| 4 | Migraties en rechten (runbook 1.5) met `--runtime-role vvn-metis-console` | `verify` geeft `PASS`, geen `BLOCKED` |
| 5 | Image bouwen (runbook 2): eerst `--dry-run`, dan echt | `release_image_reference=…@sha256:…` afgedrukt |
| 6 | Wisselen op digest (runbook 3) | het commando slaagt |
| 7 | Verifiëren (zie hieronder) | alle vier de controles slagen |
| 8 | Proef in de console | één kleine actie werkt binnen redelijke tijd |
| 9 | Vastleggen in Linear met de handoff | bewijsverwijzing aanwezig |

Stappen 1.4, 1.6 en 1.7 van het runbook gelden wanneer hun voorwaarde geldt (eerste ACR-inrichting, weergavecontrole, compacte reviewkaarten).

## Verificatie

Een deployment is pas geverifieerd met alle vier:

1. `python scripts/verify_console_deployment.py --health-url <url>/health --expected-commit <sha>` drukt `deployment_verified commit=<sha>` af;
2. de app staat op `Running` en de image-referentie is de nieuwe digest;
3. de database toont geen hangende transacties van de app (`pg_stat_activity`: geen `idle in transaction` of query ouder dan een minuut);
4. de versie in de console (`generatie.release.build`, zie `config/console_release.json`) hoort bij de SHA.

Daarna de proef: aanmelden, "Controle na deploy" in Raad, en één bekend document in Review openen. Raakt de release een schrijf- of leesroute op grote documenten, doe dan één kleine actie met één klik en lees de duur van `request_finished` in de logs.

## Als het misgaat

- **Verificatie faalt of de console blokkeert:** lever het rollbackblok uit het runbook met de digest uit stap 1, na GO. Daarna opnieuw verifiëren tegen de vorige SHA.
- **Een transactie blokkeert aanmelden of andere gebruikers:** zoek de backend in `pg_stat_activity`, en beëindig hem alleen met GO via `pg_terminate_backend(<pid>)`. Leg pid, duur en query-soort vast, zonder inhoud.
- **Per ongeluk rollback uitgevoerd:** wissel opnieuw naar de nieuwe digest en verifieer opnieuw.
- **Incident:** leg oorzaak en herstel vast in het change contract en in de PR van de fix (zie [linear-github-handoff](linear-github-handoff.md)).

## Afsluiten

Werk Linear bij vóór de volgende stap, volgens [linear-github-handoff](linear-github-handoff.md). Het werkpakket gaat pas naar Done met gemerged + gedeployed + geverifieerd. In de handoff staat onder `production_state`: de commit, het image (digest) en het rollbackpunt (digest). De bewijsverwijzing is de regel `deployment_verified commit=<sha>` plus de uitkomst van de proef.
