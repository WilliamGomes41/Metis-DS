# Vervolgnavigatie zonder verwerkingsarchief

Change class: B
Promise: Onvoorbereide reviewkaarten leiden bij vervolgnavigatie niet tot het laden van het volledige vormingsarchief; dezelfde geautoriseerde kandidaat blijft bereikbaar.
Proof: Native PostgreSQL/HTTP met incomplete vorming, ontbrekende kaartvoorbereiding/frontiers, queueparity, dezelfde vervolgpassage, actuele autorisatie en ongewijzigde duurzame toestand.
Touches lifecycle invariants: no
Rewrite risk: none

## Opdracht en domeingrens

Onderdeel van #729/MET-36, uitgevoerd na de verwijdering van de historiepagina
in de afzonderlijke PR #971. Opdracht projectlead van 3 november 2026:
vervolg de andere performanceacties. Issue #972 begrenst deze leesslice.

Dit is een stateless query: zij selecteert een navigatiekandidaat, maakt geen
reviewbesluit en beoordeelt niet het volledige document. PostgreSQL en de
bestaande bron-/review-/publicatiekernel blijven de duurzame owners. Er zijn
geen writes, nieuwe statusvelden, cache-authorities of dataconversies.

## Aangetoonde oorzaak

`read_review_navigation` probeert eerst `capture_review_cards`. Zonder complete
kaartgegevens gebruikte hij `read_review_document(current_only=True)`. Die
documentreader materialiseert bij open vorming de volledige `formation_input`
en `processing_command_input`, hoewel de queue alleen objecten, bindings en
broninputs gebruikt. Een native test faalt op de deploymentbaseline doordat
de fallback `get_envelope`/`formation_input` aanspreekt.

De fallback gebruikt nu een eigen `ReviewNavigationInputs`-capture onder de
bestaande `workflow_read_transaction`: `review_document_input`, actuele
named-reviewercontrole, `review_document_window` of de bestaande volledige
historiecompatibiliteit en `read_bindings`. `current_revisions`,
`still_matches`, `review_source_fragments` en de bestaande bronvoorbereiding
blijven de validatie-eigenaren. Daarna selecteren de oorspronkelijke
`ordinary_review_queue`/`reviewer_route_for` de kandidaat. De gekozen passage
wordt opnieuw exact geautoriseerd en gelezen door `read_review_passage`.

Er wordt geen nieuw volledig document-/processingcache-item geïnstalleerd.
De compacte envelope heeft dezelfde captured bronpin en geeft geen bewijs van
documentclosure. Expliciete documentbeoordeling gebruikt de ongewijzigde
volledige documentreader. Ontbrekende kaarten of frontiers betekenen nooit
een lege queue; de bestaande leescompatibiliteit blijft behouden.

## Invarianten en fouten

- Alle huidige objecten blijven beschikbaar voor de bestaande queuekwalificatie;
  er is geen afgekapt object-, bron- of dependencybereik.
- Rol en named-reviewer worden gecontroleerd vóór raw object-/bronlezing.
- Objecten en bindings worden onder dezelfde native readtransactie gecaptured;
  de bronreader controleert de vastgelegde immutable bronidentiteit.
- De feitelijke passage en iedere latere write controleren hun eigen actuele
  input, autorisatie, bronintegriteit en oorspronkelijke preconditie opnieuw.
- Lees-/integriteitsfouten behouden de bestaande foutvertaling. De query maakt
  geen kandidaat, voltooit geen vorming en verleent geen publicatierecht.
- Dubbele GETs hebben geen duurzame domeintransitie. Er is geen nieuw herstel-
  of rollbackpad; een binaryrevert volstaat voor deze read-only wijziging.

## Bewijs en grenzen

`tests/test_review_navigation_fallback.py` oefent echte task-v1-activatie met
drie synthetische bronaanbevelingen, twee toegelaten kandidaten en open vorming.
De proef vergelijkt de oorspronkelijke documentreader met de nieuwe
navigatiecapture, verbiedt archive-reads, test ontbrekend kaartschema/frontier,
controleert de werkelijke volgende passage en bewaakt objecten/bindings/audit.
De finale negen tests vergelijken ook de volledige documentenvelope vóór en na
de GETs. Zij slagen; de geraakte native regressierun slaagt met 77 tests. Deze
runs overlappen en worden niet opgeteld.

De HTTP-byteproef gebruikt dezelfde huidige stores en dezelfde bron. Alleen
voor de baseline wordt de vroegere documentreader als fallback ingeplugd.
Er wordt geen synthetische provideruitvoer als productiebewijs gepresenteerd.
Gemeten JSON staat onder `evidence/review-navigation-972/` en bindt aan de hash
van de werkelijk uitgevoerde reader. Geen Azure-versnelling, volledige
performanceacceptatie of inhoudelijke productie-readback geclaimd.

Dezelfde HTTP-vervolgpassage leest lokaal 299381 → 156094 DB-JSON bytes met
39 → 36 queries; end-of-queue 331518 → 299981 bytes en 31 → 29 queries. De
latency-observaties zijn geen acceptatiecriterium; de tests bewaken bytes,
bereikbaarheid en integriteit, zonder budgets te verhogen.

Repositorypreflight, architectuurgrenzen, release-control op de acht gewijzigde
paden, change-contract, compilatie, readerhashcontrole en diffcontrole: PASS.
De eerste release-controlcontrole vond verkeerd gecombineerde bewijsmarkers;
na het scheiden van die metadataregels slaagt dezelfde controle. Er zijn geen
tests, categorieën of vereisten uitgezet.

Volledige bronlezing en alle huidige objecten kunnen bij onvoorbereide kaarten
nog steeds nodig zijn. De gewone POST/databaseafstand en het einde-queue-
overzicht blijven expliciete vervolgpunten onder #729; MET-43/#952 en
MET-44/#953 blijven open.
