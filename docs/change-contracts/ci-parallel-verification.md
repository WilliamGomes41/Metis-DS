# Parallelle verificatie en herbruikbaar deploymentpakket

Change class: C
Rewrite risk: none
Touches lifecycle invariants: no
Promise: Behoud alle bestaande controles, isoleer herpogingen van browser- en
suitewerk en deploy uitsluitend het pakket van een geslaagde main-CI-run.
Proof: tests/test_ci_test_shards.py, tests/test_verified_deploy_artifact.py,
tests/test_release_control_preflight.py en tests/test_wave_c_deploy_packaging.py.

## Bestaande uitvoering en keuze vóór implementatie

Op fd15afc bezit één matrixjob per Python-versie de volledige suite, exports
van bestaand JUnit-bewijs en (3.12) de browserproeven. Test en productie bouwen
ieder opnieuw na opnieuw pytest. Alle Azure-acties blijven handmatig; main
merge mag nooit automatisch deployen. Omgevingsgoedkeuring, main-ancestry,
gescheiden OIDC-identiteiten en de inactieve test-app blijven verplicht.

Twee ontwerpen, door één model vergeleken:

1. pytest-xdist binnen de bestaande job. Minder workflowwijzigingen, maar een
   herpoging herhaalt alle workers; procesconcurrentie deelt runner/PG en heeft
   nieuwe fixture-isolatievereisten. De late browsercontrole blijft gekoppeld.
2. Vier zelfstandige runners per Python-versie, aparte browserjob en een
   verzameljob onder de bestaande `test (3.12)` / `test (3.13)` checknamen.
   Meer installatie- en collectiekosten, maar PG en processtaat blijven per job
   geïsoleerd en GitHub kan afzonderlijke mislukte delen herhalen.

Kies 2. Een vaste tijdmeting stuurt alleen de verdeling, nooit de selectie.
Iedere run verzamelt de hele suite; nieuwe bestanden worden automatisch
verdeeld. De verzamelaar eist alle vier delen, dezelfde commit/Python/collectie,
geen ontbrekende of dubbele test-ID's, afgesloten uitvoering en nul PG-skips.
Bestanden blijven bijeen en behouden hun testvolgorde. JUnit wordt samengevoegd;
de zeven bestaande native bewijscontroles blijven dat bewijs gebruiken.
Bewijsuploads gebruiken `overwrite: true`: upload-artifact v4 zou anders bij
een herpoging van een mislukte job op de al bestaande naam met HTTP 409 stoppen.
De pakketnaam bevat de runpoging en het deploymentpakket wordt niet overschreven.

Gebruik: `measure_test_suite.py --shard-index 0 --shard-count 4 --output ...`;
`ci_test_shards.py merge --directory ... --count 4 --python-version 3.12
--commit <sha> --output output/d6a-after.json`. Zonder shardargumenten blijft
de runner de volledige suite uitvoeren. `seconds` van het gezamenlijke rapport
is de som van de delen voor de bestaande kostenvergelijking; `wall_seconds`
is de langzaamste suite, exclusief queue/installatie. Pytest-collectie telt mee.

## Pakket en deployment

Alleen push-CI op main bouwt na geslaagde suite-, browser-, contract-, API- en
characterizationcontroles één ZIP. Een geïsoleerde Python 3.12-importproef
controleert de verpakte applicatie en dependencies zonder checkout/site-packages
als terugval. Manifest: commit, repository, CI-run, poging, SHA-256 en proefresultaat.
Dit is pakketcontrole naast de domeinsuite op dezelfde broncommit, geen claim
dat het volledige inhoudelijke Azure-traject is uitgevoerd.

Beide handmatige deployments vragen `commit_sha` en `ci_run_id`. Vóór Azure-login:
verifieer via GitHub dat die voltooide, geslaagde run van ci.yml een main-push
van dezelfde repository en exacte commit is; haal het pakket van die poging op;
controleer manifest, hash en commitmarker. Geen terugval naar zelf bouwen of
een andere run. Verlopen/ontbrekend bewijs blokkeert deployment. Hetzelfde pakket
kan naar test en productie. Startup-/health-/commitcontrole blijft na deployment.

Geen nieuwe productie-infrastructuur, migratie of productcodewijziging. CI heeft
contents:read; deployments krijgen daarnaast actions:read voor bewijsdownload.
Alleen deployment behoudt id-token:write. Runtime-data blijft buiten het ZIP.

## Foutscenario's en bewijs

| Scenario | Vereiste controle |
| --- | --- |
| Ontbrekend/dubbel shard, andere commit/collectie, afgebroken uitvoering | Verzamelaar weigert; geen groene testcheck/pakket |
| Nieuwe test ontbreekt in timings | Toch eenmaal geselecteerd en uitgevoerd |
| Shard faalt of PG-test wordt overgeslagen | Bewijs blijft bewaard; gezamenlijke check faalt |
| Browser faalt achteraf | Eigen job herhalen; geslaagde suites blijven behouden |
| PR-/andere workflow, SHA, repository of onvoltooide run aangeleverd | Deployment weigert vóór Azure |
| ZIP/manifest gewijzigd of onjuist commitlabel | Hash-/identiteitscontrole weigert |

Rollback: workflow/scripts terugdraaien; geen duurzame domeintoestand verandert.
De classificatie van de bestaande leesarchitectuur-PR blijft B/high en NO-GO.
Deze CI-wijziging levert geen Azure-vrijgavebewijs. De gemeten 24 minuten lokaal
zijn een historische baseline, geen gegarandeerde GitHub-doorlooptijd. Vier
gelijktijdige runners kunnen op runnercapaciteit wachten; dat moet live gemeten
worden. De lopende oude run wordt door lokaal werk niet aangepast.

## Uitgevoerde verificatie

De volledige lokale verzameling is in vier delen uitgevoerd: **5.782 passed,
29 skipped, 3 xfailed en 3 subtests passed**; nul PostgreSQL-skips. Alle 5.814
test-ID's zijn eenmaal geselecteerd en afgesloten. De verzamelaar en alle zeven
ongewijzigde native bewijscontroles slagen. De browserjob voert afzonderlijk alle
zes browsercases groen uit (112,78 s); de zes browser-skips uit de suite tellen
niet als bewijs. De 12 Docling- en 11 Bend-skips blijven aan hun bestaande
afzonderlijke workflows voorbehouden; drie bestaande B23-xfails zijn geen bewijs.

De vier delen meten 437,089 / 364,206 / 437,003 / 412,884 s. Inclusief lokale
serverstart en orchestration is de doorlooptijd **437,971 s (7:18)**. De som
van de suiteprocessen is 1.651,182 s. Vergelijking met de eerdere lokale run
van 1.421,55 s (23:42): korter wachten, maar geen besparing van dezelfde omvang
in runner-minuten. Het betreft één historische en één parallelle lokale run,
geen herhaalde A/B-proef; GitHub-installatie, wachtrij en overige workflows
kunnen de werkelijke doorlooptijd bepalen.

Startrevision van de complete uitvoering: `2539811`. De laatste metadatafix
voor artifact-herpogingen, de aanvullende assertie en het dev-extra zijn
afzonderlijk met de 69 gerichte contractcases en actionlint gecontroleerd.
Het echte pakket van `cfcf81b` slaagt voor de geïsoleerde importproef.
Hash- en CI-identiteitsmutaties worden door de gerichte tests ontdekt.
Architectuur-, release-control-, repository-, API-compatibiliteits- en
compilecontroles slagen. Details, test-ID-digest, hashes, eerdere mislukte
proeven en bewijsgrenzen staan in `ci_parallel_verification_2026_10_24` van
`console-read-architecture-evidence.json`.

Nog niet bewezen: GitHub-doorlooptijd van de nieuwe indeling, de eerste
main-pakketjob, artifactdownload tussen runs en Azure-startup na deployment.
Geen merge, deployment of gewijzigde vrijgavebeslissing uitgevoerd.
