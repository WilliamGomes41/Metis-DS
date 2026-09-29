# Verwerkingsbewijs downloaden

Open **Instellingen > Technisch beheer > Exports**, kies het document en gebruik
**Download verwerkingsbewijs als CSV-pakket**. Alleen een ingelogde reviewer die
aan het snapshot is toegewezen kan dit pakket downloaden.

De GET-route is `/review/processing-evidence-export?document=<snapshot_id>`.
De bestaande passage- en diagnostiekexports blijven beschikbaar.

Lees eerst `manifest.csv`. Iedere CSV heeft vaste kolommen, ook zonder rijen.
`snapshot_id` en `objects_revision` identificeren de huidige export. Een
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

De export voert geen modelaanroepen, extractie, validatie of opslagwijzigingen uit.
Hij exporteert geen volledige envelopes, accountconfiguratie of credentials.
Envelopebewijs en objectrevisie worden niet gepresenteerd als één atomische
historische pipelinesnapshot. Het manifest benoemt de grenzen per dataset.

Oorspronkelijke modelrequests/responses, tokengebruik, stopredenen, mislukte
pogingen, tussenliggende bronstadia en individuele validatie-uitvoering kunnen
niet achteraf uit deze records worden hersteld. Daarvoor is afzonderlijke
registratie tijdens toekomstige runs nodig. Reviewgebeurtenissen worden niet uit
de reviewledger opgehaald door deze export; menselijke referentiebeoordeling moet
afzonderlijk worden toegevoegd.

CSV gebruikt UTF-8 met BOM, komma's en JSON voor samengestelde waarden.
Formuleachtige cellen krijgen een voorloopapostrof voor veilig openen in Excel;
dit is exportcodering en verandert de opgeslagen bron niet.
