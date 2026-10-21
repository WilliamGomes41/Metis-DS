# D6a — uitvoeringsbewijs

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
Dertien draft-PRs zijn geopend; negen moeten nog worden geopend.
De publicatiebewijzen bewaren hun oorspronkelijke momentopname. Porties09 en10 zijn inmiddels volledig groen in CI.
Zie [publicatiebewijs van porties03–05](portions03-05-publication.json) en
[porties06–10](portions06-10-publication.json).

De volgende drie zijn nu geopend: de afzonderlijke PG-reviewreparatie
[#801](https://github.com/WilliamGomes41/Metis-DS/pull/801),
D6a/11 [#802](https://github.com/WilliamGomes41/Metis-DS/pull/802) en
D6a/12 [#803](https://github.com/WilliamGomes41/Metis-DS/pull/803).
Lokaal opnieuw uitgevoerd:9/9,110/110 en193 geslaagd plus12 optionele
PDF-skips; nul PG-skips. De volledige CI loopt nog.
Zie [het publicatiebewijs](prerequisite-portions11-12-publication.json).

D6a is nog niet formeel afgerond en D6b is niet gestart. #695 houdt voorrang
bij capaciteitsgebrek; GNC is niet gestart.

PR09 en10 zijn volledig groen op Python3.12 en3.13, inclusief alle vervolgchecks.
Per job:5658 passed,27 optionele skips,6 bestaande xfails en nul PG-skips.
De CI-verhoudingen tegenover de ongewijzigde basis zijn **1.3969×** voor09
en **1.6064×** voor10. Zie [de exacte heads, jobs en metingen](portions09-10-ci-success.json).
Dit rondt de overige D6a-porties en de afsluitende gates niet af.

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
Na die meting zijn CI, één rapportexportscript, vijf CI-contractcases en
gerichte test-helper-/bewijsherstellen aangepast. De 34 CI-contracttests en
zeven echte rapportexports slagen; exacte bronverschillen staan in
[de bronvergelijking](measured-source-equivalence.json). Zie [CI-integratie](main-ci-integration.json). De gegevens per portie bewaren hun oorspronkelijke uitgevoerde
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

De oorspronkelijke helper-, thread-lock- en diagnose-ID-herstelbewijzen blijven
bewaard als geschiedenis. Hun actuele CI-uitkomst staat in
[portions09-10-ci-success.json](portions09-10-ci-success.json).
