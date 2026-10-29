# WP7 — geverifieerde bronviews tussen verzoeken

Change class: B. Rewrite risk: high. Touches lifecycle invariants: no.
Issue: #904 / MET-25. Onderzochte basis: `bab68ba` (WP6 gemergd).

## Gebruik vóór implementatie

```python
# Bestaande geautoriseerde bronvoorbereiding, vóór de korte checkpointlock:
prepared = store.prepare_review_source(input_reference, payload)
store.publish_review_source(prepared)
# Bestaande checkpointtransactie pint de verwijzing onder claim/revisie/authfence.
# Review leest uitsluitend; objects=None vraagt bewust de volledige bron.
fragments = store.read_review_source(envelope, objects=current_passage_objects)
full = store.read_review_source(envelope)
```

Een ontbrekende nieuwe layout is expliciet legacy. Een aanwezige maar ongeldige
root/member is een integriteitsfout, nooit aanleiding tot GET-herbouw. De reader
bezit lookup, dependencyverzameling en checked carrier; HTTP coördineert geen SQL.

## Bestaande werking en eigenaarschap

FormationTaskStore bewaart immutable extractie/input in021 en volledige views
in023. `TaskCheckpointWriter.retain_source_views` bereidt/hash/serialiseert vóór
`_locked`, daarna pint dezelfde bestaande checkpointowner onder document,
account, claim, revisie en deadline. `load_source_views` hydrateert alle zes views.
Review document/passage/workboard/command bereiden nu per verzoek opnieuw voor.
`review_source_window` scant raw en valt bij samengestelde zinnen terug op alles.

Alleen bestaande kernel/FormationTaskStore bezit duurzame data. HTTP bezit
verliesbare presentatie. Bronbytes/extractie blijven authority; de nieuwe
records zijn reproduceerbare afleiding, zonder approval of formation_complete.
Deterministische materialisatie blijft de enige kandidaatmaker. Workerresume,
taskplannen, identiteit en volledige closure houden hun bestaande owners.

## Gegevensvorm en integriteitsmodel

Vier additieve relationele recordsets bij dezelfde store:

| Record | Sleutel / access pattern |
| --- | --- |
| Rootheader | Exact views_id, oorspronkelijke023-payloadhash, extractiehash, bronidentiteit, extractor-/Docling-/viewcontract, counts en oorspronkelijke filtermap. Kleine PK-read. |
| Raw fragment | Root + fragment-ID, oorspronkelijke ordinal, exacte payload/hash, zes-viewmembership en onafhankelijke verwachte blokmembership per view. PK-lookup. |
| Viewblok | Root + viewnaam + blok-ID, oorspronkelijke ordinal, exact public/source-paar en hash/count. PK-lookup. |
| Blokdependency | Root + viewnaam + blok-ID + raw-ID + verwachte rawhash. Composite FK en gerichte blokindex. |

Geen volledige manifestlijst op iedere detailread. Dependencies bevatten alle
rawmappingreferenties, ook join-separators. Posities, IDs, tekst, offsets,
locators en bronpayloads worden niet gereconstrueerd of hernummerd. De checked
readcarrier bewaart de oorspronkelijke rootidentiteit en expliciete scope;
een window krijgt geen verzonnen nieuwe extractiehash. Filtercompositie volgt
de oorspronkelijke volledige filtermap, niet toevallige subsetgelijkheid.
De reader sluit raw→verwachte viewblokken→raw recursief; ontbrekende blokken
in één afzonderlijke view worden ook ontdekt wanneer hetzelfde blok-ID nog
in een andere view bestaat. Werk groeit met deze echte afhankelijkheden.

Volledige `PreparedSource`-validatie plus exacte extractiebinding gebeurt vóór
publicatie. De volledige canonical `prepare(raw)`-oracle moet gelijk zijn aan
de aangeleverde views; een intern consistent maar verzonnen blok wordt geweigerd.
Record- en filtervolgorde komt uit die oracle, niet de volgorde van JSONB-sleutels.
Nieuwe records worden als complete immutable afleiding in één eigen
artefacttransactie gepubliceerd, zonder document/account/ledgerlock. De root is
pas leesbaar met alle records; SQL-constraints en sealed-recordtriggers verbieden
later toevoegen, muteren of rechtstreeks verwijderen. De bestaande korte
checkpointtransactie pint vervolgens de bestaande source_views_ref; bij stale
claim blijft hoogstens een geldige, exact gebonden afleiding ongebruikt achter.
Die verleent geen bevoegdheid en kan nooit een andere extractie activeren.
De documentkolom `review_source_ref` bewaart de gefencete verwijzing. Dezelfde
read-layout zonder marker blijft een geldige afleiding, geen reviewbevoegdheid.
Een marker met verdwenen layout/root wordt geweigerd, niet als legacy gelezen.
Geen nieuwe job-/status-/cacheautoriteit of productiebackfill.

`review_read_envelope` bevat de bestaande reviewmetadata zonder de grote
extractie/replay/pogingsarchieven. Een SQL-trigger leidt deze kolom synchroon af
uit dezelfde envelopewrite; ook een directe cachewrite wordt opnieuw afgeleid.
Referentiepinning vult deze metadata expliciet voor oude rijen. Er is geen
historische migratie-update. De read selecteert benoemde actuele documentvelden
en de compacte metadata, zonder `d.*` of archiefprojectie; alleen oude rijen
zonder voorbereiding gebruiken de lazy legacyfallback. Rollen, reviewers,
revisie en beleid behouden hun bestaande controles. Dit voegt klein afgeleid
werk toe aan bestaande envelopewrites, zonder objectset-/archiefbackfill.

Dezelfde immutable PostgreSQL-trust als de bestaande extractiestore geldt.
Readers controleren headeridentiteit/contract, geselecteerde membership,
counts, payloadhashes en bestaande mappingvalidator. Een geprivilegieerde
database-editor die payload én alle bewijzen herschrijft valt buiten dit model.
Een selectieve read detecteert geen corruptie uitsluitend in ongebruikte records;
volledige verificatie blijft een expliciete volledige operatie. Geen cryptoboom.

## Contextcontract en domeingrens

| Gegeven | Producent/eigenaar | Geldigheid / ontbrekend |
| --- | --- | --- |
| Bron/extractie | Bestaande SourceIdentity en prepared_extraction_versions | Exacte snapshot, source/document-ID, sha256, versie, contentkind, recordhash en extractorcontract; mismatch weigeren. |
| Views | Bestaande prepare en FormationTaskStore | Huidig reconstructie-/block-/filtercontract plus oorspronkelijke payloadhash. Legacy afwezigheid apart van corruptie. |
| Mapping/member | Volledig gevalideerde publicatie | Root/view/block-ID en rawhash, originele posities en volledige rawspans; ontbrekend deel weigeren. |
| Poging/revisie | Bestaande TaskCheckpointWriter | Opnieuw controleren bij pinnen; oud werk activeert niets. |
| Rol/review/publicatie | Bestaande command-/lifecycleowners | Altijd actueel, nooit uit bronartefact afleiden. |
| Readscope | Checked tijdelijke carrier | Window bewijst geen volledige bronverantwoording. Onvolledige formation/status blijft volledige bron gebruiken. |

Domain entity/aggregate: afgeleide immutable views bij één bestaande extractie.
Durable state before: geldige bron/extractie, oude views mogelijk aanwezig.
Durable state after: dezelfde domeindata plus gevalideerde gerichte readrecords.
Transaction boundary: alle afgeleide records/header atomair; pogingpin via de
bestaande afzonderlijke gefencete checkpointtransactie, geen halfbruikbare root.
Failure/recovery result: oude reader/referenties/bron en menselijk werk blijven.
Duplicate execution / idempotency result: dezelfde inhoud geeft dezelfde root;
afwijkende payload bij dezelfde identiteit is conflict.
Concurrency result: PK + rootlock serialiseren uitsluitend dezelfde afleiding;
onafhankelijke documentreads/writes mogen doorgaan tijdens voorbereiding.
Audit/evidence requirement: oorspronkelijke bestaande checkpointreferentie en
reproduceerbare root/contract/hash; geen nieuw approval- of lifecycle-event.

## Vergelijking en besluit

Twee echte, afzonderlijke agentverkenningen onderzochten A (genormaliseerde
readrecords) en B (whole payload/lazy SQL-projectie). Geen cross-modelclaim.
Criteria: exacte integriteit, koude detail-I/O, ownership, korte documentgrens,
legacy/herstart/rollback en kleinste samenhangende API. A is gekozen. B vereist
nog JSON-array-scans/TOAST-decompressie en volledige hashes/hydratatie; het
verplaatsen van die kosten bewijst geen begrensde read. Volledige consumers
houden wel de bestaande whole-viewreader. Geen generiek managerframework.

## Migratie, uitvoering en terugdraaien

Rewrite target: Review-bronreadgrens; alleen loader aansluiten is onvoldoende.
Supported runtime topologies: beide CompleteWorkflow PostgreSQL-composities,
lokale/Azure bronadapter, nieuwe processen. Geen filefallback als authority.
Persisted-state impact: additieve026-layout; oorspronkelijke021/023 records,
objecten, beoordelingen en publicaties blijven behouden.
De gecontroleerde migratielijst registreert ook bestaande020–023 als vereisten
van de gedeelde formationstore; deze expansies doen geen historische cutover.
Compatibility/migration plan: schema expand, nieuwe geautoriseerde voorbereiding
publiceert readrecords, bestaande bronnen uitsluitend expliciet voorbereiden,
reader gebruikt exacte bestaande root indien beschikbaar. Legacy reader blijft
bereikbaar; GET/startup schrijft of backfillt geen views.
Voor een bestaande extractie is `prepare_review_source_views` de expliciete
kernelcommand. De operatoringang is `scripts/prepare_review_source_records.py`
met actor, snapshot en exacte bestaande objectsetrevisie. Geen modelcall,
automatische scan/backfill of vernieuwen van kandidaten. Productieapply is apart.
Rollback/recovery plan: compatibele oude reader met originele extractie/023;
additieve records mogen blijven. Geen destructieve downmigration of reset.
Cutover trigger: volledige parity, selected corruptiematrix, native kosten,
legacy/partial formation, concurrency, nieuw proces en rollback groen.
Cleanup/decommission criteria: overgezette reads bouwen geen blokken en laden
geen ongebruikte views; volledige consumers en legacygrens expliciet behouden.
Failure blast radius: afgeleide beschikbaarheid van één extractie, geen lifecycle.
Adversarial proof matrix: verkeerde root/view/bron/contract, ontbrekend/corrupt
member/mapping, onderbreking/rollback, gelijktijdige publicatie, stale claim,
nieuwe runtime, legacy voorbereiding, partial formation, GET zonder writes.

Eerst geen veilige subtractie: de legacyreader is noodzakelijk. Alleen benodigde
schema/carrier toevoegen, vervolgens echte lees-/voorbereidingsroutes aansluiten.
Belofte bewijzen via dezelfde sourceoracle en native HTTP/storage; transfer,
hydratatie/validatie en totale respons afzonderlijk meten. #888 blijft eigenaar
van integrale eindacceptatie; geen productie-SLO uit synthetische samples.
Agree: uitvoering expliciet door William gestart. Scrap bij tweede authority,
ontbrekende membershipcontrole of terugkerende full-readworkarounds.
