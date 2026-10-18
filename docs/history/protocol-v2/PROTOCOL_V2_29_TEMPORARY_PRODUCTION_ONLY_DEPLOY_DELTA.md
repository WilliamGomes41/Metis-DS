# Protocol v2.29 — tijdelijke productie-only deployment

## Besluit

De eigenaar heeft op 5 september 2026 besloten de Azure-testomgeving pas in
de toekomst in te richten. Tot dat moment MAG de handmatige productie-workflow
zonder `vvn-metis-console-test` en zonder `METIS_TEST_APP_READY` worden gestart.
Dit is een begrensde supersessie van uitsluitend de v2.22-eis dat productie
door het bestaan van de test-App Service wordt geblokkeerd.

## Blijvende productiepoorten

Productie blijft handmatig en MUST een volledige commit-SHA ontvangen. Die SHA
MUST exact worden uitgecheckt en MUST op `main` liggen. De workflow MUST de
repository-preflight en volledige tests uitvoeren, MUST uitsluitend de aparte
`metis-deploy-production`-identiteit gebruiken, MUST alleen naar
`vvn-metis-console` kunnen schrijven en MUST afsluiten met `/health`.
Een push of merge MUST productie niet automatisch starten.

De testworkflow blijft fail-closed totdat `vvn-metis-console-test` werkelijk
bestaat. `METIS_TEST_APP_READY` MUST NOT fictief op `true` worden gezet.

## Ongewijzigde grenzen

G2 blijft BLOCKED en `publish()` blijft G2-BLOCKED. Deze wijziging opent geen
publicatie en verandert geen bron-, kennis-, review- of servingwet.
