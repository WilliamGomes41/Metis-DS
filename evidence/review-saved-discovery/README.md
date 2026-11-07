# Opgeslagen kennisobject terugvinden — #1008

Class B; Rewrite risk: none. Lokale synthetische PostgreSQL/Chromium-proef op de patch boven broncommit `c4db3bd84bfe722ab235eff67d2ccf69b60a785b`; geen productiegegevens of Azure-uitvoering.

## Aangetoond

- De oorspronkelijke drie HTTP-tegenvoorbeelden faalden: inventarislink ontbreekt naast open werk; bon heeft geen objectlink; afgehandelde KO-titel opent alleen de bron.
- De gerichte native/HTTP-/architectuurcontroles en werkelijke browserproef worden op de definitieve patch uitgevoerd. Python3.13.5, PostgreSQL17.11, Chromium met Playwright1.58.2. De eerste volledige set van33controles slaagde in42,72s; daarna is een aanvullende toegangscontrole voor de leesweergave toegevoegd.
- Werkelijke opslag → bon → object lezen; overzicht → alle passages → opgeslagen KO lezen. Ook met ander open werk blijft de inventaris bereikbaar.
- De leesweergave toont huidige inhoud, versie, afgeleide status, broncontext en actuele geregistreerde N/A; zij bevat geen beoordelingsformulier. Historische bon en huidige objectversie blijven onderscheiden.
- Na een echte correctie opent de oude bonlink de nieuwe huidige versie; het oude akkoord en de oude N/A worden daar niet overgenomen. De historische bon blijft intact, ook na herstart.
- Gelijktijdige GETs van werkoverzicht en leesweergave wijzigen geen fysieke object-/bindingsrijen, documenttoestand of review-events. De bestaande autorisatieproeven blijven groen.
- De browserproef bedient de bonlink via het toetsenbord. De bon is op375/768/1024/1440px gecontroleerd; leesweergave en werkoverzicht op375/1440px. Geen horizontale overflow. Mobiele leesweergave en desktopwerkoverzicht zijn visueel geïnspecteerd.

## Beelden van de werkende testconsole

- [Bon op mobiel met objectlink](ko4-na-receipt-375.png)
- [Kennisobject lezen op mobiel](ko4-saved-object-375.png)
- [Kennisobject lezen op desktop](ko4-saved-object-1440.png)
- [Werkoverzicht op mobiel](ko4-saved-workboard-375.png)
- [Werkoverzicht op desktop met permanente inventarislink](ko4-saved-workboard-1440.png)

## Grenzen

De testfixture vervangt model/Blob-transport; de HTTP-handler, PostgreSQL-opslag en browser zijn echt. Dit is geen productieacceptatie of prestatietoets. De wijziging voegt geen SQL/store/status of nieuwe review-/publicatiebevoegdheid toe. Volledige CI en automatische review worden op de uiteindelijke PR-head apart beoordeeld. Geen merge of deployment uitgevoerd.

Impeccable-contextloader was niet beschikbaar; de gepinde instructies, bestaande huisstijl en reviewkaart-/bonarchitectuur zijn rechtstreeks gelezen en toegepast. Geen detectorclaim.
