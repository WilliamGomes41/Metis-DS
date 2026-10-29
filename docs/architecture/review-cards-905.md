# WP8 — actuele compacte Review-invoer

Change class: B
Promise: actuele persoonlijke kaarttellingen zonder volledige objecthistorie of broninhoud op de overzichtsroute.
Proof: native HTTP-oraclepariteit, begrensde rijen/bytes, actuele bindings/policy/actor en stale/concurrency/recoverytegenvoorbeelden.
Touches lifecycle invariants: no
Rewrite risk: high

Issue #905 / MET-26. Basis main `4844fbe`; WP7 en de metadata/auditvoorstap
uit PR #923 zijn gemergd. Deze wijziging implementeert de resterende compacte
kaartinvoer. De productiereader blijft standaard `legacy` tot expliciete cutover.

## Bronbesluit

William koos op 29 oktober 2026 expliciet voor tellingen uit de geverifieerde
retained extractie plus actuele reviews. De oorspronkelijke bron wordt volledig
gecontroleerd bij openen/beoordelen en publicatie. De kaart vermeldt dat controle
bij openen/beoordelen plaatsvindt. Daardoor blijven taken op de kaart bestaan als
de oorspronkelijke bron ontbreekt of corrupt is; dat geeft geen reviewbevoegdheid.
Ontbrekende/verouderde afgeleide kaartinvoer betekent onbekend/onbeschikbaar,
nooit impliciet nul taken. Een existence-/sizecontrole bewijst geen checksum en
vervangt de bestaande broncontrole niet.

## Ground → Sketch → Agree → Implement → Scrap

Ground: de bestaande overzichtsreader laadt huidige objecten via volledige
histories, bindings en bronviews. `current_revisions` beslist over afstamming;
ReviewDuty, bronaccountability, reviewpolicy en graphowners beslissen over taken.
Een verkort object opnieuw hashen zou exacte reviews ongeldig maken.

Sketch: twee afzonderlijke read-only runners hebben alternatieven getoetst.
Uitsluitend dynamische SQL kan letterlijke mapping en exacte canonieke hashes
niet controleren zonder de weggelaten inhoud. Een aparte persoonlijke
kaart-/closurestatus zou een tweede autoriteit worden. Gekozen: kleine
intrinsieke feiten bij dezelfde documentstore; de bestaande Python-owners
projecteren met actuele governance, policy, bindings en actor.

Agree: de gebruiker heeft de vervolgstap en het bovenstaande bronbesluit expliciet
opgedragen. Implement: eerst primitive-oraclepariteit, dan writer/freshnessbewijs,
dan native HTTP en bounded-I/O. Scrap bij een tweede statusautoriteit, verborgen
GET-herbouw of volledige closureberekening onder iedere savelock.

## Gebruik en eigenaarschap

```python
# In workflow_read_transaction: alleen coherente databasecapture.
captured = capture_review_cards(store, con, visible_snapshot_ids)
bindings = review_store.read_bindings(visible_snapshot_ids)
# Buiten de transactie: bestaande owners beslissen over persoonlijke taken.
item = review_work_item(console, account=current_account, envelope=envelope,
                       inputs=ReviewWorkInputs(objects, bindings, lifecycle,
                                               published, sources, graph_inventory))
# Expliciete beheervoorbereiding van bestaande authority, nooit GET/startup.
prepare_review_cards(store, snapshot_id)
```

`ReviewObjectFacts` is immutable en niet JSON-serialiseerbaar als KnowledgeObject.
`ReviewFactSources` bindt primitive bronproofs aan exact de objectinstanties uit
dezelfde capture. De carrier is geen volledige bron en geen commandinput.
Exacte reviewhashes worden door de bestaande kernel bij schrijven berekend;
op GET wordt de geverifieerde hash hergebruikt. Policy-, vierogen-, context-,
repair- en graphregels blijven bij hun bestaande owners. Geen opgeslagen
approved/complete/remaining/actorstatus. Commands en publicatie houden hun
volledige objecten en bronvalidatie.

| Gegeven | Eigenaar en actualiteit | Ontbrekend/verouderd |
| --- | --- | --- |
| Huidige objectselectie en exacte hash | current_revisions/kernel, gevalideerd bij writer; fysieke dirty/coveragebewaking | Kaart onbekend |
| Bron-/mappingprimitives | bestaande validators; exacte inputhash, extractie/source/view/producercontract | Kaart onbekend; geen GET-herstel |
| Governance en objectpolicy | bestaande documentstore, live copied fields bij veilige SQL-update | Onveilige mutatie invalideert |
| Bindings | bestaande reviewstore, dezelfde repeatable-readcapture | Geen gecachte approval |
| Documentmetadata/policy/deelname | bestaande fysieke kolommen en envelope; trigger onderhoudt compact header | Geen oude envelope over fysieke autoriteit |
| Actor/rol | actuele identityowner vóór capture | Toegang geweigerd na intrekking |
| Lifecycle/publicatiestatus | bestaande canonical lifecycleowner | Geen nieuwe servingautoriteit |
| Beginnen/Verder | bestaande compacte auditheuristiek uit PR923 | Geen auditdetails laden |

## Opslag, writers en herstel

Additieve migratie 027 maakt `review_fact_state`, `review_object_facts` en
`documents.review_card_envelope`. Geen historische backfill in de migratie.
State bevat input/prepared-epoch, source identity en verwacht aantal actuele
objecten. Objectfacts bevatten historycount, dirty, geselecteerde versie/volgorde,
compacte velden, intrinsieke proof en technische CRC. De CRC over JSONB-text is
geen vervanging van de canonieke reviewhash.

Alle fysieke SQL-objectwrites onderhouden invalidatie in dezelfde transactie,
ook position, identity move, delete/reinsert en TRUNCATE. Tombstones voorkomen
ABA. Exacte vergelijking onderscheidt `1` van `1.0`. Alleen canoniek/intrinsiek
ongewijzigde governance/admission/passageregisterupdates mogen live velden
kopiëren. Historische governance overschrijft het huidige object niet.

Runtime/concurrent `write_bundle` en scoped `apply_review_changes` sealen de
gevalideerde geraakte histories atomair met hun authoritywrite. Proofs met exact
dezelfde intrinsieke input worden hergebruikt. Initiële verwerking en reprocess
bereiden bronviews/proofs vóór de beschermde activatietransactie voor. Dezelfde
transactie publiceert de immutable views en facts. Geen volledige
source_accountability bij iedere save. Binding-only replacement/backfill blijft
live readinput en behoeft geen objectcounterbump.

Legacy-import zonder complete posities/retained extractie wordt niet stil
hersteld: eerst de bestaande cutover/preparation uitvoeren. Expliciete
kaartvoorbereiding mag ontbrekende geïndexeerde views uit de geverifieerde
retained extractie maken, zonder oorspronkelijke bronbytes. Corrupte pinned
views worden niet stil vervangen. Voorbereiding berekent buiten de beschermde
write en installeert onder epoch/source-CAS; een nieuwere writer wint.
Rollback draait authoritydelta en facts samen terug. Contract, CRC, source
identity, objecttuple, coverage en dirty-markers worden op iedere capture getoetst.

## Mitigatie en rollout

Rewrite target: de gedeelde workboard/navigation readgrens en afgeleid writeronderhoud.
Why local patching is insufficient: minder HTML of kleinere interfaces verwijderen de diepe bron-/historieafhankelijkheid niet.
Current authority/writer/reader map: workflowdocumenten/objecten/reviewbindings blijven authority; runtime/concurrent bundle en scoped commandwriters onderhouden afleiding; legacy/import/SQL invalidatie; workboard en navigatie consumeren; command/detail/publicatie behouden volledige owners.
Supported runtime topologies: CompleteWorkflow PostgreSQL lokaal en Azure-broncompositie; herstart/nieuw proces. Geen nieuwe multi-instancegarantie.
Persisted-state impact: uitsluitend additieve reproduceerbare facts/compacte envelope; geen review-, object-, bron- of lifecycle-identiteit vervangen.
Compatibility/migration plan: expand via 027, writers onderhouden ook in legacy mode, expliciete voorbereiding/check, daarna opt-in compact reader.
Rollback/recovery plan: zet reader terug op legacy en herstart; authority is ongewijzigd. Herstel afleiding via expliciete voorbereiding; geen destructieve reset.
Cutover trigger: alle toegewezen actieve documenten hebben actuele facts, oracle-/writer-/recoverybewijs en CI groen; beheerder zet expliciet CONSOLE_REVIEW_CARD_READS=compact.
Cleanup/decommission criteria: oude reader pas verwijderen na afzonderlijk geaccepteerde rollout; zolang rollback nodig is geen contract/remove-migratie. Geen automatische expiry.
Failure blast radius: overzichtstelling kan onbekend zijn; geen extra review/publicatiebevoegdheid of wijziging van serving.
Adversarial proof matrix: alternate writers/overrides, binding-only, policy/actor, SQL identity/numeric/history, corrupte/missende facts, concurrent prep/writer, rollback, nieuw proces, beide HTTP-topologieën en pagina-/historiegroei.

Gebruik de bestaande databaseconfiguratie/credentialowner. Na toepassing van de
additieve migratie, in de beoogde omgeving:

```sh
python scripts/prepare_review_cards.py --snapshot SNAPSHOT_ID
python scripts/prepare_review_cards.py --snapshot SNAPSHOT_ID --check
# Alleen als expliciet volledige scope bedoeld is:
python scripts/prepare_review_cards.py --all
python scripts/prepare_review_cards.py --all --check
```

Een niet-actueel document geeft exit 1 en een veilige foutcode. `--check` gebruikt
een read-only repeatable-readtransactie. Scope is verplicht. GET/startup doen
geen voorbereiding en de compacte reader heeft geen verborgen deep fallback.
Default/rollback: `CONSOLE_REVIEW_CARD_READS=legacy`. Voor readercutover:
`CONSOLE_REVIEW_CARD_READS=compact` en runtime herstarten. Productiemigratie,
configuratiewijziging en deployment zijn in dit werk niet uitgevoerd.

## Uitgevoerd bewijs en grenzen

Native oracle-, HTTP-, storage- en I/O-tests staan in
`tests/test_review_card_{facts,storage,io}_v1.py`. Zij toetsen bestaande
reviewbeslissingen, graph/context, sourcecorruptie met geblokkeerde echte command,
missing/CRC/contract/foreign tuple, rollback, stale voorbereiding en nieuw proces.
SQL-archive- en bronreadcanaries bewaken de echte HTTP-ingang.

Met 32 en 128 zware historische versies blijft de kaartread drie actuele facts
laden. Met 26 en 51 toegewezen documenten laadt pagina 1 exact 25 documenten /
75 facts / 322975 JSON-bytes; de laatste pagina één document / drie facts.
Dit bewijst begrensde factoverdracht en geen bron-/historiepayload op de route.
Metadataselectie blijft over toegewezen documenten scannen. Navigatie is een
aggregaat over alle toegewezen documenten en heeft geen paginaconstante kost.
Andere ingest/publish-badges behouden hun bestaande SQL; geen algemene claim
dat alle database-I/O historie-onafhankelijk is. MET-17/#888 houdt de uiteindelijke
runtime-/SLO-acceptatie van maximaal drie seconden.

De twee afzonderlijke adversariële reviews hebben fysieke metadata-autoriteit,
volledige compacte extractieheaderbinding, assignmentrevocatie bij ontbrekende
facts, reviewerconsistentie en numerieke refs-gelijkheid laten corrigeren.
Alle gerichte onafhankelijke herstelproeven zijn groen. Canonieke hashes zijn
daarbij niet genormaliseerd; alleen de bestaande refs-gelijkheid is behouden.

Definitieve native matrix: 44 tests groen plus de afzonderlijke herstart-/
readerrollback- en publicatieactualiteitstests groen, plus twee routeproeven
voor het trajectoverzicht (48 totaal). De compacte
lifecycle-read herstelt, net als de legacy reader, altijd zijn tijdelijke tree-
prefetchscope: een volgende commandread ziet een tussentijdse canonieke publicatie.
Het native tegenvoorbeeld is rood/groen uitgevoerd; de fix is afzonderlijk
read-only gereviewd en alle 21 betrokken kaart-/badge-/rollbacktests slagen.
Met 32/128 historieversies zijn de factpayloads
13387/13391 bytes voor drie actuele records (kleine identiteits-/versielengte-
variatie). Daarnaast slagen 38 bestaande native POST-/lock-/concurrency- en
overzichtsregressies en 6 architectuurinvarianten. Volledige regressie- en
CI-uitkomsten worden bij de PR vastgelegd; productie/SLO is hiermee niet bewezen.

De volledige CI bracht aanvullende bestaande readcontracten aan het licht.
Nu ingest geïndexeerde bronviews voorbereidt, toetsen instrumentatie- en
bronhergebruiktests beide layouts expliciet: native nul reconstructies en de
oorspronkelijke raw-/legacybudgetten, met identieke HTML en objectevidence.
De bestaande bronwindowowner selecteert voor de native variant het objectvenster;
de strikte één-fragmentassertie blijft voor eerste/middelste/laatste object gelden.
Volledige bronconsumers halen root, blocks, membership en fragments nu in één
SQL-snapshot op, met alle bestaande pin-/hash-/membershipchecks. Dit herstelt
het ongewijzigde publicatiegereedheidsbudget van maximaal vijf queries; het
begrenst geen volledige bronpayload en verandert de selected/windowbranch niet.
Rood/groenbewijs: 60 betrokken bron-/diagnostiek-/publicatietests plus zes
windowtests groen. De SQL-batch is afzonderlijk read-only gereviewd.
De resterende volledige-suitebevinding betrof historische structurele objecten
met stringreferenties. De compacte velden behouden die representatie zonder
nieuw bronbewijs; hash/bronowners en capturechecks veranderen niet. De bestaande
native audit-/publicatiegateproef is rood/groen uitgevoerd en de compatfix is
afzonderlijk read-only gecontroleerd.
De automatische PR-review signaleerde daarnaast dat de middlewarebypass te
breed was. Alleen de persoonlijke reviewerlanding (`work=mine`) slaat de globale
lifecycle-prefetch over. `work=all` en publisher-only houden de bestaande batch,
ook bij een ontbrekend origineel; twee echte auth-/HTTP-tegenvoorbeelden zijn
rood/groen uitgevoerd. De route-/auth-/threadgrens is afzonderlijk gereviewd.
