# Verwerkingsbewijs downloaden

Open **Instellingen > Technisch beheer > Exports**, kies het document en gebruik
**Download verwerkingsbewijs als CSV-pakket**. Alleen een ingelogde reviewer die
aan het snapshot is toegewezen kan dit pakket downloaden.

De GET-route is `/review/processing-evidence-export?document=<snapshot_id>`.
De bestaande passage- en diagnostiekexports blijven beschikbaar.

Lees eerst `manifest.csv`. Iedere CSV heeft vaste kolommen, ook zonder rijen.
CSV-pakket v3 gebruikt `snapshot_id` en `revision_id`. Koppel deze twee kolommen
aan `revision.csv` om de exacte `objects_revision` terug te vinden. De lange
revisiecode staat daar eenmaal. V2-pakketten bevatten deze code nog op iedere rij;
v2-consumenten moeten voor v3 de join ondersteunen. De in-memory/MCP-projectie
behoudt de v2-kolommen en versieaanduiding; de v3-join geldt alleen voor de ZIP. Een
historische `run_id` is een afzonderlijke sleutel. Koppel historische kandidaten
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
