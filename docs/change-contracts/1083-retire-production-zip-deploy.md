# #1083 — legacy-productie-ZIP begrenzen vóór definitieve uitfasering

Change class: B
Promise: bestaande Python-hosting behoudt de tijdelijke code-updateroute, terwijl de bijgewerkte ZIP-workflow containerhosting en onbekende runtimes vóór settings of deployment weigert.
Proof: uitvoering van de echte workflowguard en mutatiecommando's met een geïnstrumenteerde Azure-CLI; geldige Python-runtime, containers, onbekende waarden en leesfouten; behoud van exacte-CI-/artifact-, identiteits- en healthchecks.
Touches lifecycle invariants: no
Rewrite risk: none

## Besluit en correctie

William gaf op 15 november 2026 opdracht stap 1 van het aanpassingsplan uit te
voeren en daarna de review van PR #1084 te corrigeren. [GitHub #1083](https://github.com/WilliamGomes41/Metis-DS/issues/1083)
en MET-83 houden de volledige uitfasering open.

De eerste versie (`6ff04c1d`) wees iedere productie-ZIP-aanroep af. De P1-review
liet een ongedekte voorwaarde zien: het container-runbook ondersteunt alleen
container → container, en vereist voor een eerste Python/ZIP → containerovergang
een eigen rollbackplan en capaciteitsproef. De actuele productiehosting is niet
vastgesteld; groen repositorybewijs bewijst die overgang niet.

De gecorrigeerde slice volgt de reviewoptie **behoud de bestaande route totdat
de eerste containerovergang bewezen is**. Er wordt geen migratieplan verzonnen
of een capaciteitsproef als uitgevoerd gepresenteerd. Ontbrekend operationeel
bewijs blijft onder de bestaande [#695](https://github.com/WilliamGomes41/Metis-DS/issues/695)
en [#696](https://github.com/WilliamGomes41/Metis-DS/issues/696). Definitieve
verwijdering blijft resterend werk van #1083; deze PR sluit dat issue niet.

## Uitvoering en grenzen

De bestaande productieworkflow behoudt handmatige dispatch, de production-environment,
exacte main-CI-/artifactcontrole, gescheiden OIDC-identiteit en versiecontrole.
Na Azure-login leest één nieuwe shellstap de actuele `linuxFxVersion`, vóór de
bestaande app-settingmutaties en ZIP-deployment:

- Exact `PYTHON|3.13`: de bestaande legacy-code-updateroute kan doorgaan.
- Containerhosting, een andere/lege/ontbrekende waarde of een leesfout: geen
  app-settingmutatie en geen ZIP-deployment.

De guard staat in de workflow zelf. Hij blijft daardoor beschikbaar als de
gecontroleerde ZIP een oudere main-commit zonder deze guard bevat. De CLI-uitvoer
bevat alleen een vaste toestemmings-/weigeringscode, geen runtimecoördinaten.
Een read-only runtimecheck is geen lock tegen gelijktijdige externe Azure-mutaties;
bestaande handmatige GO-, review- en coördinatievoorwaarden blijven gelden.

De runbooks onderscheiden de actuele hosting vóór routekeuze. De bestaande
containerprocedure behoudt haar STOP voor een onbewezen eerste overgang. Er
wordt geen onbewaakt handmatig productie-ZIP-deploycommando aangeboden.

Containerbuildscript, Dockerfile, CI-packagebouw, testworkflow, artifactverificatie,
identiteitslogica en applicatiecode blijven ongewijzigd. Er zijn geen wijzigingen
in duurzame domeintoestand, lifecycle, schema, opslag of runtime-authority.

## Bewijs en resterend werk

De guardtest faalde eerst op de bestaande workflow zonder runtimeguard.
De test voert daarna de **echte** guard en beide **echte** mutatiecommando's uit
met een lokale fake `az`: legacy-Python bereikt de settings en ZIP-deploy,
container/unknown/read-error bereikt uitsluitend de read-only configquery.
Er wordt geen echte Azure-CLI of GitHub-deployment aangeroepen.

Bestaande productie-ZIP-bewijzen voor main-ancestry, artifactintegriteit, gescheiden
identiteiten en exacte health-SHA zijn behouden. Container- en cutoverhealthchecks
blijven aanvullend getest, met een oude SHA die HTTP 200 retourneert en met een
URL met afsluitende slash. Testuitkomsten en actuele head staan in de PR.

De gecombineerde lokale controle van de correctie telt 183 geslaagde tests,
nul failures/errors/skips (Python 3.13, eigen PostgreSQL 17, 69,06 seconden).
Een geïsoleerde mutatie die alle runtimes toelaat wordt door de containertest
afgewezen omdat settings en deployment dan ten onrechte bereikbaar worden.

Historisch: de eerdere 171 lokale tests en GitHub-CI waren groen op `6ff04c1d`.
De oude volledige lokale run leverde geen eindrapport en telt niet als PASS.
Dit bewijs vervangt de verificatie van de gecorrigeerde head niet.

Geen Azure-resources, rechten, settings, credentials, migraties, imagebuilds of
imagewissels zijn in deze uitvoering gewijzigd. Historische workflowrefs en
al gestarte runs worden niet ingetrokken. Geen eigen merge of deployment.
