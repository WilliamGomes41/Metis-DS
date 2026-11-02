# PostgreSQL workflow readiness — stap 8

Datum: 2026-09-12

## Verdict

**Code/CI readiness: PASS voor stap 9 (Azure cut-over voorbereiding).**

Dit is nadrukkelijk geen verklaring dat de productieomgeving al is gemigreerd of dat een echte Azure recovery-drill is geslaagd. Azure-configuratie, operationele cut-over en productieherstel blijven aparte stappen.

## Bewezen in code en CI

De gedeelde workflow-authority bestaat uit PostgreSQL voor accounts/sessies, documenten/envelopes, work objects, review-events, publish authorizations, Audit-records en Audit-secretpayloads. Immutable bronbytes blijven onder Azure Blob-authority; canonical/publication state blijft onder PostgreSQL-authority.

De migratiegolf heeft de volgende eigenschappen met echte PostgreSQL 16-tests afgedekt:

- lokale `/home/data`-bestanden zijn in volledige PostgreSQL-modus geen correctness-authority meer;
- identity-, document-, review- en resterende workflowstores hebben expliciete cut-over/migratiepaden;
- concurrerende username-creatie heeft één winnaar;
- session revoke is direct zichtbaar tussen onafhankelijke store-instanties;
- stale same-object writes worden geweigerd;
- onafhankelijke objectwijzigingen binnen dezelfde snapshot kunnen beide behouden blijven;
- review-events blijven onder concurrency één lineaire hash-chain;
- authorizations van onafhankelijke snapshots gaan niet verloren;
- workflow + canonical/publication backup/restore wordt tegen PostgreSQL 16 roundtrip getest;
- review-ledger tampering wordt fail-closed gedetecteerd;
- document/object state, publish authorizations en review-events committen in de volledige reviewworkflow nu binnen één gedeelde PostgreSQL-transactie. Een gesimuleerde uitval vóór de outer commit rolt alle drie terug.

De CI-gates blijven repository preflight, release-control mapping, compileall, architecture invariants en de volledige pytest-suite op Python 3.12 en 3.13. De stap-8 transaction-PR draaide volledig groen; Python 3.13 rapporteerde 1524 geslaagde tests.

## Waarom de gedeelde workflowtransactie nodig was

Voor stap 8 waren document/object writes, authorizations en review-ledger writes elk transactioneel op zichzelf, maar niet crash-atomair als combinatie. Exception-compensatie kon een normale fout herstellen, maar geen procesuitval tussen twee reeds gecommitte PostgreSQL-transacties.

`workflow_transaction_v1.py` laat de bestaande stores binnen één request-lokale outer PostgreSQL-transactie dezelfde verbinding lenen. Hun bestaande transacties worden savepoints. Buiten deze grens houden de stores hun bestaande zelfstandige connection-semantiek. Er is geen nieuwe service of tweede workflow-engine toegevoegd.

## Bewust niet veranderd

De topology-guard blijft actief. De ondersteunde deploymentgrens blijft voorlopig:

- één Gunicorn worker;
- één App Service instance;
- geen claim dat horizontaal schalen al operationeel is vrijgegeven.

De PostgreSQL-concurrencytests bewijzen dat de gedeelde stores de eerder geïdentificeerde races correct afhandelen, maar het verruimen van de deploymenttopologie is een aparte expliciete beslissing.

Ook zijn in stap 8 geen Azure app settings, identity/role assignments, netwerkregels, database-inhoud of Blob-inhoud gewijzigd.

## Security-observaties buiten deze migratieclaim

De consolesessiecookie is `Secure`, `HttpOnly` en `SameSite=Lax`. Een expliciete CSRF-tokenlaag en login-throttling zijn in deze stap niet als aparte beveiligingsgarantie bewezen. Dat is geen reden om de PostgreSQL-migratiecode tegen te houden zolang de console intern en binnen de bestaande toegangsgrens blijft, maar het mag niet stilzwijgend worden opgevat als bewijs voor publieke internet-exposure.

## Entry criteria voor stap 9

Stap 9 mag starten met behoud van de bestaande topology-guard en zonder productieclaims. De operationele volgorde moet minimaal bevatten:

1. actuele backup/integriteitscontrole van canonical/publication PostgreSQL en Blob authority;
2. workflow migrations `002` t/m `005` toepassen/verifiëren;
3. legacy identity, documenten, reviewstate en resterende workflowstate expliciet migreren en exact verifiëren;
4. workflowstores activeren in dependency-volgorde: identity → documents → review → remaining;
5. startup fail-closed controleren met PostgreSQL + Blob als authority;
6. smoke tests uitvoeren op Inleveren → Review → Publiceren → Documenten en Audit;
7. lokale `/home/data`-bestanden uitsluitend als mirrors/derived state behandelen;
8. geen topology-verruiming tijdens dezelfde cut-over.

## Resterende productiegrens

Na stap 9 is nog steeds een gecontroleerde productie-drill nodig. Stap 10 moet minimaal de echte Azure PostgreSQL/Blob recoveryprocedure, read-back/integriteitscontrole en rollbackprocedure bewijzen. Pas daarna kan operationele production-readiness voor deze migratieketen worden vastgesteld.
