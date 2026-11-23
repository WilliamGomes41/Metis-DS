# Ontbrekend document in Publicatie

Change class: B
Promise: Een uitgever die een link naar een onbeschikbaar document opent, ziet een melding met een directe link naar het Publicatieoverzicht. Een geldig gekozen document staat als eerste op de pagina en de andere documenten blijven ingeklapt.
Proof: De bestaande Chromium-proef controleert de melding, teruglink en documentvolgorde op desktop en mobiel. Een native PostgreSQL-proef controleert de selectie, de aanroepen voor gereedheidsbeoordeling en de opgeslagen toestand.
Touches lifecycle invariants: no
Rewrite risk: none

## Opdracht en gedrag

William gaf op 23 november 2026 opdracht voor deze stap uit het implementatieontwerp voor de Metis-console met “ga daarmee aan de slag”. [Implementatieontwerp](https://github.com/WilliamGomes41/Metis-DS/issues/1045#issuecomment-7083786548) · [GitHub #1141](https://github.com/WilliamGomes41/Metis-DS/issues/1141)

`GET /publish?document=<snapshot_id>` vergelijkt de gevraagde snapshot met de bestaande lijst van documentkaarten. Als een ingevulde selectie ontbreekt, toont de route boven de compacte kaarten “Dit document is niet beschikbaar.” en “Terug naar Publicatieoverzicht”. De link opent `/publish`. De melding gebruikt vaste tekst. Ook met een lege documentlijst blijft de melding zichtbaar. Bij een selectie die ontbreekt krijgt de melding voorrang op `published=yes`. De geslaagde publicatie gebruikt de bestaande terugkeer naar `/publish?published=yes`.

De afhandeling gebruikt de bestaande uitgeversrol, lijstlezing en compacte kaarten. Gereedheidsbeoordeling blijft beperkt tot de geselecteerde kaart die aanwezig is. De schrijfacties voor publiceren en intrekken behouden de bestaande domeinregels.
