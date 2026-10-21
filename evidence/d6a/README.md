# D6a — lokaal uitvoeringsbewijs

De lokale migratie naar de productiecompositie op PostgreSQL is voorbereid in
21 migratieporties plus één afzonderlijke Class A-bugreparatie. Iedere
voorgestelde PR raakt maximaal twintig testbestanden. Alle branches en
[PR-teksten](prs/) zijn voorbereid; alle 22 branches zijn gepusht.
Alle zes workflows van [draft-PR #791](https://github.com/WilliamGomes41/Metis-DS/pull/791)
zijn groen. [D6a/02, draft-PR #792](https://github.com/WilliamGomes41/Metis-DS/pull/792)
is nu ook geopend, tegen de branch van #791: 16 testbestanden, CI gestart.
Zie [publicatiebewijs van portie02](portion02-publication.json).
Ook porties03 tot en met10 zijn als draft geopend:
[#793](https://github.com/WilliamGomes41/Metis-DS/pull/793),
[#794](https://github.com/WilliamGomes41/Metis-DS/pull/794),
[#795](https://github.com/WilliamGomes41/Metis-DS/pull/795),
[#796](https://github.com/WilliamGomes41/Metis-DS/pull/796),
[#797](https://github.com/WilliamGomes41/Metis-DS/pull/797),
[#798](https://github.com/WilliamGomes41/Metis-DS/pull/798),
[#799](https://github.com/WilliamGomes41/Metis-DS/pull/799) en
[#800](https://github.com/WilliamGomes41/Metis-DS/pull/800).
Tien PRs zijn geopend; twaalf moeten nog worden geopend.
De workflows van06 tot en met10 zijn gestart of staan in de wachtrij.
Zie [publicatiebewijs van porties03–05](portions03-05-publication.json) en
[porties06–10](portions06-10-publication.json).

D6a is nog niet formeel afgerond en D6b is niet gestart. #695 houdt voorrang
bij capaciteitsgebrek; GNC is niet gestart.

PR09 is hersteld na een gemiste fixturedoorgifte bij de portiegrens.
De eerder mislukte source-processing-workflow is groen op de gecorrigeerde head;
de volledige CI-suite en timing lopen nog.
Alle directe afnemers zijn meegenomen; vier zelfstandige migraties schuiven naar10.
Zie [het herstelbewijs](portion09-fixture-boundary-repair.json).

## Actuele controle

De volledige ononderbroken lokale suite heeft **5.667 groene tests,
27 optionele skips en 6 bestaande xfails**, zonder fouten of PG-skips.
De nameting duurt **2313.951 seconden** tegenover **1043.807 seconden**
voor de schone baseline: **2.2168×**.
De lokale verhouding ligt boven twee: de prestatievoorwaarde is nog niet
gehaald. De meetopdracht faalt daarom op de tijdgrens, ondanks de groene tests.
De fixture moet verder worden verbeterd en in CI vergeleken voordat D6b kan starten.

[Volledige testuitslag en JUnit-hash](final-suite-verification.json),
[exacte meetgegevens](local-final-full.json) en
[alle verificatiegrenzen](verification.json).
De runtime-, fixture- en meetrunnerbroncode zijn identiek aan de gemeten commit.
Daarna zijn alleen CI, één rapportexportscript en vijf CI-contractcases
aangepast om de versnelling op main (#790) te behouden; deze 34 contracttests
en zeven echte rapportexports slagen. Zie [CI-integratie](main-ci-integration.json). De gegevens per portie bewaren hun oorspronkelijke uitgevoerde
revisies; de actuele branches staan daarnaast in de reviewvolgorde.

De volledige gemeten inventaris telt 5700 cases, waarvan 2034
PG-afhankelijk in 218 bestanden (inclusief adapterproeven).

- [Reviewvolgorde en branches](review-stack.json), met concrete testbestanden
  per PR. Portie 20 bewaart bewijs; de codecorrecties zijn teruggebracht naar
  hun introducerende porties en krijgen geen zelfstandige PR.
- [Bewijs per portie](batches.json): oorspronkelijke testaantallen en gerichte
  consumentenproeven, inclusief de exacte revisies en JUnit-hashes.
- [Volledige bestandsinventaris](file-topology-inventory.json): 130 expliciete
  `file_topology`-gevallen in 21 bestanden; deze blijven tot D6b.
- [Fixturevergelijking](fixture-portion-benchmark.json): dezelfde 37 tests,
  sjabloonkopieën 37 groen; rollback 31 groen en 6 fout door ontbrekende
  commit-/herstartzichtbaarheid.
- [Vooruitkopieproef](fixture-prefetch-benchmark.json): dezelfde 37 tests,
  17,036 → 15,096 seconden, beide groen zonder skips. Elke test houdt een
  nieuwe database met echte commits; gebruikte databases worden nooit hergebruikt.
- [D5 in de volledige suite](final-d5-mirror-proof.json): beide productieklassen,
  alle 15 fasen, geen spiegeltoegang en volledige PG-gelijkheid.
- [Database-start als root](root-start.json): echte PG16.15 onder `nobody`,
  statusbestand van de aanroeper met modus `0600`, opruimen geslaagd. Gewone
  gebruiker en de D4/D5-gifrun zijn daadwerkelijk uitgevoerd in Codex.
- [Herstel van configuratie-isolatie](fixture-environment-isolation.json):
  de gelijktijdige native hersteltest liet PG-instellingen achter; de 100
  gerichte gevallen zijn nu groen zonder nieuw instellingenlek. Alle 130
  bestandsgevallen zijn ook met vooraf ingestelde PG-variabelen groen.
- [Afsluitende repositorychecks](final-checks.json) en
  [22 gevalideerde PR-contracten en portiegrenzen](review-stack-validation.json).
- [Gemeten broncode en begrensde CI-wijzigingen](measured-source-equivalence.json) en
  [statische workflowcontrole](workflow-validation.json).
- [Collection zonder database](missing-postgres-collection-audit.json),
  [meetisolatie](measurement-isolation.json) en
  [beoordeling van karakteriseringsgoldens](characterization-golden-review.json).

Het [bewijs van de eerste portie](first-portion-history.md) en de
[volledige tussenrun met vijf fouten](local-unprefetched-full.json) blijven
bewaard als historie. De schone baseline staat in
[local-baseline-clean.json](local-baseline-clean.json); lokale cijfers zijn
geen CI-resultaten.

## Open voorwaarden

Voor D6a zijn CI-baseline en nametingen per portie en bewijs uit de gebruikte
Cursor-omgeving(en) nog nodig. De blijvende Codex-setupinstellingen zijn vanuit
deze sessie niet schrijfbaar; de repo bevat het gemeenschappelijke setup- en
startscript. Zie [omgevingsinstructies](../../docs/agents/postgres-tests.md).

D6b wacht daarnaast op de afgesproken review van Lex, Sherlock en Argos en de
beslissing over bestaande lokale JSON-toestand. De bestandsruntime, vijf
storevariabelen en lokale CLI-start zijn daarom nog aanwezig.

PR10: een gedeelde lockteller veroorzaakte een wisselende testuitkomst. De voorbereidingsproeven meten nu lockeigenaarschap per thread; bestaande rode/groene proef en alle 206 native acceptatiegevallen zijn vastgelegd in [het herstelbewijs](portion10-lock-observation-repair.json). Nieuwe volledige CI en tijdmeting zijn nog open.

PR09/10: de volledige CI toonde één gemiste aanbevelingshelper-afnemer. De fixture- en consolefabriek zijn naar de introducerende portie verplaatst, met behoud van alle bestaande verwachtingen. Zie [het herstelbewijs](portion09-10-recommendation-boundary-repair.json); de nieuwe volledige CI-uitkomsten zijn nog open.

PR09/10: de volledige suites waren op Python3.12 groen; een volgende bewijscheck herkende de hernoemde diagnosegevallen niet als PG. De bestaande gate blijft intact, met expliciete PG-test-IDs en 23/23 lokaal uitgevoerde diagnosegevallen op beide porties. Zie [het labelherstelbewijs](portion09-10-native-label-repair.json). Nieuwe exacte-head CI loopt nog.
