# HA-4 — gedeelde lezers en gecontroleerd stoppen van AI-prozapogingen

Change class: A
Rewrite risk: high
Promise: Een bevoegde bronactor kan oude AI-prozapogingen voor één ongepubliceerde werkrevisie expliciet stoppen; opgeslagen werk blijft behouden en oude workers/retry kunnen niet opnieuw activeren.
Proof: Helper-/hash-equivalentie, echte HTTP en native PostgreSQL voor beide inputlayouts, stale/duplicate/authorization, worker/stop-race, restart, backup/restore en oude-writer-bypass; volledige repository-CI.
Touches lifecycle invariants: yes

William gaf op 9 november 2026 expliciet opdracht de resterende koppelingen
los te maken en lopende AI-taken gecontroleerd af te handelen. Basis is main
`70b1c723` (#1034 gemerged). #1017 en het gepinde HA-1-ontwerp blijven leidend.
Deze opdracht bouwt overgangscapaciteit; zij voert geen productiecutover,
bulkstop, menselijke takeover, deployment of definitieve prozaverwijdering uit.

## Lifecycle vóór productcode

Lifecycle entity: ongepubliceerde WorkingRevision, oorspronkelijke AI-pogingen en hun bron-/bewijsartefacten.
Lifecycle transition: expliciet stopcommand → lopende prozapogingen terminal failed met gerichte overgangsreden → duurzame, bron- en werkrevisiegebonden uitvoeringsblokkade.
Initial durable state: bestaande native workflowdocumenten met inline of relationele AI-pogingen; bron is immutable; er is geen publicatiebijdrage uit deze werkrevisie.
Trigger: geauthenticeerde POST met snapshot, actuele attempt-ID, command-ID, verwachte objectrevisie en reden; inventaris lezen/startup stoppen niets.
Authorization: bestaande source_selection.authorize; iedere herhaling controleert actuele account-/brontoegang opnieuw, plus bestaande mutability/publicatiegrens.
Validation: huidige WorkingRevision, bronhash/-versie, actuele poging, object-CAS, geldig command en reden; human-build en beslisboom weigeren; nieuwe commando's op een reeds gestopte werkrevisie conflicteren.
Mutable entities: uitsluitend bestaande processing_attempts en append-only prose_transitions-commandbewijs in dezelfde workflowdocumentauthority.
Immutable entities: bronbytes, extractieversies, task/checkpoint/providerartefacten, huidige/historische kandidaten en reviewbesluiten, canonieke releases en registry.
Workflow state before: bestaande processing/in_review/blocked-afleiding.
Workflow state after: oude uitvoering is geblokkeerd met menselijke vervolgactie; geen nieuwe workflowstatus en geen impliciete goedkeuring of annotatie-eigendom.
Release state before: geen publicatiebijdrage uit betrokken werkrevisie; eventuele oudere release blijft immutable.
Release state after: ongewijzigd.
Serving state before: bestaande publication registry.
Serving state after: identiek, ook na restart/restore.
Expected API result: exact opgeslagen stopreceipt of conflict; inventaris toont de huidige bron, poging en expliciete vervolgbehoefte zonder providercall.
Expected UI result: bestaande werkplek/lezers blijven toegankelijk; de API is de bedieningsingang van deze slice, zonder nieuw formulier of vervangende reviewpagina.
Failure result: geen gedeeltelijke stop of verloren input; bij stale/unauthorized/commit failure blijft de eerdere toestand intact. Een reeds verstuurde providercall kan eindigen, maar mag na de stop niet meer activeren.
Restart result: terminale pogingen en uitvoeringsblokkade blijven behouden; dispatcher vindt geen automatisch hervatbare oude prozataak.
Recovery result: bestaande workflowbackup/lege-doelrestore behoudt overgangsbewijs en weigert oude uitvoering; ontbrekende native guards weigeren het stopcommand vóór mutatie.
Legacy-data result: oude publicaties/bewijzen blijven leesbaar; nieuwe guards veranderen historische rijen zonder overgangsbewijs niet. Beide bestaande documentinputlayouts blijven ondersteund.
Required black-box scenario: echte bronontvangst → AI-poging reserveren/checkpoint → HTTP-inventaris → geautoriseerde stop → restart → oude delivery/retry/claim weigert zonder providercall of objectmutatie; onafhankelijke human/boom- en publicatieketens blijven werken.
Explicit non-goals: productie-inventaris uitvoeren, automatische AI→human-selectieconversie, oude kandidaten verwijderen, volledige takeover van reeds geactiveerde objectsets, nieuwe reviewerpolicy, praktijkacceptatie of globale cutover.

GIVEN een ongepubliceerde actuele werkrevisie met AI-prozapoging,
WHEN een bevoegde actor die exacte poging met actuele objectrevisie stopt,
THEN blijven alle bron-/werk-/bewijsobjecten behouden, verliezen oude workers
hun uitvoerrecht en blijft die blokkade na restart/restore gelden, zonder
servingwijziging of automatische menselijke overname.

## Eigenaars, context en herschrijfrisico

Rewrite target: gedeelde bron-/providerhelpers en de uitvoerbaarheid van bestaande AI-pogingen na een expliciete per-revisieovergang.
Why local patching is insufficient: alleen een startknop verbergen stopt geen dispatcher, lease, checkpoint, directe strategieaanroep, retry of rollbackwriter.
Current authority/writer/reader map: authenticated API → bestaande bronautorisatie → reprocessing transaction (authorization/document-lock) → workflowdocument/attempt-writer; native worker/checkpoint/activation lezen dezelfde document- en attemptauthority. Bronviews, historische bewijs-/forensische lezers en boomtransport krijgen pure/shared helpers; de bestaande proza-uitvoerder importeert diezelfde functies zolang cutover niet bewezen is.
Supported runtime topologies: native PostgreSQL met inline/relational processing en documentinputs legacy/v1, lokale/Azure immutable source adapters, bestaande meerdere consoles/workers en daadwerkelijke console-MRO; geen file-only productieauthority.
Persisted-state impact: additieve migratie met native guards; append-only commandbewijs in het bestaande documentpayload, terminale bestaande attempts. Geen bron-/object-/reviewbackfill.
Compatibility/migration plan: expand met guards en nieuwe commandcapability; historisch werk zonder marker blijft functioneren. Geen nieuwe standaardmodus, parallelle keuzeroute of automatische stop bij installatie.
Rollback/recovery plan: vóór commandgebruik is de refactor terugdraaibaar. Na gebruik behouden DB-guards de terminale toestand en weigeren oude writers die markers laten vallen of nieuwe AI-uitvoering starten. Serving blijft staan; forward fix of bewezen herstel met geschikte readers. Geen destructieve downmigratie of heimelijke AI-fallback.
Cutover trigger: deze capability draait uitsluitend na expliciet per-revisiecommand; globale cutover vereist de afzonderlijke praktijk-/releasevoorwaarden uit #1017.
Cleanup/decommission criteria: bron-/historische lezers en beslisboomtransport importeren geen proza-uitvoerder meer. Tijdelijke re-exports in de oude uitvoerder verdwijnen bij definitieve subtractie; resterende uitvoerende productingangen staan expliciet open tot die fase.
Failure blast radius: betrokken ongepubliceerde werkrevisie en oude uitvoerpogingen; geen mutatie van kandidaattekst, oordeel, release of serving.
Adversarial proof matrix: forged/stale/duplicate command, revoked actor, boom/human misrouting, oude worker/claim/checkpoint/activation tegenover stop, oude document-/attemptwriter die marker verwijdert of AI herstart, beide layouts, rollback, restart en lege-doelrestore.

| Gegeven | Producent / consument | Authority en geldigheid |
| --- | --- | --- |
| Snapshot/bron/WorkingRevision | ingest → stopcommand, alle workers | bestaande workflowdocumentidentity; exacte hash/versie/werkrevisie, geen fuzzy overname |
| Poging/claim/checkpoint | bestaande reserve/dispatcher → stop/checkpoint/activatie | bestaande attempts; stop onder dezelfde documentgrens, geen nieuwe queue |
| Overgangsreceipt | expliciet stopcommand → reserve/strategie/API/DB-guard | append-only in workflowdocument, één command per betrokken werkrevisie; geen procesflag |
| Bronviews en historische hashes | oorspronkelijke extractie/proof → human/boom/readers | dezelfde fragmentfilters/contractstrings/serialisatie; equivalentie vóór calleromzetting |
| Review/publicatie | bestaande owners → huidige lezers | geen nieuwe rechten; registry blijft servingauthority |

De stop is atomair met zijn receipt. Een worker die eerder commit wint, maakt
een stale stop zichtbaar via CAS; wint de stop, dan weigeren de bestaande
attemptfences verdere checkpoints/activatie. Native guards beschermen ook
tegen een oude writer die het overgangsbewijs niet begrijpt. Een verlopen
of geweigerde poging is geen verloren bron en geen geslaagde vorming.

Een expliciete nieuwe menselijke bronvoorbereiding blijft een afzonderlijke
bestaande handeling. Waar reeds opgebouwde kandidaten/semantisch bewijs een
takeover vereisen, blijft die weigering zichtbaar; deze slice wist ze niet.

## Implementatie en verificatie

De gedeelde owners zijn `prepared_source_views_v1` (bronfilters),
`semantic_proposal_contract_v1` (historische contracten/proposalvalidatie) en
`bounded_model_call_v1` (boomtransport en responseparser). Een verse interpreter
weigert de oude executorimport tijdens het laden van bron-, bewijs- en
forensische lezers en boomtransport. De vaste fixture uit main `70b1c723`
bewaart bronfilterresultaten, drie contractstrings en drie schemahashes;
raw en voorbereide carriers leveren dezelfde resultaten.

Native PostgreSQL 16: 51 gerichte stop/herstel/worker-tests slagen; de uitgebreide
laatste matrix met inline pogingen, beide inputlayouts, API-validatie,
boom/human-afwijzing, helperbewijs en architectuurinvarianten slaagt (21 tests).
De ondersteunde combinaties zijn legacy inputs + inline pogingen, legacy inputs
+ task-v1 en v1 inputs + task-v1; v1 inputs weigert inline opslag al bij ingest.
De worker/providerrace behoudt opgeslagen extractieversies en activeert geen
object na stop. Twee onafhankelijke consoles met hetzelfde command krijgen
één receipt. Geïnjecteerde commitfout rolt attempts én receipt terug.

Workflowback-ups gebruiken versie 13. Versie 12 zonder stopbewijs wordt zonder
nieuwe domeinbesluiten opgewaardeerd; oudere versielabels met stopbewijs worden
geweigerd. Lege-doelrestore behoudt de receipt en blokkeert opnieuw starten;
ontbrekende guards laten het doel leeg. Oude SQL-writers die metadata laten
vallen of een poging heropenen worden in beide layouts geweigerd.

Afzonderlijke codecontrole toetst API/autorisatie → documentlock → atomaire
attempt-/receiptopslag → claim/checkpoint/activatiefences → restart/restore.
Historische kandidaatsets en serving hebben geen nieuwe writer. De routegolden
verandert uitsluitend door de nieuwe GET/POST. Contractwijzigingsinjecties in
bestaande tests richten zich op de nieuwe contractowner; hun weigeringen
blijven vereist. De volledige suite en remote CI zijn de resterende technische
releasecontrole; uitkomsten worden op de PR vastgelegd. Technisch testbewijs
is geen praktijkacceptatie of bewijs dat productie al is gestopt.

Compositiediagram en uitleg bijgewerkt in
`docs/architecture/prose-transition-1017.md` en de AI-uitleg van
`src/settings/metis_explained_content.py`. De bestaande presentatie is behouden;
er is geen nieuw formulier of automatische uitvoerhandeling toegevoegd.

Aanvullend bewijs: 111 tests voor contractwissels en native databasecontroles
slagen met lokaal `psql`; 12 tests voor code-rollback, legacy upgrades en
herstelformaat slagen. De vaste verwachtingen voor het actuele herstelformaat
zijn versie 13; historische inputversies blijven staan. Een versie-12-archief
zonder stopbewijs wordt in beide layouts exact opgewaardeerd.

Chromium: 13 tests (12 stop/herstel plus de bestaande browserproef gericht op
de AI-modeluitleg) slagen. Acht screenshots op 1440/390 px, licht/donker,
toetsenbordnavigatie en JavaScript-uitval zijn gecontroleerd; de AI-uitleg op
beide breedtes is visueel bekeken. Geen overflow of nieuwe pagina-indeling.
Screenshots zijn tijdelijke technische bewijsartefacten, geen productiebeeld.

Bronlinkcontrole vond dat de uitleg nog naar een oudere repositoryrevisie wees,
waarin het nieuwe diagram niet bestaat. De vaste verwijzingsrevisie is nu
`6c2e156048d526221d5c34a29d8ce665fc95fba1`; alle modelbronnen bestaan op die
commit en de nieuwe diagramlink is ook via GitHub opgehaald. Dit is een
repositoryreferentie, geen claim over de actieve productiedeployment.
