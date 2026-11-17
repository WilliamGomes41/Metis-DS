# Blijvende lijst met opgeslagen annotaties

Change class: B
Promise: De medewerker ziet tijdens annoteren welke annotaties door de server zijn opgeslagen, kan deze heropenen en ziet welke stap naar Review nog nodig is.
Proof: Browserproeven met echte HTTP/PostgreSQL-opslag voor volgende kaart, herladen, heropenen, mislukte opslag en bouwstatus; desktop en mobiel.
Touches lifecycle invariants: no
Rewrite risk: none

Opdracht projectlead, 17 november 2026: “Implementeer dat”, na het voorstel voor
een blijvende lijst ‘Opgeslagen annotaties’. Basis: main `17bce9e1`.
Het aanmaken van een extern uitvoeringsticket is door automatische goedkeuringscontrole
geweigerd. Deze expliciete opdracht wordt lokaal uitgevoerd; niets wordt zonder
publicatieautorisatie naar GitHub of Linear geschreven.

## Werking en ontwerp

De bestaande `flush` schrijft via `/annotations/api`; pas het succesvolle antwoord
werkt `state.entries` bij. De lijst projecteert die bevestigde versies, niet de
nog onopgeslagen editorinhoud. Een fout houdt de vorige versie zichtbaar. Een
ingetrokken annotatie en bronverantwoording vormen geen lijstitem.

De lijst staat in het bestaande zijpaneel bij de bron, onder de huidige kaart.
Elke regel bevat een bronexcerpt, afgeleide status en een gewone heropenlink.
De bestaande actie naar documentcontrole wordt hergebruikt. Links bewaren eerst
de actuele wijzigingen; bij een opslagfout blijft de medewerker in de kaart.

Statussen komen uit bestaande annotatiestatus, objectbinding/pending en de laatste
bouwopdracht. Het bouwmodule blijft eigenaar van de bestaande query voor die
opdracht. Alleen bij een lopende bouw wordt de bevestigde lijststatus ververst;
de polling leest het bestaande lichte bouwstatus-endpoint. De volledige bron- en
annotatieset wordt pas opnieuw gelezen wanneer de bouw eindigt.
Dit past nooit de actieve editorversie of CAS-basis aan. Een verouderd antwoord
mag een recentere opslagbevestiging niet overschrijven. Falen van de statusread
laat de laatst bevestigde lijst staan met een zichtbare melding.

Een aparte lijst met eigen persistente status is verworpen: die zou naast de
bestaande owners kunnen afwijken. Een derde hoofdworkflow of automatisch bouwen
na elke opslag is niet nodig. De UI-projectie gebruikt alleen bestaande opslag,
bronidentiteiten, saves, documentcontrole, bouw en Review. Er komen geen migraties,
nieuwe domeinstatussen, kandidaatmakers of gewijzigde review-/publicatieregels.

## Bewijsgrenzen

De proeven tonen bewaren/heropenen aan, inclusief een geweigerde save,
intrekking en actuele bouwstatus. Een gebruikerstoets in productie en deployment
vallen buiten deze implementatie.

## Uitgevoerde verificatie

- 79 gerichte tests geslaagd voor opslag, bouwen, bronweergave, preview,
  materialisatie en architectuurinvarianten (56,54 s).
- Nieuwe volledige browserroute geslaagd op echte HTTP/PostgreSQL-opslag:
  1 passed (22,56 s). Alleen provider-I/O is synthetisch; de bouwuitvoering wordt
  tijdelijk bij de worker vertraagd om de bestaande running-toestand te zien.
- Dezelfde nieuwe browserproef faalt op ongewijzigde main `17bce9e1` doordat
  de opgeslagen lijst ontbreekt (1 failed, 10,96 s), en slaagt met de wijziging.
- Vier bestaande browserroutes geslaagd: bronselectie, annotatiekaart,
  modelvoorstellen/typecorrectie en afsluiten/bouwen/Review (83,92 s).
- Na de lichtere voortgangspolling zijn de nieuwe browserroute en de bestaande
  volledige bouwroute opnieuw geslaagd: 2 passed (36,13 s). De proef controleert
  expliciet dat een lopende statuscontrole de volledige bron niet opnieuw leest.
- Repositorypreflight, release-control op de werkelijke gewijzigde paden,
  architectuurgrenzen, Python-compilatie en JavaScript-syntax geslaagd.
- Desktop 1440 en mobiel 390 px gerenderd en bekeken; geen horizontale overflow.

[Schermbeelden en JUnit](../../evidence/saved-annotations/README.md).
De volledige collectie op implementatiecommit `b8824937` is na één volledige
herhaling van partitie 2 gevalideerd met de canonieke shardmerger: 8.810 geslaagd,
58 overgeslagen, geen fouten of PostgreSQL-skips. De eerste uitvoering had één
timingoverschrijding in een bestaande Review-batchtest (0,351 s > 0,250 s).
Die proef slaagde zowel gericht als binnen de volledige partitieherhaling,
zonder code- of testgrenswijziging. De oorzaak is niet vastgesteld; beide
uitkomsten staan in de verificatiesamenvatting. De latere bewijsaanvulling
wijzigt uitsluitend documentatie en verificatieartefacten, geen code of tests.
