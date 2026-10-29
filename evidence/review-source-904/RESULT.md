# WP7 / MET-25 — bronviews tussen verzoeken

Change class: B. Rewrite risk: high. Touches lifecycle invariants: no.
Basis: `bab68ba` (WP6 / PR919). [Ontwerp en ownership](../../docs/architecture/review-source-904.md).

## Geleverd gedrag

FormationTaskStore publiceert een exact geverifieerde immutable readlayout bij
de bestaande extractie. De root, rawfragmenten, canonieke viewblokken en hun
membership committen atomair zonder documentlock. Alleen de bestaande gefencete
checkpointowner of expliciete kernelvoorbereiding pint review_source_ref.
Ongebruikt geldig voorbereidingswerk kan na een stale poging blijven staan;
het verleent geen review- of activatiebevoegdheid.

Passage-GET sluit benodigde blok/raw/view-afhankelijkheden via gerichte PK/index-
reads. Identieke views delen hun door de bestaande oracle bewezen gelijke
blokpayload; alle zes view-/filtercontracten en originele globale posities blijven
behouden. Docling-records worden alleen bij expliciete behoefte geladen.
Document-, workboard-, status- en commandconsumers kunnen bewust een volledige
voorbereide bron aanvragen. Een window bewijst geen volledige vormingsafsluiting.

Schema026 is additief; de migratielijst bevat ook de bestaande020–023-vereisten.
Geen bron-/object-/review-/publicatiemutatie of automatische historische cutover.
Ontbrekende voorbereiding gebruikt expliciet de oude reader. Verdwenen/corrupte
vastgelegde evidence geeft een fout, nooit GET-herbouw of stille downgrade.
Voor bestaande bronnen is de expliciete prepare_review_source_views-command
bestaand geautoriseerd, revisiegebonden voorbereidingswerk; geen modelcall.

## Native bewijs vóór de volledige suite

34 gerichte tests passed,0 skips,65.18s; Python3.12.14, PostgreSQL16.
De groep bevat volledige/selected oraclepariteit, beide native consolecomposities,
herhaalde echte HTTP-GETs na een nieuwe runtime, partial formation met volledige
closure, koude broncache zonder GET-write, retained Docling-mapping/record,
expliciete legacyvoorbereiding, gecontroleerde migratieherhaling, concurrency,
onbeschermde voorbereiding en weigering van stale pinning.

Corruptiematrix: verloren root/layout, verkeerde header/hash/bron/contract,
rawinhoud/hash/ordinal/viewmembership, blokinhoud/hash/ordinal, verdwenen
dependencies en één afzonderlijke verdwenen view. Een intern consistent
verzonnen blok met vernieuwd blok-ID wordt vóór publicatie tegen de volledige
bronoracle geweigerd. Herordende JSON-sleutels leveren dezelfde publicatie.

Rood/groen:

- Dezelfde32-passage-GET op ongewijzigde bab68ba faalt op de verboden volledige
  bronread/herbouw; de nieuwe native proef slaagt zonder die route.
- Een geïsoleerde in-memory mutatie die de vergelijking van declared/actual
  membership weglaat laat de single_view_block-regressietest falen door
  `DID NOT RAISE`; de oorspronkelijke controle blijft in de implementatie.
- Afzonderlijke native agentprobe reproduceerde een request-cache-headergat;
  de cache bindt nu ook extractieversie/sourceheader. Dezelfde probe slaagt.
- Afzonderlijke native agentprobe reproduceerde volgordegevoelige idempotentie;
  alle afgeleide records komen nu uit de canonical bronoracle. Regressie groen.

Twee afzonderlijke agents voerden ontwerpverkenning en begrensde adversariële
inspectie uit. Dit is geen cross-modelclaim. Statische bevindingen over verdwenen
viewmembership/layout en sealed-insert zijn hersteld en native getest; de
veronderstelde seal-race is ingetrokken als onbewezen, niet als bug geteld.

## Kosten en bewijsgrenzen

De vaste passagekeuze bevat maximaal25 peers plus doel en gedeelde kop. De
bronread draagt alleen die echte dependencyclosure over, niet alle bronviews.
De HTTP-proef registreert bronrecordrijen/JSON-bytes, totale HTTP-tijd en
afzonderlijke hydratatie/validatiefasen; blokherbouw is verboden.
Getallen uit vóór de laatste deduplicatie zijn geen finale performanceclaim.
De machine-uitvoer en volledige-suite/CI-status volgen bij de PR-handoff.

Volledige bronconsumers en onvolledige vormingsafsluiting groeien bewust met
hun complete bronafhankelijkheid. De bestaande bronbyteverificatie/open-original
blijft afzonderlijk; geen nieuwe toestemming uit een snelle read afleiden.
Synthetische lokale voorbeelden zijn geen productie-SLO, p95 of replay van699.
#888/MET-17 blijft eigenaar van de totale gebruikers-/runtimeacceptatie.

De trustgrens is de bestaande vertrouwde immutable PostgreSQL-owner: publicatie
controleert de volledige bronoracle en beschermt vervolgens records/membership.
Een privileged editor die alle payloads én bewijzen consistent herschrijft valt
buiten dit model. Een detailread detecteert geen schade uitsluitend buiten haar
geselecteerde dependencies. Er is geen nieuwe cryptoboom of signingframework.

## Verificatie bij start van de volledige suite

Repositorypreflight, release-control, compileall en architectuurgrenzen zijn groen.
De uitgebreidere architectuurset vond twee legacyread-regressies; die zijn
hersteld met een exact gebonden extractieread zonder replayarchief.
De workerresume nam aanvankelijk review_source_ref niet mee; resume/retry
bewaart nu deze broncontext naast de bestaande source_views_ref. De50
worker-/Docling-regressies zijn daarna groen. Een sequentiële verkennende suite is na139 groene
tests netjes onderbroken; de volledige bestaande vierdelige CI-runner wordt
uitgevoerd met inventaris/digest/JUnit-aggregatie. Nog geen volledige groenclaim.
Deployment, productieapply, backfill en merge zijn niet uitgevoerd.


Compacte metadata wordt synchroon uit de definitieve envelope afgeleid na de
bestaande lifecycle-trigger, ook wanneer die een impliciete reparatie doet.
Native tests bewijzen directe cachewrite-correctie, impliciete reparatie en
het niet evalueren van de legacyarchiefprojectie. Deze afleiding voegt werk
toe aan bestaande documentwrites; de oorspronkelijke lifecycle-trigger
normaliseert de envelope daar al. De bestaande POST-/lockproeven blijven
vereist; geen claim dat documentwrites onafhankelijk van archiefgrootte zijn.


## Definitieve gerichte HTTP-meting

Broncommit `7b94d79`; zes native HTTP-tests groen,0 skips,47.94s.
[Machine-uitvoer](http-metrics.json) bevat acht opeenvolgende GET-samples:
32/128 passages × lokale/Azure compositie × twee verzoeken na herstart.
Hetzelfde venster draagt steeds138 bronrecords over,141780/141782 JSON-bytes.
Hydratatie exclusief validatie:1.741–4.415ms; mappingvalidatie:2.650–14.335ms.
Totale HTTP-tijd:0.2048–1.8697s; de vier suiteprocessen startten tijdens de
latere samples, dus deze gedeelde runner bewijst geen latencyverdeling/SLO.
Azure betekent de ondersteunde compositie met fixture bronstore en echte
HTTPS Origin, geen live Azure-netwerkmeting. Transfercijfers tellen alleen
source_read-records; bronbyteverificatie en overige responsekosten staan apart.
