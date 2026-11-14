# PostgreSQL in Azure: ontwerp, pstack-beoordeling en verificatie vóór implementatie

Datum: 2026-11-14. Onderzochte code: `0bbd58f2aa2b1f4a9e6dff288458ec76b4809c56`.
Status: ontwerp en lokale baseline uitgevoerd; productie-implementatie niet gestart.

## Besluiten (GO projectlead, 2026-11-14)

William gaf opdracht om het voorbereide werk te pushen en daarna te implementeren.
Uitvoeringsissue: GitHub #1074; status/handoff: MET-80 onder MET-10.
De oorspronkelijke analyse en de 54 tests hieronder horen bij de expliciet
genoemde oudere SHA. De implementatie begint vanaf actuele main
`aae99d6e` en hergebruikt de inmiddels uitgebreide verifier en migratieregistratie.
Dat oudere bewijs wordt niet als test van de actuele main gepresenteerd.

De eerste strikte regel blijft begrensd: geen UPDATE op publication_refusals,
plus gevaarlijke rolkenmerken en bereikbare rolwisselpaden. De bestaande
minimumlijsten worden niet stilzwijgend maxima. Overige privilege-maxima blijven
zichtbaar onbeoordeeld; een strict-PASS is geen volledige least-privilege-audit.
Er is geen wijziging van compositie, opslagroutes of deploymenttopologie voorzien.

## Opdracht en fasen

Verbeter de onderbouwing en het ontwerp voor runtimeprivileges, begrensde
migratielocks en TLS-serveridentiteit. Deze opdracht maakt een reviewbaar ontwerp
en voert bestaande tests en afzonderlijke lokale ontwerpcontroles uit. Zij past
geen productiecode, bestaande migraties of Azure-configuratie aan.

Pstack-route, via de `architect`-skill:

- [x] Ground: huidige aanroeppaden, bevoegdheden en transacties onderzocht.
- [x] Sketch: twee structureel verschillende kandidaten uitgewerkt en beoordeeld.
- [x] Agree: GO projectlead op 2026-11-14; uitvoering onder #1074/MET-80.
- [ ] Implement: volgt na de afzonderlijke push van dit voorbereidingsbewijs.
- [ ] Scrap: niet geactiveerd; heroverweeg bij de hieronder genoemde stopcondities.

Dit document is ontwerpdocumentatie: Class C, Rewrite risk: none. De voorgestelde
gerichte runtimewijzigingen zijn voorlopig Class B, Rewrite risk: none, zolang
zij alleen bestaande grenzen verdiepen en geen lifecycle-, herstel-, migratie-
of autorisatie-eigenaarschap vervangen. Iedere implementatieslice moet die
classificatie opnieuw aan de concrete diff toetsen. Een nieuw migratieregister,
nieuwe autorisatiegrens of gewijzigde recoverysemantiek vraagt herclassificatie.

## Ground: hoe de bestaande opzet werkt

| Begrip en eigenaar | Bestaand gedrag en aanroeppad | Ontwerpgrens |
| --- | --- | --- |
| Runtimeverbindingen | `console_asgi.py` maakt canonical- en workflowstores met een gedeelde `CachedAzurePostgresCredential`. Identity-, document- en canonicalstores gebruiken `connect_postgres`; API-access heeft een eigen `psycopg.connect`-pad. | Bestaande stores blijven eigenaar van verbindingen. De meetwrapper blijft diagnostiek. |
| Authenticatie | Azure-paden gebruiken een Entra-token, `sslmode=require` en een connectietimeout. Expliciete DSN-paden ondersteunen lokale tests. | Geen tweede tokencache; lokale test-DSN's blijven bruikbaar. |
| Schemawijzigingen | Operator-CLI `apply_workflow_postgres_migrations.py` doet plan/apply/verify. `apply_migrations` controleert de digest en voert ieder geregistreerd bestand in een transactie uit. | Geen runtime-DDL; geen stille retry; reeds gecommitte bestanden blijven gelden wanneer een later bestand faalt. |
| Rechtencontrole | `observe_runtime_privileges` leest PostgreSQL-catalogi, controleert benodigde workflowrechten en rapporteert gerichte GRANT-regels. | De controle kent zelf geen rechten toe. De huidige matrix beschrijft minima. |
| Workflowmutaties | `workflow_transaction` deelt een verbinding tussen stores; bestaande objectrevisies en locks bewaken writes. | Atomaire commits, concurrency, ledger en publicatievoorwaarden behouden. |
| Duurzame gegevens | PostgreSQL bevat workflow- en publicatiestatus; Azure Blob bevat bronbytes. | Geen bronwijziging, backfill, servingwijziging of extra authority. |

Waargenomen: het eerste-inrichtingsrunbook geeft alle DML-rechten op alle tabellen
in `public` en `workflow`. Het verbiedt elders UPDATE op `publication_refusals`.
Dat is een concrete instructietegenstrijdigheid; de werkelijk toegekende rechten
in Azure zijn onbekend. De huidige verifier beoordeelt uitsluitend `workflow`;
een PASS bewijst geen volledige rechtencontrole van `public` of `api_access`.

Waargenomen: geen van de 27 SQL-migratiebestanden stelt `lock_timeout` in of bouwt
indexen met CONCURRENTLY. Sommige leestransacties hebben al eigen statement- en
idle-timeouts. Dat maakt algemene uitspraken als "er bestaan geen timeouts" onjuist.

Onbekend: productieversie, tabelomvang, schrijfbelasting, effectieve rolhiërarchie,
netwerkconfiguratie, certificaatvertrouwen, backupinstellingen en uitgevoerde
Azure-herstelproeven. Er is geen actuele productieprestatieclaim.

## Gebruik eerst: voorgesteld operatorcontract

De onderstaande opties/signatures zijn ontwerp, geen bestaande functionaliteit.

```text
# Bestaande minimumcontrole blijft compatibel.
python scripts/apply_workflow_postgres_migrations.py verify \
  --host HOST --database DB --user ADMIN --runtime-role RUNTIME

# Nieuwe, expliciet begrensde strikte beoordeling.
python scripts/apply_workflow_postgres_migrations.py verify \
  --host HOST --database DB --user ADMIN --runtime-role RUNTIME \
  --strict-runtime-privileges

# Bestaande doel-/digestbevestiging blijft; lockwachten krijgt een grens.
python scripts/apply_workflow_postgres_migrations.py apply \
  --host HOST --database DB --user ADMIN \
  --confirm-target HOST/DB --confirm-digest DIGEST --lock-timeout-ms 5000
```

Een normale Azure-storeverbinding gebruikt na implementatie `verify-full` met
een vertrouwde certificaatketen. Geen terugval naar `require` bij een fout.
Verbindingsfouten houden bestaande veilige foutcodes en tonen geen token/DSN.
De beheerder krijgt bij privileges een inspectierapport, geen automatisch
uitgevoerd REVOKE-script. Brede of geërfde grants kunnen andere gebruikers raken.

## Twee kandidaatontwerpen en pstack-beoordeling

Kandidaat A verdiept bestaande grenzen: rechtenanalyse in de huidige verifier,
lockbegrenzing in de huidige runner en TLS-opties bij de bestaande verbindingen.
Er ontstaat geen permanente status of afzonderlijke beheerservice.

Kandidaat B voegt een zelfstandige PostgreSQL-preflightlaag toe die rechten,
migratiebeleid en TLS-beleid beoordeelt. Stores en migratierunner raadplegen deze
laag; zij voert zelf geen databasewijzigingen uit. De datavorm is een
`Target(host, database, runtime_role)` met een `PreflightReport` en findings.
Dat biedt één rapportage-ingang, maar verplaatst beleidskennis naar een extra
grens naast de bestaande owners.

| Criterium | A: bestaande grenzen | B: afzonderlijke preflightlaag |
| --- | --- | --- |
| Eenduidig eigenaarschap | Bestaande owners behouden beleid en uitvoering | Risico op beleid naast de werkelijke schrijvers |
| Aansluiting op gebruik | Huidige operator-CLI en bestaande storeaanroepen | Nieuwe CLI plus afstemming met oude ingangen |
| Verificatie | Bestaande tests direct uitbreidbaar | Extra contracten voor samenwerking tussen lagen |
| Concurrency | Begrensd wachten binnen echte DDL-transactie | Een voorafgaande PASS voorkomt latere lockconflicten niet |
| Wijzigingsomvang | Gericht; geen permanente toestand | Meer interfaces en kans op dubbele handmatige matrices |

Keuze: A. Neem van B expliciete rapportagescope, observatietijd en zichtbare
onzekerheden over. Geen scores zonder meetbasis en geen nieuwe beheerlaag om
uitsluitend rapportage te centraliseren.

De twee kandidaten zijn afzonderlijk uitgewerkt door twee echte gedelegeerde
agentuitvoeringen en door de hoofdagent gesynthetiseerd. Er zijn geen verschillende
modellen geconfigureerd; dit is geen claim van cross-modelconsensus. Hun concrete
tegenvoorbeelden zijn in dit ontwerp verwerkt: minimumrechten zijn geen maxima,
workflow is niet de gehele database, DSN/API-access zijn aparte verbindingpaden,
en directe REVOKE verwijdert geërfde bevoegdheden niet.

Geaccepteerde afweging: we behouden enkele expliciete verbindingspaden in ruil
voor lokale wijzigbaarheid en behoud van bestaande owners. Alleen identieke
Azure-TLS-opties mogen een kleine gedeelde functie krijgen; authenticatie,
verbindingslifecycle en performance-instrumentatie blijven op hun bestaande plek.

## Kernstructuren en interfaces vóór implementatielogica

### Privileges

Eén canonieke specificatie per beoordeelde relatie, met benodigde rechten en
een afzonderlijk inhoudelijk beoordeeld maximum. Schets:

```python
PrivilegeSpec(required: frozenset[str], allowed: frozenset[str] | None)
PrivilegeFinding(relation: str, privilege: str, source: str | None, reason: str)

observe_runtime_privileges(connection, role, *, view_check=False,
                          compact_cards=False, strict=False) -> dict
```

`allowed=None` betekent onbeoordeeld, niet "alle rechten toegestaan" en ook niet
"minimum automatisch maximum". Bestaande matrices/views worden, als omzetting
nodig is, uit dezelfde specificatie afgeleid. Geen twee handmatig onderhouden
tabellijsten. Catalogus-lookups zijn incidentele operatorcontroles over een kleine
set relaties; daarvoor is geen cache, achtergrondservice of database nodig.

Resultaat behoudt `missing_privileges` en `grants` en voegt `excess_privileges`,
`unsafe_role_attributes`, `inspection_scope`, `unassessed_relations` en
`observed_at` toe. Een strict-PASS mag alleen slaan op de benoemde, volledig
beoordeelde scope. Onbekende maxima of onvolledige rolinspectie blokkeren die
claim. De oude minimumcontrole behoudt haar bestaande betekenis.

Beoordeel ten minste effectieve tabelrechten, eigenaarschap, superuser/BYPASSRLS,
schema-CREATE en relevante geërfde of via SET ROLE bereikbare rollen. Onderscheid
een onmiddellijk effectief recht van een recht dat pas na rolwisseling bestaat.
Beoordeel ook TRUNCATE, REFERENCES en TRIGGER voordat een exact minimum wordt
geclaimd. De eerste harde inhoudelijke regel is: geen UPDATE op
`workflow.publication_refusals`. DELETE blijft onderdeel van het bestaande
retentiecontract; dit ontwerp splitst die bevoegdheid niet automatisch af.

Public/canonical en api_access krijgen een expliciete inventarisatiestap van
hun echte writers en benodigde rechten. Tot die voltooid is, blijven zij buiten
een strikte workflow-PASS en worden ze als niet beoordeeld vermeld. Geen
generieke regel "audit mag nooit UPDATE": bestaande stores verschillen hierin.

PostgreSQL blijft eigenaar van actuele bevoegdheden. Een rapport is een
tijdgebonden observatie; na een beheerwijziging moet opnieuw worden gecontroleerd.
Automatisch intrekken of een eerder PASS als uitvoeringsbevoegdheid gebruiken
is uitgesloten. Benodigde directe SQL, uitsluitend als beoordeeld voorbeeld:

```sql
REVOKE UPDATE ON workflow.publication_refusals FROM "vvn-metis-console";
```

Die regel is alleen afdoende als de rol het recht niet via andere bronnen houdt.
Inspecteer die bronnen eerst en controleer daarna opnieuw de effectieve rechten.

### Migratielocks

```python
apply_migrations(connection, *, paths, expected_digest,
                 lock_timeout_ms: int = 5000) -> dict
```

Per bestaande bestandstransactie: valideer de timeout als positief geheel getal,
stel transaction-local `set_config('lock_timeout', '5000ms', true)` in, voer het
ongewijzigde bestand uit en commit of rollback zoals nu. Nul, negatieve waarden
en niet-gehele invoer worden geweigerd. De CLI kiest standaard 5000 ms; dit is
een operationeel startpunt, geen afgeleide productie-SLA.

Bij SQLSTATE 55P03: behoud de bestaande publieke foutcode en bestandsnaam;
rapporteer de begrensde lockfout zonder gevoelige SQL-parameters. Geen automatische
retry. Inspecteer een blokkade, wacht tot zij is verholpen en herhaal de bestaande
idempotente route. Vorige bestanden kunnen al gecommit zijn; geen claim van één
alles-of-niets-transactie over de gehele reeks.

`lock_timeout` begrenst lockwachten, niet totale looptijd of alle wachttijd van
applicatieverkeer. Er komt geen ongemotiveerde globale statement-timeout van
vijf seconden. Concurrente indexbouw blijft een afzonderlijke beslissing voor
een concreet grote, actieve tabel: de huidige wrapper ondersteunt haar niet.
Een nieuw uitvoeringspad daarvoor valt buiten deze eerste implementatie.

### TLS

Inventariseer en dek de Azure-verbindingen af in canonical, workflow identity,
workflow documents (inclusief afgeleide stores), API-access en `connect_entra`.
De voorgestelde kleine herbruikbare waarde is een set libpq-TLS-opties:
`sslmode=verify-full` plus een vooraf geverifieerde trust-root/configuratie.
De concrete trust-rootkeuze wordt in het werkelijke deploymentimage vastgesteld;
dit ontwerp verzint geen Azure-certificaatbestand of permanent certificaat.

Gebruik DNS-hostnames die bij het servercertificaat horen. Een expliciete lokale
test-DSN behoudt zijn eigen TLS-instellingen. Inventariseer productie-DSN-gebruik
apart: een productie-DSN mag verplichte serveridentiteitscontrole niet omzeilen.
Een onbereikbare server, onjuiste hostname, ontbrekende trust-root of onbetrouwbare
CA faalt gesloten. Geen fallback en geen tweede tokenverversingsmechanisme.

## Risicogerichte acceptatie- en testmatrix

| Claim / foutscenario | Beslissende controle | Vereist resultaat | Nu uitgevoerd? |
| --- | --- | --- | --- |
| Te brede grant blijft onopgemerkt | Volledig schema, gewone runtime-rol, extra UPDATE op refusals; verifier en echte UPDATE | Nieuwe strict-controle weigert; minimumcontrole blijft compatibel | Huidig tekort gereproduceerd: minimum-PASS én UPDATE slaagt |
| Beperking breekt noodzakelijke rechten | Canonieke minimale grants; verboden UPDATE na gerichte REVOKE | Benodigde rechten blijven voldoende; UPDATE faalt; rij blijft gelijk | Lokaal bewezen voor minimumcontrole en verboden UPDATE |
| Directe REVOKE mist rolhiërarchie/PUBLIC | Grant via groepsrol respectievelijk PUBLIC | Strikte analyse ziet bron/recht; geen misleidende herstelclaim | Beide effectieve-rechtengevallen lokaal bewezen |
| Rolwisseling of ownerrechten omzeilen strikte beoordeling | NOINHERIT/SET ROLE-pad, eigenaarschap, superuser/BYPASSRLS, schema-CREATE | Detectie of expliciet onvolledige scope; nooit valse strict-PASS | Nog te schrijven tegen de voorgestelde verifier |
| Lock bezet tijdens migratie | Twee echte verbindingen; SELECT-transactie houdt lock, DDL wacht | Begrensde 55P03, geen gedeeltelijke wijziging, retry na vrijgave slaagt | Mechanisme lokaal bewezen; runnerintegratie nog te schrijven |
| Timeout lekt of bestanden rollen verkeerd terug | Controle na transactie; tweede migratie faalt na eerste commit | Timeout terug naar eerdere waarde; alleen falend bestand teruggerold | Local-setting-herstel bewezen; reeksproef nog te schrijven |
| Concurrente index gebruikt verkeerde wrapper | CREATE INDEX CONCURRENTLY in transactie en autocommit | Eerste faalt, tweede slaagt | Lokaal bewezen; nieuw pad niet in scope |
| TLS vertrouwt verkeerde servernaam | Echte lokale TLS-server met certificaat voor localhost | verify-full goed: succes; verkeerde naam: fout | Bewezen; require accepteerde dezelfde verkeerde naam |
| Onbetrouwbare CA/ontbrekend trustbestand | Echte TLS-server, andere CA en ontbrekend bestand | Verbinding geweigerd, geen fallback | Gepland; niet uitgevoerd |
| Eén connectiepad vergeet TLS-beleid | Adaptertests voor alle vijf ingangen, inclusief API-access en Azure-DSN | Zelfde beleid op Azure; lokale DSN blijft werken | Gepland; niet uitgevoerd |
| Authenticatiegedrag verandert | Bestaande tokencache; nieuwe authenticatie na refreshmoment | Tokenverversing blijft correct; geen token in uitvoer | Gepland; geen Entra-integratie uitgevoerd |
| Hardening raakt transacties/concurrency | Bestaande cross-store rollback-/commit- en raceproeven | Bestaande uitkomsten blijven behouden | Gerichte baseline geslaagd |
| Azure wijkt af van lokale proef | Entra-verbinding vanuit werkelijk image, effectieve rolrechten en instellingen | Correcte verbinding/rechten aantoonbaar; gevoelige waarden verborgen | Niet uitgevoerd; Azure-toegang ontbreekt |

De lokale probes bewijzen het PostgreSQL/libpq-mechanisme. Zij zijn geen
rood/groenbewijs voor nog niet geschreven productiecode. Bij implementatie komen
de betekenisvolle gevallen als regressietests in de bestaande testmodules;
de tests moeten dan eerst het huidige tekort ontmaskeren en na de wijziging slagen.
Mock catalogus-/TLS-gedrag niet voor een claim over hun werkelijke werking.

## Werkelijk uitgevoerde verificatie

Eigen tijdelijke server: PostgreSQL 17.11, Python 3.13.5, psycopg 3.3.5.
De server is uitsluitend voor deze opdracht aangemaakt en daarna gestopt en
verwijderd. Er is geen bestaande server gestopt of aangepast. Eerst is
`scripts/test_postgres.sh` tegen deze eigen server uitgevoerd.

```text
tests/test_workflow_postgres_migration_v1.py
tests/test_workflow_runtime_privileges_v1.py
tests/test_workflow_transaction_v1.py
tests/test_workflow_postgres_concurrency.py
tests/test_migration_018_postgres_v1.py
tests/test_azure_step9_cutover_v1.py
=> 54 passed, 0 failed, 0 errors, 0 skipped; 8.59 seconden.

scripts/check_architecture_boundaries.py
=> Architecture boundaries: PASS.
```

Er was één bestaande Starlette/AnyIO-deprecationwaarschuwing. De Azure-step9-tests
gebruiken testdoubles en bewijzen geen actuele Azure-inrichting. Migratierunnertests
combineren offline contracttests met native PostgreSQL-proeven; niet alle 54
cases zijn afzonderlijk native databasecases.

Negen aanvullende ontwerpcontroles zijn geslaagd. De lockproef brak met 55P03
af na circa 0,302 s bij een ingestelde 300 ms. Dit is mechanismebewijs op een
lokale fixture, geen productieprestatie of maximale gegarandeerde wandkloktijd.
De TLS-proef gebruikte een eigen tijdelijk certificaat, geen Azure-certificaat.

Bewijsmateriaal in deze workspace:

- `evidence/postgresql-preimplementation/run_baseline.py`: reproduceerbare runner.
- `evidence/postgresql-preimplementation/probes.py`: aanvullende scenario's.
- `evidence/postgresql-preimplementation/baseline.xml` en `baseline.log`: testuitkomsten.
- `evidence/postgresql-preimplementation/probes.json`: negen meet-/gedragsuitkomsten.
- `evidence/postgresql-preimplementation/summary.json`: versie, revisie en cleanup.

De lokale omgeving bevat PG17. Het project verlangt PG16-bewijs; deze uitvoering
vervangt dat niet. Herhaal de gerichte tests en nieuwe regressietests op PG16 vóór
merge; controleer daarnaast de werkelijke Azure-majorversie vóór uitrol.

## Implementatievolgorde en herstel

1. Beoordeel dit ontwerp. Geen ongefundeerde codeverwijdering of scaffolding nodig.
2. Maak de effectieve-rechtenanalyse expliciet begrensd. Voeg regressietests voor
   extra rechten, normale noodzakelijke writes, PUBLIC/inheritance, SET ROLE,
   eigenaarschap en onvolledige scope toe. Behoud minimumcontrolecompatibiliteit.
3. Voeg transaction-local lockbegrenzing toe aan de bestaande runner, met echte
   lockconflict-, rollback-, retry- en setting-hersteltests. Geen migratiehistorie.
4. Pas alle Azure-verbindingspaden aan voor serveridentiteitscontrole, met echte
   TLS-negatieve tests en behoud van lokale DSN's en bestaand tokengedrag.
5. Draai de gerichte suites op PG16, repository-/releasechecks die voor de concrete
   PR gelden en de dependencycheck. Daarna gecontroleerde Azure-read-only verificatie
   vanuit de bedoelde identiteit en het bedoelde image.
6. Een bevoegde beheerder beoordeelt daadwerkelijke grantwijzigingen per bron;
   die vormen een afzonderlijke productiehandeling. Controleer vervolgens de
   bestaande workflow met de echte runtime-identiteit en bevestig effectieve rechten.

Code-rollback vereist geen datamigratie. Een grantwijziging is niet hetzelfde als
code-rollback: leg de actuele ACL/rolrelaties vooraf veilig vast en herstel alleen
de aantoonbaar ontbrekende noodzakelijke rechten. Een TLS-verificatiefout los je
op met correcte hostname/trust/configuratie; geen automatische verslechtering
naar zwakkere verificatie. Reeds gecommitte migratiebestanden blijven behouden.

Uitgesteld: pooling zonder latencybewijs, volledig migratieregister, algemeen
concurrent-indexframework, wijziging van topologie, nieuw tenant/RLS-model,
gegevensbackfills en wijziging van herstel- of publicatiesemantiek.

Stop en herontwerp bij noodzaak tot nieuwe duurzame authority, herschrijven van
historische migraties, onduidelijke privilege-maxima, gewijzigde lifecycle-/recovery-
semantiek of structureel twee beleidsbronnen. Ontbrekend Azure-bewijs beperkt een
uitrolbesluit; het is geen reden om een bekende lokale ontwerpkeuze te verbergen.

## Oordeel vóór implementatie

De bestaande gerichte baseline is groen en de mechanismen voor de drie voorstellen
zijn lokaal onderbouwd. Kandidaat A is de voorgestelde implementatierichting.
De strengere verifier, runnerintegratie en volledige TLS-adapterdekking bestaan
nog niet; hun acceptatietests zijn expliciet gespecificeerd. PG16- en Azure-bewijs
blijven open. Er is geen productiecode gewijzigd en geen productiehandeling uitgevoerd.

Bronnen: `src/workflows/workflow_postgres_migration_v1.py`,
`src/workflows/workflow_transaction_v1.py`,
`src/publication/canonical_publication_postgres_v1.py`,
`src/workflows/workflow_identity_postgres_v1.py`,
`src/workflows/workflow_documents_postgres_v1.py`,
`src/settings/api_access_v1.py`, `src/azure_postgres_credential_v1.py`,
`src/console_asgi.py`, `src/console_performance_v1.py`,
`docs/AZURE_STEP9_CUTOVER_RUNBOOK.md`, `docs/AZURE_RELEASE_RUNBOOK.md`,
`docs/RUNTIME_DATA_RECOVERY.md` en de zes hierboven genoemde testmodules.
