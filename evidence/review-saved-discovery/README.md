# Opgeslagen kennisobject terugvinden — #1008

Class B; Rewrite risk: none. Lokale synthetische PostgreSQL/Chromium-proef op de patch boven broncommit `c4db3bd84bfe722ab235eff67d2ccf69b60a785b`; geen productiegegevens of Azure-uitvoering.

## Aangetoond

- De oorspronkelijke drie HTTP-tegenvoorbeelden faalden: inventarislink ontbreekt naast open werk; bon heeft geen objectlink; afgehandelde KO-titel opent alleen de bron.
- De definitieve lokale set slaagt met **39 uitgevoerde controles in48,14s, geen skips**:38native/HTTP-/architectuurcontroles en1werkelijke browserproef. Python3.13.5, PostgreSQL17.11, Chromium met Playwright1.58.2.
- Werkelijke opslag → bon → object lezen; overzicht → alle passages → opgeslagen KO lezen. Ook met ander open werk blijft de inventaris bereikbaar.
- Een reeds opgeslagen eerste akkoord dat op een andere reviewer wacht opende oorspronkelijk opnieuw de tweede-reviewkaart. Dat HTTP-tegenvoorbeeld faalde op e1d45df3. De inventaris opent voor deze actor nu ook de leesweergave met toestand Tweede review; de bevoegde tweede reviewer behoudt zijn eigen echte beoordelingsformulier. Alle10gerichte ontdekking/toegang/publicatiegevallen slagen (11,83s).
- De leesweergave toont huidige inhoud, versie, afgeleide status, broncontext en actuele geregistreerde N/A; zij bevat geen beoordelingsformulier. Historische bon en huidige objectversie blijven onderscheiden.
- Na een echte correctie opent de oude bonlink de nieuwe huidige versie; het oude akkoord en de oude N/A worden daar niet overgenomen. De historische bon blijft intact, ook na herstart.
- Gelijktijdige GETs van werkoverzicht en leesweergave wijzigen geen fysieke object-/bindingsrijen, documenttoestand of review-events. De bestaande autorisatieproeven blijven groen.
- Aanvullende automatische review vond een onvolledige publicatiestatus. Werkelijke HTTP-tegenvoorbeelden na publicatie en intrekking faalden op9d7. De reparatie hergebruikt de bestaande canonieke lezer voor één exacte tuple en KO-3-statusafleiding. Alle9gerichte ontdekkings-/toegangs-/publicatiegevallen slagen (9,35s), inclusief vervangen en een andere canonieke tuple die de huidige goedkeuring niet als gepubliceerd mag tonen. Workflow én canonical tabellen blijven door bekijken ongewijzigd.
- De browserproef bedient de bonlink via het toetsenbord. De bon is op375/768/1024/1440px gecontroleerd; leesweergave en werkoverzicht op375/1440px. Geen horizontale overflow. Mobiele leesweergave en desktopwerkoverzicht zijn visueel geïnspecteerd.

## Beelden van de werkende testconsole

- [Bon op mobiel met objectlink](ko4-na-receipt-375.png)
- [Kennisobject lezen op mobiel](ko4-saved-object-375.png)
- [Kennisobject lezen op desktop](ko4-saved-object-1440.png)
- [Werkoverzicht op mobiel](ko4-saved-workboard-375.png)
- [Werkoverzicht op desktop met permanente inventarislink](ko4-saved-workboard-1440.png)

## Grenzen

De testfixture vervangt model/Blob-transport; de HTTP-handler, PostgreSQL-opslag en browser zijn echt. Dit is geen productieacceptatie of prestatietoets. De leesweergave voegt één begrensde aanroep van de bestaande publicatiemetadatalezer toe; geen nieuwe SQL/store/status of review-/publicatiebevoegdheid. Gepubliceerd/ingetrokken gebruiken de werkelijke consolecommands; het supersession-tegenvoorbeeld activeert een nieuwere versie via de werkelijke canonical store. Een eerste supersession-fixture met een oudere tijd werd terecht geweigerd en is gecorrigeerd naar de oorspronkelijke releasetijd plus1seconde. Volledige CI en automatische review worden op de uiteindelijke PR-head apart beoordeeld. Geen merge of deployment uitgevoerd.

Impeccable-contextloader was niet beschikbaar; de gepinde instructies, bestaande huisstijl en reviewkaart-/bonarchitectuur zijn rechtstreeks gelezen en toegepast. Geen detectorclaim.
