# WP5 / MET-23 — afsluitcontract en herhaalbaar bewijs

Change class: C. Rewrite risk: none. Touches lifecycle invariants: no.
Geen productiecode, domeinregel, schema, deployment of live productiemeting.
De uitgevoerde revisie, artifact-ID en resultaten worden vastgelegd in
[PR #914](https://github.com/WilliamGomes41/Metis-DS/pull/914) en
[#902](https://github.com/WilliamGomes41/Metis-DS/issues/902). Dit document en een
aanwezige test zijn op zichzelf geen geslaagde uitvoering.

## Scope en voltooiing

WP5 levert een reproduceerbare huidige baseline, geïsoleerde native databasegrens,
variantgebonden compatibiliteitsoracles en meet-/invoercontract voor WP6–WP8.
De huidige trage writer wordt hier niet versneld. Een aangetoonde baselinefout
wordt dus niet verborgen om een prestatie- of productieoplossing te claimen.
Een onbekende liveoorzaak blijft expliciet onbekend, conform #902; nieuwe livechecks
horen bij #699/#680. Dat is geen impliciete toestemming om productie te benaderen.

| Criterium #902 | Behouden uitvoerbaar bewijs / controle |
| --- | --- |
| Exacte code/runtime/input | JSON: geteste merge-ref, harnesshash, Python/PG, storageversie, generatie, source-/extractiecontract en werkelijke object-/historie-/bindingtellingen. Artifact koppelt de merge-ref aan de PR-head. |
| GET / normale POST / 400 / 409 / retry | Legacyprofielen plus echte complete/incomplete task-v1; full ASGI response, redirects niet gevolgd, draft-/durable-statecontrole. |
| Afwijzing vóór versus in transactie | Ontbrekende rejectcomment:400 zonder store_transaction; source-discrepancy:400 met echte store_transaction en behouden concept. |
| SQL execute/fetch/JSON en bronwerk | Bestaande diagnostiek plus transparante native cursorobserver met vaste categorieën, execute-/fetchtijden, opgehaalde rijen en geraakte writerijen; geen SQL/parameters exporteren. |
| Lock versus uitvoering isoleren | Onafhankelijke documentrijblocker met observer en vrijgave; context/single-review over onafhankelijke runtimepaden met native wait-for-grafiek en SQLSTATE. |
| Zware historie/bindings en schalen | Legacy 20 met vier historiecycli; task-v1 32/128 met twee cycli, geldige/stale bindings en identieke focale passage. Werkelijke tellerwaarden zijn leidend; geen exportreplay claimen. |
| Relationele/contextafhankelijkheden | Context na approval; oude→nieuwe doelpassage; volledige context-/publicatierace-referentietest. Writer-/invalidatiesets in WRITERS-902.md. |
| Fout / rollback / herstel | Echte binding-INSERT-fout P9021 en deferred COMMIT-fout P9022; opgeslagen toestand/generatie gelijk; verse productiecompositie en originele retry. |
| Geen verstopte missers | JUnit failures/errors/skips en request-/testinventaris behouden; een gestart maar onafgerond geval heeft geen succesvolle latency. Ontbrekende JUnit betekent geen afgeronde run. |
| Compatibiliteit / eigenaren | Onderstaande retrymatrix plus strict passage-token, command-equality en disjuncte storage-merge; geen universele CAS of deduplicatie. |

## Reproduceren

Gebruik de gepinde dependencies en native PostgreSQL16 met CREATEDB. Eerst:

```sh
export METIS_TEST_POSTGRES_DSN="$(bash scripts/test_postgres.sh)"
REVIEW_PROOF_OUTPUT=/tmp/wp5.json python -m pytest -x -q \
  tests/test_review_post_baseline_postgres.py --junitxml=/tmp/wp5.xml
```

Gebruik een nieuw uitvoerpad. Voor de aanvullende bestaande referentietests:
voer de volledige pytest-invocatie uit de stap `MET-23 native Review POST baseline`
in `.github/workflows/ci.yml` uit. De bestaande CI-job bewaart alles als
`review-post-902`; er is geen aparte infrastructuur nodig.

`wp5.progress.json` bevat begonnen en afgeronde HTTP-verzoeken.
`wp5.tests.json` bevat begonnen/afgeronde gevallen; JUnit bepaalt pass/fail/skip.
Een afgebroken geval wordt niet uit de inventaris verwijderd en telt niet als
succesvolle sample. Native kernelproeven hebben eigen resultaatregels; bij een
timeout blijft het begonnen testgeval zichtbaar.

## Variantgebonden retry-oracles

| Variant / ingang | Te behouden uitkomst; geen algemene idempotentieclaim |
| --- | --- |
| Approval / compact HTTP-formulier |303; hetzelfde oude formulier409, winnaar ongewijzigd. |
| Exacte semantische approval / directe kernel | Bestaande duplicatefastpath: ongewijzigde historie/revisie; afzonderlijke referentietest. |
| Reject / HTTP |303 en definitief rejected/geen geldige approval; oude precondition409 zonder tweede mutatie. |
| Revise-specificatie / HTTP |200 met correctiespecificatie, geen domeinwrite; identieke herhaling200. |
| Ingevulde source-unit-repair / kernel | Opvolger en needs_review; herhaling van oorspronkelijke precondition conflicteert zonder tweede herstelwrite/audit. |
| Later / deze HTTP-payload |303 met gelijke semantische domeintoestand; bestaande bundelwrite kan generatie wijzigen, zodat oud compact formulier409 geeft. Geen universele no-write-belofte. |
| Tweede review / kernel | Exacte kennisversie/hash blijft gelijk; verse retry schrijft geen extra historie/binding/event. |
| Headingbatch / HTTP | Ontdubbelde batch atomair303; oude revision409; verse reeds bevestigde batch303 zonder nieuwe domeinwrite. |
| Binding-only intrekking / legacy en task-v1 | Bestaande documentcounters blijven gelijk; oude generatie is geen approvalbewijs. Expliciete nieuwe approval mag de ingetrokken binding vernieuwen (303). |

## Werkbelasting, tijden en technische budgetten

De grotere gevallen starten de eerste HTTP-meting met een verse productiecompositie
over dezelfde gecommitte database en bron. Daarna twee GET/400-herhalingen; OS- en
PostgreSQL-caches worden niet geflusht. Rapporteer dus eerste compositielezing en
herhalingen afzonderlijk, niet als gegarandeerd koude schijf/netwerk. Eén approval
en de conflict-/retrygevallen blijven losse waarnemingen. Geen p95 uit deze aantallen.
De transparante observatie heeft eigen meetoverhead; trek die niet denkbeeldig af
en gebruik dezelfde observer bij de latere vergelijking.

Vóór productie-optimalisatie vastgelegde engineeringdoelen voor WP6: totale
303/400/409-POST elk ≤3000ms; hold van exclusieve storelock ≤250ms; storetransaction
≤500ms. Het betreft inclusive duur per span (lockhold omvat ander werk), geen som
van overlappende fasen. Geïnjecteerde blocker-/deadlocktijd apart houden. Dit zijn
technische synthetische vergelijkingsdoelen, geen met William overeengekomen
productie-SLO en geen claim dat de baseline eraan voldoet. Overzicht3s/detail5s
blijven de afzonderlijke projectdoelen.

Schaalinput en gemeten bytes/rijen worden gepind per grootte. WP6 vergelijkt dezelfde
sourcehash, contracten, historie, bindings en beslisvariant vóór/na. De synthetische
grootheden vervangen geen originele bron-/databaseback-up. Een onveranderd
referentiepad en de bestaande bron-/closure-/publicatieproeven blijven behouden.

## Rode baseline en vervolggrens

De documentrijprobe onderscheidt een echt `Lock/transactionid`-wait van CPU/trigger-
of netwerkwerk en toont vrijgave gevolgd door303. De context/single-probe observeert
de twee echte PostgreSQL-blocking edges; bij een te invalideren bestaande binding en de omgekeerde lockvolgorde
wordt SQLSTATE40P01 plus één duurzame winnaar vereist. Een geslaagde diagnostische
test betekent hier dat de fout aangetoond is, niet dat de writer deadlockvrij is.
De veiligheidsassertie `assert not result['observed_cycle']` op deze native
resultaatregel met `has_prior_binding=True` is de rode no-deadlock-baseline voor WP6.
De negatieve controle zonder bindings heeft geen bindingdelta/authorizationlock:
context commit, de gelijktijdige approval conflicteert op revisie. Dat is geen
deadlock en moet als bestaand correct conflictgedrag behouden blijven.
De bestaande writer blijft
ongewijzigd; een latere fix moet het echte concurrerende pad opnieuw uitvoeren.

`baseline_budget_violations` registreert de overschrijdingen van de vooraf genoemde
doelen. Bewaar uitzonderingen, SQLSTATEs en onafgeronde gevallen naast de latenties.
De live incidentoorzaak kan hiermee niet worden vastgesteld. Een gecontroleerde
cyclus/wachttijd is bewijs voor deze fixture en databasegrens; productieattributie
blijft buiten deze afronding.

WP6 mag geen binding-/rolwijziging uitsluitend met object_generation controleren.
Het moet oude én nieuwe contextgebruikers, peers en aanvullende mixin-/beleidswrites
behouden, en de database-lockorde voor alle betrokken writers onderbouwen. Zie
[WRITERS-902.md](WRITERS-902.md). WP5 sluit pas met geinspecteerde native artifact,
groene verplichte checks en expliciet afrondingsoordeel in de trackers.
