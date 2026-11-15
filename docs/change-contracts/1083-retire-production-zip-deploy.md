# #1083 — productie-ZIP-deployment afsluiten

Change class: B
Promise: de bijgewerkte productie-ZIP-workflow kan geen Azure-actie uitvoeren; de bestaande container-op-digestprocedure blijft beschikbaar.
Proof: rood/groen op workflowbevoegdheden en actieve runbookcommando's; lokale uitvoering van de afwijzing zonder Azure-aanroep; release-, identiteits-, artifact- en PostgreSQL-regressiecontroles.
Touches lifecycle invariants: no
Rewrite risk: none

## Besluit en bestaande uitvoering

William gaf op 15 november 2026 opdracht stap 1 van het aanpassingsplan uit te
voeren. Scope en acceptatie staan in [GitHub #1083](https://github.com/WilliamGomes41/Metis-DS/issues/1083), werkbord MET-83.

`deploy-production.yml` kon een handmatige dispatch ontvangen, een exacte
main-CI-ZIP downloaden, met Azure OIDC aanmelden en `az webapp deploy --type zip`
uitvoeren. Het cutoverrunbook bood daarnaast dezelfde ZIP-mutatie als handmatig
commando. De tijdelijke v2.29-route botste met de bestaande actuele
containerprocedure, die een volledige Docling-runtime en wisselen op digest vereist.

## Begrensde wijziging

De workflow blijft herkenbaar voor bestaande aanroepen, maar bevat uitsluitend
een onvoorwaardelijke afwijzing (`production_zip_deploy_retired`, exit 1).
`permissions: {}` geeft geen OIDC-tokenbevoegdheid. Er zijn geen checkouts,
actions, environment-bindingen, credentials of Azure-stappen meer. Er is geen
nieuw productie-deploymechanisme toegevoegd.

De actieve runbooks en ROADMAP verwijzen voor productie naar de bestaande
containerprocedure. Het cutoverrunbook behoudt de read-only preflight,
migratie-/rechtenvoorwaarden en gemeten versiecontrole, zonder een alternatieve
ZIP-uitrol aan te bieden.

De test-ZIP-workflow, CI-packagebouw, artifactintegriteitscontrole, gescheiden
identiteiten, `scripts/build_azure_release_image.sh` en `Dockerfile.docling`
blijven ongewijzigd. Tests voor de vervallen productieworkflow worden vervangen
door bewijs van afwijzing. Exacte-commitcontroles blijven uitgevoerd voor de
testworkflow en de bestaande container-/cutoverprocedure, inclusief een oude
SHA die HTTP 200 teruggeeft maar toch moet worden afgewezen.

Alleen repositorybestanden wijzigen. Geen Azure-resources, rollen, App Settings,
secrets, runtime-data of publicatievoorwaarden worden aangepast.

## Verificatie en grenzen

- De nieuwe afwijzingstest faalde vóór de wijziging op de aanwezige OIDC-rechten.
- De runbooktest faalde vóór de wijziging op het uitvoerbare productie-ZIP-commando.
- Beide tests slagen na de wijziging. De werkelijke afwijzende shellstap draait
  lokaal met geldige legacy-instellingen en een geïnstrumenteerde `az`; exit 1 en
  nul Azure-aanroepen zijn vereist. Er wordt geen GitHub-deployrun gestart.
- De gecombineerde eindcontrole telt 171 geslaagde tests, nul failures/errors/skips
  (Python 3.13, eigen PostgreSQL 17, 54,92 seconden). Daaronder vallen de echte
  packagebouw met dependencies, artifactintegriteit, de scheiding van identiteiten,
  release-image-dry-runs en de bestaande PostgreSQL-migratie-/rechtencontroles.
- Repositorypreflight en architectuurcontrole slagen. De volledige lokale suite,
  release-controlcontrole op de uiteindelijke commit en exacte-head-CI worden met
  hun daadwerkelijke uitkomst in de PR vastgelegd. Een lokale test is geen Azure-proef.

Dit sluit de **bijgewerkte** workflow af zodra de wijziging gemerged is.
Historische refs en al gestarte runs worden hiermee niet ingetrokken; bestaande
externe credentials en Azure-rechten worden niet gewijzigd. Geen claim dat een
repositorywijziging alle buiten deze route aanwezige deploybevoegdheden intrekt.

De bestaande containerprocedure heeft haar eigen GO per Azure-mutatie,
rollbackpunt en runtimeverificatie. Deze uitvoering doet geen merge, imagebuild,
imagewissel, migratie of deployment. Terugdraaien van deze repositorywijziging
zou de uitgesloten route heropenen en is geen voorgestelde herstelactie.
