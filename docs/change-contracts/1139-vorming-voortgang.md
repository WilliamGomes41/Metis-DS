# Voortgang in Vorming blijft op haar plek

Change class: B
Promise: De onderzoeker kan de documentkiezer blijven bedienen terwijl Metis de zichtbare actieve pogingen bijwerkt. Een afgeronde geselecteerde poging toont de vervolgactie uit de bestaande detailcontrole.
Proof: Chromium houdt een echte verwerkingspoging vast, ververst en herstelt de voortgang, en controleert focus, scrollpositie en vervolgnavigatie. PostgreSQL- en Entra-proeven toetsen begrenzing, bevoegdheid, leesgedrag en sessieverloop.
Touches lifecycle invariants: no
Rewrite risk: none

De projectlead gaf op 22 november 2026 de opdracht “Ga door” met het consoleontwerp. Deze tweede wijziging behandelt Vorming. [Werkpakket #1139](https://github.com/WilliamGomes41/Metis-DS/issues/1139) · [Implementatieontwerp](https://github.com/WilliamGomes41/Metis-DS/issues/1045#issuecomment-7083786548)

`GET /source-selection/progress` leest de bestaande compacte PostgreSQL-projectie voor de aangevraagde snapshots na controle van de actuele sessie, rol en documenttoegang. De route gebruikt passieve sessiecontrole en geeft `Cache-Control: no-store` mee. Het bestaande overzicht blijft de bron van de vergelijkbare tijdmetingen. De live kaart rekent met die bandbreedte en de verstreken tijd uit de actuele poging.

De pagina houdt maximaal één statusaanvraag tegelijk bezig en wacht vijf seconden na een antwoord. Een verborgen tabblad en handmatig pauzeren stoppen het automatisch ophalen. Handmatig verversen blijft beschikbaar, ook als link wanneer scripts uitstaan. Bij een verbindingsfout blijven de laatst ontvangen voortgang en leestijd zichtbaar. Bij gewijzigde toegang verwijdert de browser de betrokken actieve kaart.

De poging uit de aanvraag en de opgeslagen poging moeten bij elkaar horen voordat de bestaande detailcontrole wordt getoond. Voor oudere compacte projecties is de opgeslagen starttijd de referentie wanneer het poging-ID ontbreekt. Een compacte technisch geslaagde poging stelt alleen vast dat de volledigheid nog gecontroleerd moet worden. De bestaande detailprojectie bepaalt of Review of een herstelactie beschikbaar is. De pagina behoudt de documentkiezer en stelt een kaartvervanging uit zolang bediening in die kaart focus heeft.

De statusroute leest uitsluitend. Alleen de bestaande startopdracht kan een poging reserveren.
