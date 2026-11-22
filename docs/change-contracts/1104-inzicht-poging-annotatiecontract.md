# #1104 — V3-contractbewijs per poging in Inzicht

Change class: B

Rewrite risk: none

Touches lifecycle invariants: no

**Promise.** Vanuit de bestaande Documentdiagnose kan een bevoegde gebruiker de verwerkingspoging aanwijzen en de verwachte bronrevisie en gebruikte annotatieversie herleiden. Het bestaande JSON-verwerkingsspoor geeft dezelfde selectie en hetzelfde bewijs.

**Proof.** De V3-resumeproef koppelt het HTTP-verzoek aan de afgehandelde poging en vergelijkt het volledige contract en de digest met de bestaande contractfunctie. De native workerproef controleert het bewijs na overdracht en kernelherstart. De navigatieproef controleert dat documentrechten ook met een expliciete selector gelden.

## Gegevens en selectie

De workflow blijft eigenaar van poging, bronrevisie en geregistreerde contractversie. De pogingprojectie berekent SHA-256 over de volledige opgeslagen contractwaarde. Gereserveerd en uitgevoerd contract hebben eigen velden. Bij ontbrekend uitvoeringsbewijs blijft de status onbekend. De bestaande grens van 512 tekens voor `semantic_contract_version` blijft gelden. Het aanvullende veld `executed_contract_version` toont maximaal 1024 tekens. De digest blijft beschikbaar bij langere canonieke waarden. Er is geen migratie of nieuwe workflowwrite.

Documentdiagnose gebruikt het bestaande tabblad Documenten, binnen Bewijs en downloads. Zonder selector opent daar de recentste bewaarde poging. Met een selector vraagt de gebruiker exact één poging-ID of het oorspronkelijke verzoek-ID binnen het bevoegde document op. Bij een onbekende of dubbelzinnige selector volgt een expliciete melding. Bij afgekapt historiebewijs kan een uniek verzoek-ID niet worden bevestigd. Een exacte poging-ID binnen de beschikbare historie kan wel worden getoond.

Het geautoriseerde verwerkingsspoor houdt zijn bestaande antwoord zonder selector. Met een selector bevat het daarnaast status en gekozen poging-ID. Zoekresultaten zijn onafhankelijk van lokale logretentie. Bij rollback vervallen de nieuwe weergave en de aanvullende velden. Bestaande bewijsrecords blijven bruikbaar.
