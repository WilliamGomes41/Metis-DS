# HA-2b prerequisite: betekenis en essentiële relaties duurzaam aanwijzen

Change class: A
Promise: De researcher bewaart exacte betekenisvelden en bronrolvoorstellen en herstelt of verantwoordt een ontbrekend essentieel verband, zonder overschrijven van claims of stil verlies bij hervatten, oudere clients en workflowherstel.
Proof: native PostgreSQL, HTTP en echte browser; resultaten hieronder pas na uitvoering.
Touches lifecycle invariants: yes
Rewrite risk: high

Deze afgebakende prerequisite binnen #1015 / MET-59 volgt op #1021/#1022 en het
[uitvoeringscontract](1015-human-annotation-execution.md). De expliciete opdracht
“Start 2b” autoriseert deze uitvoering; de oude needs-triage/planningregistratie
is geen separate startopdracht. Geen issue-Done, merge of release door de agent.
De nog niet opgeleverde afsluit-/bouwroute blijft apart en gebruikt daarna één
materialiser en de bestaande FormationEvidence-owner. De ongecommitteerde
bouwtak is geen geleverd productbewijs.

## Lifecycle

Lifecycle entity: annotation-ID binnen één ongepubliceerde WorkingRevision.
Lifecycle transition: gepinde invoer -> nieuwe immutable annotatierevisie met exacte velden, bronrolvoorstel en expliciete essentiële verplichtingen -> opgeslagen overzicht/hervatten.
Initial durable state: 034-set met bron-/extractiepin, heads/generatie en object-CAS; geen kandidaatset.
Trigger: selecteren/koppelen, autosave, gereed melden, essentieel verband verwijderen/herstellen of expliciet met reden terugnemen.
Authorization: bestaande actuele source-selection-autorisatie en mutable WorkingRevision, ook voor duplicate requests.
Validation: exacte halfopen codepoint-/grapheme-/quoteankers, gesloten bestaande veld/bronrolcontracten; v2 mag niet door v1 worden overschreven; essentiële relatie blijft aangewezen of expliciet open/teruggenomen.
Mutable entities: bestaande setgeneratie en heads, in dezelfde workflowtransactie.
Immutable entities: bron/extractie, annotatieversies, actor/commandreceipts en alle publicatie-/reviewhistorie.
Workflow state before: processing.
Workflow state after: processing; ready betekent alleen opgeslagen selectie, nooit reviewgoedkeuring/bronafsluiting.
Release state before: eventueel bestaande historische/actieve voorganger.
Release state after: ongewijzigd; deze opdracht schrijft geen publicatierelease.
Serving state before: bestaande publicatieregistry.
Serving state after: ongewijzigd; annotatie verandert geen serving.
Expected API result: revisie/generatie/receipt na servercommit; identieke duplicate idem; stale/legacy/verliesverzoek weigeren zonder nieuwe rij.
Expected UI result: bron aanwijzen voor noodzakelijke betekenisvelden; bronrolvoorstel zonder KO; ontbrekend essentieel verband opnieuw aanwijzen of met expliciete reden terugnemen, zichtbaar in overzicht.
Failure result: geen gedeeltelijke revisie/head/receipt; editor behoudt aanwijzingen en toont herstelactie.
Restart result: nieuwe productieconsole/proces leest dezelfde velden/relaties/status uit PostgreSQL.
Recovery result: bestaande workflowexport/lege-doelrestore behoudt canonieke input/historie, controleert ook relatiecontinuïteit; geen nieuwe inhoudelijke keuze.
Legacy-data result: bestaande v1-entries blijven exact leesbaar; v2 is expliciete nieuwe inputvariant, oude writers mogen haar niet degraderen.
Required black-box scenario: echte ontvangstroute -> bron openen -> meerdere bereiken/veld selecteren -> pause/login -> essentiële voorwaarde verwijderen -> servercommit open verplichting -> gereed weigeren -> opnieuw aanwijzen -> gereed en overzicht -> nieuwe productieconsole/back-up/restore behoudt input, geen kandidaten/review/serving.
Explicit non-goals: seal/job/human FormationEvidence/materialisatieactivatie, HA-3, globale HA-4-cutover en researcherpraktijkacceptatie worden met deze prerequisite niet voltooid.

GIVEN gecommitteerde brongebonden invoer met essentieel verband,
WHEN de researcher dat bereik verwijdert,
THEN wordt het verband als open verplichting bewaard, kan ready niet slagen,
en blijft het na herstart zichtbaar tot opnieuw aanwijzen of expliciete
terugname met reden; serving blijft ongewijzigd.

## Bestaande betekenis en identiteit

MET-49 / #986 blijven leidend: één claim met context, bewijs en provenance.
De oudere definitie “kleinste stuk richtlijntekst” is expliciet achterhaald.
Keuze A uit de sessie blijft: voorwaarde/uitzondering bij een claim wordt
brongebonden context, niet automatisch een afzonderlijk kennisobject.
Deze inputlaag maakt geen canonical text, candidate-ID of kandidaatmapping.

Bestaande source_bound_fields_v3.FIELDS/MISSING en source_accountability.ROLES
blijven de gesloten vocabularia. Veldankers zijn exacte bronposities met
transiënte quotegetuige; geen claim overtypen, fuzzy herstel of normalisatiewijziging.
De aangewezen kerngroep mag expliciet type-/kernbewijs aanduiden, maar niet
onderwerp/handeling/doel raden. Verdere veldverplichtingen blijven gelden bij
latere afsluitcontrole/admission; opgeslagen ready is geen volledige kandidaatvalidatie.
Quote wordt niet extra opgeslagen/exporteerbaar gemaakt; bestaande bronrechten
blijven gelden. Geen besluit dat bepaalde richtlijninhoud nooit een KO is.

Relatie-ID is een opaque, canoniek UTF-8 JSON-anker onder de annotation-ID
met prefix link-v1, oorspronkelijke rol/blok/start/end. Herankeren behoudt de
relatie-ID en krijgt een nieuwe exacte ankergetuige. Rol hoort bij identiteit;
inhoudelijke functiewijziging wordt als nieuwe annotatierevisie vastgelegd.
Een essentieel verband mag alleen essentieel gebonden blijven, expliciet open
blijven (blokkeert ready), of met reden worden teruggenomen. Hele entry
terugnemen is een expliciete bestaande withdrawn-revisie, geen fysieke delete.

## Rewrite-mitigatie

Rewrite target: annotatie-inputcontract en behoud van essentiële betekenisrelaties.
Why local patching is insufficient: een browser-only waarschuwing verliest verplichtingen bij reload, oudere client of direct SQL; server en herstel moeten dezelfde relatiecontinuïteit bewaken.
Current authority/writer/reader map: human_annotation_v1.prepare/save/overview/validate_stored_selection; human_annotation_ui_v1 routes /annotations, /annotations/source, /annotations/api en editor.js; bestaande annotation_* tabellen/034-triggers; formation_recovery_v1._validate_annotations en workflow_chain_recovery_v1 export/restore; oudere binaries/direct SQL. Volledige overige routekaart staat in het uitvoeringscontract.
Supported runtime topologies: workflow PostgreSQL, legacy en v1 document-input-layout, dezelfde productiecompositie met lokale of Azure immutable bronstore; geen annotatie-file-store.
Persisted-state impact: optionele expliciete v2 payloadvariant in bestaande immutable versies; additieve 035 constrainttrigger, geen backfill/nieuwe store of tabel.
Compatibility/migration plan: v1 input blijft leesbaar, v2 velden behouden canonieke shape; deferred native fence controleert v2->v1 en essentiële continuïteit ook bij omgekeerde restore-rijvolgorde. Archiveformat blijft v10/formation3 omdat de tabellen/kolommen gelijk blijven; oude archivevalidator weigert onbekende v2 payload in plaats van haar stil te verliezen.
Rollback/recovery plan: oude binary kan v2 niet overschrijven; 034 kandidaat-/AI-fences blijven ongewijzigd actief. Restore naar lege doel via bestaande exclusieve transactie valideert alle historische revisies, brongetuigen en receipts. Geen destructieve productiemigratie.
Cutover trigger: native CAS/duplicate/stale/relatieverlies/restore/SQL-rollback en echte browserproeven groen op exacte code; HA-2b afsluiten/activatie wordt hiermee nog niet ingeschakeld.
Cleanup/decommission criteria: geen parallelle creator/job/reviewstore; v1 compatibiliteitslezen blijft voor historie. Oude prozacallers en broncontextpagina worden pas bij bewezen HA-4 globaal verwijderd.
Failure blast radius: alleen betrokken ongepubliceerde annotation-ID/set; geen release/servingwijziging.
Adversarial proof matrix: oudere client tegen v2, direct SQL v2-degradatie/relatieverlies, reanchor met ander ID, dubbele/stale commands, twee tabs, open verplichting ready, gewijzigde veldquote, beide documentlayouts, herstart en corrupte historische workflowrestore.

## Bewijs

Nog niet voltooid. Voor PR volgen gerichte native proeven, browser op desktop en
mobiel, aparte adversariële pass en de verplichte repositorychecks/volledige
suite. Geen technische fixture als praktijkacceptatie presenteren.

### Uitgevoerde gerichte verificatie

- 47 native PostgreSQL-gevallen groen: annotatie/v2-input/production-migratieplan.
  Dit omvat beide document-input-layouts, exacte duplicate/CAS, gelijktijdige
  veld- en essentiële-contextcorrectie, opnieuw aanwijzen, expliciete terugname,
  rechtstreekse SQL-v2-degradatie/veldverlies/relatieverlies en head-terugzetting,
  normale herstart en lege-doelrestore met omgekeerde rijvolgorde.
- Zelfconsistente corruptie van een historische relatie (inclusief opnieuw
  berekende payload- en commandhash) wordt bij restore geweigerd zonder
  gedeeltelijke doelgegevens. Native constraints controleren beide aangrenzende
  revisies en de actuele head; een oudere head mag nieuwe v2-invoer niet verbergen.
- De exacte vorige archivevalidator op 9b40d8df accepteert v1, weigert v2 daadwerkelijk;
  geen stil verlies of verzonnen downgrade. Historische v1->v1-handelingen
  krijgen niet achteraf een v2-besluit toegeschreven; nieuwe editorwrites zijn v2.
- Mutatieproef op een wegwerp-database: beide nieuwe triggers uitschakelen maakt
  de native verliesproef rood met DID NOT RAISE. De eerste hook raakte een
  andere testmodule en was onbruikbaar als mutatiebewijs; de gecorrigeerde hook
  koppelt aan de werkelijk uitgevoerde functie en controleert tgenabled='D'.
  Geen mutatie in productcode of duurzame gedeelde database achtergelaten.
- Echte Chromium-keten groen op 1440/390: muis/Unicode, betekenisveld en
  richtinggetuige, opslagfout zonder vals succes, pauze wacht commit, nieuwe
  login, essentiële relatie verwijderen -> ready weigeren -> reload -> opnieuw
  aanwijzen -> ready/overzicht, vervolgens expliciete terugname met reden en
  bronrolvoorstel. De eerste volledige browserproef vond een echte fout:
  bronrolselectie van een kop ging onterecht door de kandidaatkern-resolver.
  Alleen bronrolvoorstellen gebruiken nu de reeds exacte bronankervalidatie;
  kandidaatkernen behouden de bestaande resolver. De uitgebreide keten is
  daarna daadwerkelijk opnieuw groen geworden.
- Onafhankelijke Impeccable-review vond mobiele afstand tussen bron en acties.
  Directe bronsectielinks, focusbare targets en een mobiele wisselbalk lossen
  dat gericht op; de hercontrole beoordeelt de fix als resolved/ship. De eigenlijke browsertest
  toetst beide linkmiddens via elementFromPoint op zichtbaarheid/afdekking en
  controleert heen-/terugfocus. De onafhankelijke reviewer inspecteerde alleen
  screenshots/code en claimt geen eigen browser- of praktijktoets.
- Compileall, architecture checker, 6 architectuurtests en diff/JS-check groen.
  Volledige suite en definitieve preflights worden nog afzonderlijk vastgelegd.

De native proeven draaien met PGBIN=/tmp/metis-pg16/bin (server16.4) en psql17
uitsluitend als client. Geen PG-skip als geslaagd geteld. Geen nieuwe kandidaat,
AI-fallback, approval of publicatie door deze inputstap; 034 blijft dicht.

### Volgende HA-2b-stap

Vervolg de exacte afsluit-/bouwtransitie uit het uitvoeringscontract. Migratie
035 is nu de inputfence; de nieuwe seal/human-proofuitbreiding krijgt een eigen
opvolgende migratie (036). Het overzicht moet vóór verzegeling ook de exacte
complementbereiken/volledige bronafhandeling en ontbrekende betekenisvelden
controleren. Bronrolvoorstellen en annotatie-ready geven geen bronafsluiting of
reviewgoedkeuring.

De seal moet naast entrygeneratie en document-/extractiepin ook ingestpolicy en
alle materialisatiebepalende documentmetadata binden. Een metadatawijziging kan
zonder nieuwe annotatiegeneratie plaatsvinden: dus geen uniekheid uitsluitend op
snapshot/generatie of bouwen uit actuele los gelezen documentvelden. Gebruik de
exacte overzicht-/contextidentiteit, dezelfde lock/CAS-grens voor save/seal en de
bestaande processing-attempt/lease-owner voor één herhaalbare opdracht.

Daarna pas human FormationEvidence als gesloten variant binnen de bestaande
owner/schema/FK/CHECK, echte human operational-inputrefs zonder model/replay,
de enige materialiser, exact immutable entry->objectversie/hash-bewijs en
proofgebonden native activatie. De nieuwe tabellen moeten in de bestaande
workflowback-up/restore op FK-volgorde worden opgenomen; v11/formation4 hoort bij
die toekomstige schema-uitbreiding, niet bij deze gelijk gebleven tabelvorm.
Native save->seal->build->correctie->oude activatie weigeren blijft verplicht.
Review/herstel/publicatie, API/MCP, globale verwijdering en praktijktoets blijven
ook daarna afzonderlijk bewijsbaar; het parent-issue is hiermee niet gereed.


De aparte controle na de eerste codefreeze vond een echt versiegat: een losse
nieuwe rol, relatie-ID of pending-rol zonder andere optionele velden kreeg nog
geen v2-marker. Dat tegenvoorbeeld is gereproduceerd; de canonicalisatie maakt
nu elke nieuwe capability expliciet v2. Drie native regressiegevallen bewijzen
de marker en weigering van een latere oudere client. Een nog niet toegevoegde
herstelmarkering bewaart ook de oorspronkelijke relatie-ID; native hervatten
en de browser-reload bewijzen dat dezelfde verplichting wordt hersteld.

De eerste volledige run is daarom bewust onderbroken (exit2 na5528 passed,
45 skipped,3 xfailed,29 subtests in874.19sec). Dit is geen geslaagde volledige
suite. Na reparatie:47 native plus1 uitgebreide browserproef daadwerkelijk
PASS in46.33sec. De volledige suite wordt opnieuw op de vastgezette code
uitgevoerd; definitieve resultaten volgen hieronder.
