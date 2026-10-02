# Verwerkingsbewijs downloaden

Open **Instellingen > Technisch beheer > Exports**, kies het document en gebruik
**Download verwerkingsbewijs als CSV-pakket**. Alleen een ingelogde reviewer die
aan het snapshot is toegewezen kan dit pakket downloaden.

De GET-route is `/review/processing-evidence-export?document=<snapshot_id>`.
De bestaande passage- en diagnostiekexports blijven beschikbaar.

Lees eerst `manifest.csv`. Iedere CSV heeft vaste kolommen, ook zonder rijen.
CSV-pakket v5 gebruikt `snapshot_id` en `revision_id`, zoals v3/v4. Koppel deze
kolommen aan `revision.csv` om de exacte `objects_revision` terug te vinden.
De lange revisiecode staat daar eenmaal. V2-pakketten bevatten deze code op iedere
rij; v2-consumenten moeten voor v3/v4/v5 de join ondersteunen. De in-memory/MCP-
projectie gebruikt nu versie v4 met de oorspronkelijke revisiekolommen; de
revision-join geldt alleen voor de ZIP. Selecteer de lezer op `schema_version`:
`processing-evidence-export-v5` voor ZIP, `processing-evidence-export-v4` voor
projector/MCP. Oudere ZIP-v3- en projector-v2-pakketten blijven afzonderlijke
contracten. De nieuwe versies voegen aan `context_evidence` de opgeslagen
`context_realization` en `source_bound_context` toe. Alleen gerealiseerd,
brongebonden bewijs kan toelating ondersteunen; detectie bewijst geen volledigheid.

Beide nieuwe contracten voegen `text`, `left_fragment_id` en `right_fragment_id`
toe aan lineage. Een `inserted_join_separator` is een ingevoegde reconstructie-
spatie met beide originele fragment-ID's. Deze rij verzint geen raw bronpositie.
De bestaande raw-range-rijen behouden hun betekenis. Separatorbewijs betreft
fragmentreconstructie; spaties tussen afzonderlijke geselecteerde bronblokken
vallen buiten deze mappingbelofte.

Een historische `run_id` is een afzonderlijke sleutel. Koppel historische kandidaten
alleen aan huidige objecten als ook versie en canonical hash overeenkomen.

Beschikbaarheid:

- `recorded`: opgeslagen bewijs, mogelijk expliciet leeg;
- `partial`: bestaande gegevens, zonder volledige uitvoeringshistorie;
- `not_recorded`: niet beschikbaar in de gelezen records;
- `not_exported`: deze export leest deze gegevensbron niet.

`semantic_proposals.csv` bevat het laatst opgeslagen gevalideerde replayvoorstel,
niet de ruwe providerrespons. `source_stages.csv` bevat huidige objecttekst, niet
een gereconstrueerde extractiehistorie. Selectiebereiken verwijzen naar de
oorspronkelijke bloktekst; pas die offsets niet toe op huidige objecttekst.
Een restbereik is geen expliciete modelafwijzing. Een opgeslagen contextstatus
`include` bewijst niet dat context daadwerkelijk is gekoppeld.

`context_evidence.csv` heeft daarnaast `source_context_review`: uitsluitend
expliciet opgeslagen bronrol en letterlijke contextkoppelingen, met bronhash,
bronposities, source/targetversies, reviewer en reden. `issues` meldt een ontbrekende
of gewijzigde koppeling. Passage-export en MCP lezen hetzelfde bewijs. De labelhint
blijft een onbeslist voorstel wanneer geen reviewerrol is opgeslagen.

De export voert geen modelaanroepen, extractie, validatie of opslagwijzigingen uit.
Hij exporteert geen volledige envelopes, accountconfiguratie of credentials.
Envelopebewijs en objectrevisie worden niet gepresenteerd als één atomische
historische pipelinesnapshot. Het manifest benoemt de grenzen per dataset.

`model_calls.csv` bevat voor nieuwe geslaagde runs met opgeslagen providerbewijs
het oorspronkelijke requestpayload zonder transportheaders, de samengevoegde
outputtekst en beschikbare response-ID, status en tokenaantallen. De deployment-
marker en aanvraagtijd horen bij de oorspronkelijke aanroep. Ook na replay is dit
geen nieuwe modelcall. Het bewijs hoort via `proposal_hash` bij het laatste
opgeslagen voorstel; oudere en mislukte pogingen vormen geen volledig archief.
Historische records zonder dit bewijs blijven `not_recorded`.

Volledige ruwe responses, stopredenen, mislukte pogingen, tussenliggende bronstadia
en individuele validatie-uitvoering kunnen niet achteraf uit deze records worden
hersteld. Reviewgebeurtenissen worden niet uit
de reviewledger opgehaald door deze export; menselijke referentiebeoordeling moet
afzonderlijk worden toegevoegd.

CSV gebruikt UTF-8 met BOM, komma's en JSON voor samengestelde waarden.
Formuleachtige cellen krijgen een voorloopapostrof voor veilig openen in Excel;
dit is exportcodering en verandert de opgeslagen bron niet.
