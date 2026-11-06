# #995 / #990 — goedgekeurd ontwerp reviewkaart en bon

Change class: C
Promise: Leg de goedgekeurde kaart met documentcontext en de bon na opslag gedetailleerd en vindbaar vast voor KO-2.
Proof: Architectuurcontract met RC-01–RC-21, onveranderde mock-ups met SHA-256-herkomst en aansluiting op het KO-programma; repository-, link- en architectuurchecks.
Touches lifecycle invariants: no
Rewrite risk: none

## Besluiten (GO projectlead, 6 november 2026)

William: “Nice is en de bon is wat ik wil leg de afspraken heel gedetalieerd vast in de architectuur”. Dit is goedkeuring van het interactieontwerp en opdracht tot vastlegging; geen opdracht om de gehele KO-implementatie, merge of deployment uit te voeren.

De [gedetailleerde architectuurafspraak](../architecture/review-card-receipt.md) is de inhoudelijke uitwerking. Het [KO-programma](../plans/ko-statechart-program.md#show-a-clear-review-card-then-a-receipt-after-a-successful-save-ko-2) is eigenaar van uitvoering, volgorde en gates.

- De kaart komt vooraf; de bon volgt pas na bevestigde duurzame opslag.
- De reviewer ziet de claim en betekenisdragende context naast de bron, met koppenstructuur, omliggende tekst en naburige passages om volledigheid en plaatsing te beoordelen.
- De bon toont het werkelijke besluit en de samenhang tussen claim, voorwaarden, uitzonderingen, onderbouwing en herkomst van precies het opgeslagen resultaat.
- Geen extra formulier, bevestigingsstap of universele verplichting tot twee reviewers. Bestaande domein-, autorisatie-, opslag- en publicatiegrenzen blijven gelden.

## Bewijsgrens en vervolg

De twee geaccepteerde mock-ups zijn ongewijzigd bewaard met herkomst en hashes. Ze bevatten fictieve voorbeeldinhoud. De acceptatiematrix specificeert toekomstige productverificatie en is geen verklaring dat de nieuwe interface al werkt.

Deze wijziging raakt alleen documentatie en ontwerpbeelden. KO-2 bouwt de kaart en bon; KO-4 centraliseert de transitiewachters. Geen productiecontrole of Azure-bewijs wordt hiermee geleverd. Productacceptatie blijft bij #990 / MET-53 en de bestaande reviewerproef.
