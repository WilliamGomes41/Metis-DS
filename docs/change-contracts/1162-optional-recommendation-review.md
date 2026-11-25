# Stap 3 · Optionele bevestiging van richting en sterkte

Change class: A. Rewrite risk: none. Part of MET-145. Refs #1159 and #1162.

Besluit projectlead, 25 november 2026. De eerste reviewer mag een aanbeveling uit menselijke annotatie goedkeuren en bevestiging van richting en sterkte overslaan. Deze keuze past de eerste review uit [#1067](slice5-reviewer-recommendation-semantics.md) aan.

## Gedrag

| Keuze | Bestaande reviewtransactie |
| --- | --- |
| Accepteren | Bevestigt het getoonde volledige voorstel na controle van de werkrevisie, het voorstel op de exacte objectversie en het bronbewijs. |
| Weigeren | Legt de weigering vast. Richting en sterkte blijven onbevestigd, tenzij de reviewer beide expliciet en met geldig bronbewijs kiest. |
| Overslaan | Legt overslaan vast. Een voorstel blijft onbevestigd. Op een opvolgende versie kan een eerder bevestigde waarde behouden blijven wanneer hetzelfde bewijs nog bindt en de nieuwe versie is beoordeeld. |

De keuze **Niet vermeld** is een eigen bevestiging. Een expliciete bronsterkte sluit die keuze uit. Een halve keuze blijft open. Zonder uitdrukkelijke acceptatie wordt een voorstel nooit als bevestiging opgeslagen.

## Levenscyclus en bewijs

De bevoegde eerste reviewer geeft op een open WorkingRevision het bestaande inhoudelijke akkoord. De PostgreSQL-reviewtransactie legt de exacte versie, reviewbinding en uitkomst in één commit vast. Een verkeerde keuze, verouderd voorstel of oude revisie schrijft niets. De verplichte onafhankelijke tweede review bevestigt de versie van de eerste en beslist niet opnieuw over richting en sterkte. Herstart leest dezelfde objectversie, binding en logboekuitkomst terug.

Bij een correctie maakt de bestaande route een opvolgende versie. De vorige versie en de releasehistorie blijven intact. De opvolger heeft opnieuw review nodig. Bij gewijzigde of ongeldige binding vervalt de eerdere bevestiging op de opvolger. Een review creëert geen release. De afzonderlijke publicatie blijft alle inhoudelijke, technische en toegangsvoorwaarden controleren.

De Product API levert bevestigde semantiek via de bestaande canonieke projectie. Bij een onbevestigde aanbeveling uit annotatie verwijdert de antwoordprojectie een afsluitende expliciete richting-sterkteaanduiding uit de afgeleide tekst. De canonieke bronpassage blijft letterlijk beschikbaar voor broncontrole. Oude bevestigingen, de beslisboom en de reviewroute voor aanbevelingen uit andere producenten volgen hun bestaande contract.

Meet accepteren, weigeren en overslaan met het bestaande reviewlogboek en de bestaande aggregatie, bij eerste goedkeuringen waarbij een bruikbaar voorstel voorlag. Historische gebeurtenissen zonder dit bewijs tellen niet mee.

De native PostgreSQL-proeven in `tests/test_reviewer_recommendation_semantics_1067.py` volgen de aanbeveling van annotatie naar review, audit, herstart en Product API. De Chromium-proef in `tests/browser_human_review_check.cjs` bewijst de bediening op desktop en telefoonbreedte. Voor stap 2 komt het afzonderlijke PDF-labelbewijs uit het bouwplan aan bod.
