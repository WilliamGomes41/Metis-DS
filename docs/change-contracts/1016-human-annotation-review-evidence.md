# HA-3 — uitvoeringsbewijs en overdracht

Change class: A. Rewrite risk: high. Contract:
[1016-human-annotation-review.md](1016-human-annotation-review.md).
Basis main `dfc077af362e0d8156aa5ea96e05b9d83c45127a` (#1031).
Branch `feat/human-annotation-review-1016`.
Product- en testcode voor de finale run: `00733c0284c60a86408901ed3add2a2f2a1bac7f`.
Geen merge, deployment of productiemigratie uitgevoerd.

## Werkelijke verticale uitkomsten

Native PostgreSQL 16.4 via de repository-fixture en scripts/test_postgres.sh;
geen PostgreSQL-test als skip geaccepteerd. Beide operationele documentlayouts
legacy/v1 zijn geraakt en getest. De publicatieketen gebruikt de bestaande
MemorySourceStore uitsluitend voor immutable-blobtransport; workflow, versies,
reviewbindings, producerbewijs en publicatieregistratie zijn echte PostgreSQL.

```sh
env -u METIS_TEST_POSTGRES_DSN PGBIN=/tmp/metis-pg16/bin \
  PATH=/tmp/metis-pg-client/usr/lib/postgresql/17/bin:$PATH \
  /workspace/Metis-DS/.venv/bin/python -m pytest -xq \
  tests/test_human_annotation_review_postgres.py --tb=short
```

**27 passed**, 51.76s, geen skips. Log lokaal:
`/tmp/metis-ha3-final-native.log`. Omvat oorspronkelijke annotatiecorrectie,
nieuwe exacte objectversie met behoud van bevestigd type/relaties, gewijzigde
kernankers met behoud van canonieke identiteit, twee bewijsfuncties, gerichte
invalidatie, ongewijzigde save/duplicate receipt, stale frontier, echte rollback,
concurrente commands, publicatie/correctie met beide mogelijke winnaars,
herstart, exact archiefherstel na drie builds in beide layouts, vervalste
approval tijdens restore, onafhankelijke reviewers volgens ingestkeuze,
ontbrekende native guard, oude correctiewriter, onafhankelijk herberekend
vervalst bewijs, voorbereidingswerk buiten writerlock en structurele relaties
die geen inhoudelijk oordeel ongeldig mogen maken. Nieuwe seals pinnen het
bestaande T10-bronbeleid; seals zonder die pin behouden exact hun legacyuitvoer.

De doorlopende HTTP-proef start bij echte multipart `/ingest` met ingestkeuze
uploader_sole. Bron openen → exacte core/condition/evidence/context aanwijzen
via de productie-API → save → app sluiten/herstarten met dezelfde database →
overzicht → finalize → bestaande dispatcher/jobs → oorspronkelijke annotatie
corrigeren → tweede overzicht/finalize/bouw → definitieve reviewkaart met
bewijsfunctie → drie expliciete antwoorden → receipt → opnieuw openen zonder
herhaald formulier → publicatie → ProductAPI 200 met dezelfde release en
context → bestaande MCP-queryowner leest registry en exacte versie na herstart.
Deze ene proef selecteert via HTTP; de afzonderlijke Chromium-proeven oefenen
werkelijke muisselectie en mobile/desktopgedrag uit.

De native publicatieproeven controleren vóór review BLOCKED, lege registry en
API404; na het toepasselijke oordeel de exacte gepubliceerde tuple. Correctie
van gepubliceerd werk wordt geweigerd en verandert historische release niet.
MCP-bewijs betreft de bestaande geautoriseerde interne queryowner, geen nieuw
publiek MCP-transport of externe Entra-authenticatieproef.

Eerdere gerichte combinaties: **60 passed** (HA-3, D5-code-rollback durable/Azure,
T11; `/tmp/metis-ha3-preflight-native.log`) en **48 passed** (revision frontiers,
herstel en HA-3; `/tmp/metis-ha3-frontiers.log`). Deze werden vóór de laatste
bronbeleidpin uitgevoerd; de finale volledige suite controleert de gezamenlijke
regressies op de vastgelegde code.

## Browser en frontend

```sh
env -u METIS_TEST_POSTGRES_DSN PGBIN=/tmp/metis-pg16/bin \
  PATH=/tmp/metis-pg-client/usr/lib/postgresql/17/bin:$PATH \
  METIS_BROWSER_EXECUTABLE=/usr/bin/chromium \
  METIS_PLAYWRIGHT_MODULE=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright \
  /workspace/Metis-DS/.venv/bin/python -m pytest -q \
  tests/test_browser_knowledge_context.py
```

**15 passed**, 140.27s, geen skips (`/tmp/metis-ha3-browser-matrix.log`).
Afzonderlijke finale HA-3-browserproef: **1 passed**, 14 deselected, 9.23s
(`/tmp/metis-ha3-browser-complete.log`). Werkelijke selectie/correctie,
pauze/hervatten, overzicht, dispatcherbouw, exacte versie/bewijsfunctie,
oordeel en heropenen zonder dubbele vragen. Zes gecontroleerde captures op
1440/390px staan lokaal onder
`/tmp/metis-ha3-browser-complete/test_desktop_mobile_review_con0`.
Finale controle op productcode `00733c0284c60a86408901ed3add2a2f2a1bac7f`:
**3 passed**, 12 deselected, 31.91s, geen skips. Zelfde opdracht met
`-k 'human_annotation or human_build or human_review'` en
`--basetemp=/tmp/metis-ha3-browser-final`; log
`/tmp/metis-ha3-browser-final.log`. De drie human-ketens zijn dus ook na de
bronbeleidpin echt opnieuw uitgevoerd.
De browsermatrix in CI neemt de nieuwe proef en captures mee.

Impeccable-context/detector eenmaal gebruikt; detector `[]`. Afzonderlijke
finishreviewer inspecteerde de zes screenshots en betrokken code/tokens en gaf
`ship` voor deze bestaande-console-uitbreiding. Documenter bevestigde behoud
van incumbent tokens/shell/native controls; geen nieuw PRODUCT/DESIGN-document
of nieuwe assets nodig. Pre-existente fallbacktokens/statusaccenten/kleine
hulptekst bleven buiten deze begrensde wijziging. Deze visuele controle bewijst
geen researcherpraktijkacceptatie of backendreleasegereedheid.

## Afzonderlijke adversarial pass

De primaire agent heeft naast implementatie een afzonderlijke pass op de
concrete diff/aanroepers uitgevoerd. Dit is geen onafhankelijke codeaudit.
Getoetst: beide console-MRO's, native bundlewriter en directe SQL, oude
correctie-/broncontextingangen, ontbrekende guard, proofvervalsing met nieuwe
hashes, huidige versus historische producerbinding, cachecompatibiliteit,
reviewafhankelijkheden, duplicate/stale calls, lockvolgorde, lopende voorbereiding,
publicatie/correctieraces en lege-doelrestore/rollback.

Gevonden en gesloten:

- Save hield documentlock vóór de bestaande filelock terwijl publicatie de
  omgekeerde volgorde nam. Save en finalize volgen nu dezelfde globale volgorde;
  echte concurrentieproeven en rollback controleren dit.
- Bronbewijs binnen hetzelfde human-object was niet bekend bij de bestaande
  KO-evidencegate. Exact gevalideerd literal support gaat nu via dezelfde
  reviewowner; geen extra KO of NVT-omweg.
- De oude archive-export verloor authorization_payload. v12/formation5 bewaart
  de volledige exacte binding; oude ontbrekende payload blijft expliciet null.
- Oude revision-frontier/readfactcontracts dekten human oorsprong niet. Hun
  bestaande compatibilityowners vallen gecontroleerd terug op volledige input.
- Een structurele parentrelatie trok ongeraakte inhoudelijke review in. De
  native rode tegenproef is groen na filtering op echte betekenisafhankelijkheid;
  semantic supported_by blijft juist wel gericht ongeldig worden.
- Nieuwe human-bronresten droegen onbedoeld legacybeleid. De volledige HTTP-proef
  reproduceerde onnodige herbeoordeling; expliciet gepind T10-beleid sluit alleen
  bewezen brongebruik. Een native compatibiliteitsproef houdt oude output gelijk.

Geen tweede candidatecreator, queue, reviewengine of servingauthority toegevoegd.
De bestaande enige materialiser maakt de ruwe kandidaat; de bestaande
revision_workflow-owner past uitsluitend bewezen output op de expliciete
voorganger toe. Historische human-KO-versies en proofs blijven bewaard.

## Finale repositoryverificatie

Repositorypreflight: PASS, 2309 bestanden. Compileall: PASS.
Architecture boundaries: PASS. Architectuurinvarianten: **6 passed**.
Release-controlpreflight op gecommitteerde diff: PASS
(`/tmp/metis-ha3-final-release-preflight.json`). Diffcheck: PASS.

Volledige suite gestart op product-/testcode `00733c0284c60a86408901ed3add2a2f2a1bac7f`:

```sh
env -u METIS_TEST_POSTGRES_DSN PGBIN=/tmp/metis-pg16/bin \
  PATH=/tmp/metis-pg-client/usr/lib/postgresql/17/bin:$PATH \
  /workspace/Metis-DS/.venv/bin/python -m pytest -q -n4 \
  --basetemp=/tmp/metis-ha3-full-suite
```

**8460 passed, 48 skipped, 3 xfailed, 32 subtests passed**, 1485.94s,
exit 0. Log `/tmp/metis-ha3-full-suite.log`. Geen native PostgreSQL-skip.
De 48 optionele skips zijn 25 browsergevallen, 12 echte Docling/PDF-
acceptatiegevallen en 11 optionele Bend-proeven. De volledige bestaande
Chromium-matrix is afzonderlijk uitgevoerd; de drie human-ketens zijn ook
na de bronbeleidpin nogmaals uitgevoerd. Optionele skips zijn geen geslaagd
acceptatiebewijs. Latere commits wijzigen alleen bewijs/praktijkdocumentatie;
product- en testcode blijven exact deze geteste versie.

## Migratie, rollback en resterende grenzen

Additieve migratie 037, uitsluitend op tijdelijke testdatabases uitgevoerd.
Geen productiebackfill/downmigratie. Nieuwe correcties vereisen aanwezige,
ingeschakelde native guards. Na adoptie van nieuwe revisions/proofs mag een
onbegrijpende oude binary niet schrijven: writes blokkeren, registry-serving
behouden, forward fix of bewezen nieuwe-reader-restore. Geen AI-fallback.

Niet geleverd door deze correctieslice: nieuwe claims toevoegen na activatie,
split/merge/terugnemen van geactiveerde claims, overname historische AI-objecten,
een nieuwe reviewerpolicy, automatische goedkeuring, Azure-deployment of externe
transportauthenticatie. Het huidige claimlidmaatschap blijft expliciet gefixeerd;
de oorspronkelijke claim kan wel bronbereiken, context en bewijs corrigeren.
Leeskosten bij grote documenthistorie zijn niet gemeten; geen latencybelofte.

HA-4 (#1017/MET-61) blijft eigenaar van de volledige oude AI-prozaroute- en
configverwijdering en de praktijktoets met onafhankelijk referentiedocument.
Het [bestaande praktijkplan](../plans/human-annotation-practice-acceptance.md)
neemt nu ook de correctielus na activatie met oude/nieuwe versie op.
Researcheronderzoek is niet uitgevoerd. De technische keten en screenshots
zijn daarvan geen vervanging. Review, CI, merge en toepasselijke release/live
verificatie blijven afzonderlijk nodig; MET-60 en het parent blijven open.
