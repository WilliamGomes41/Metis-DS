# Wachtfeedback op de persoonlijke Review-kaart

Change class: B
Promise: Een beoordelaar ziet tijdens verzending wat er gebeurt. Herhaald activeren verstuurt dezelfde kaart niet opnieuw. Na opslag krijgt de titel van de bestaande bevestiging toetsenbordfocus.
Proof: De bestaande persoonlijke Review-browserproef houdt de echte aanvraag tegen, herhaalt de actie en controleert het opgeslagen besluit en de bevestiging op desktop en mobiel. De bestaande PostgreSQL-tests toetsen geweigerde, verouderde en vreemde interacties.
Touches lifecycle invariants: no
Rewrite risk: none

## Besluit

Op 22 november 2026 gaf de projectlead de opdracht “Start implementatie van de verbeteringen”. Dit is de eerste uitvoering van het consoleontwerp. De huidige persoonlijke Review gebruikt de compacte beoordelingskaart en de eerder goedgekeurde bevestiging.

- [Werkpakket #1137](https://github.com/WilliamGomes41/Metis-DS/issues/1137)
- [Implementatieontwerp](https://github.com/WilliamGomes41/Metis-DS/issues/1045#issuecomment-7083786548)
- [Afspraken voor de Review-kaart en bevestiging](../architecture/review-card-receipt.md)

## Gedrag

De compacte kaart gebruikt de bestaande HTML-formulierverzending via `/review` of `/review/second-review`. Na browservalidatie toont de kaart boven de hoofdknop een voorleestekst in de bestaande tussenruimte. Goedkeuren en afwijzen tonen “Review wordt opgeslagen…”. Later beoordelen toont “Volgende passage wordt geopend…”. De acties blijven op hun plaats en krijgen geen extra beweging.

De kaart houdt de verzendstatus lokaal bij. Daardoor kan de browser bij de eerste aanvraag de naam en waarde van de gekozen knop versturen. De kaart vangt herhaalde verzendacties af en herstelt de bediening als dezelfde pagina uit het browsergeheugen terugkomt.

De bestaande beoordelingsopdracht behandelt autorisatie, validatie, het besluit en opslag. Na een geldige opslag toont de bestaande, geautoriseerde bevestiging de feitelijke opslag. Bij een weigering komt de beoordelaar terug op de bestaande foutweergave. De bevestiging en leesnavigatie blijven leeshandelingen.
