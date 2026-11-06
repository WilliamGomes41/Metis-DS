# Reviewkaart en bon: beoordelen met context, daarna zien wat is vastgelegd

Status: door William goedgekeurd interactieontwerp, vastgelegd op 6 november 2026.
Implementatiestatus: ontwerpafspraken; deze documentatie implementeert KO-2 niet.
Eigenaar uitvoering: [#995 / MET-56](https://github.com/WilliamGomes41/Metis-DS/issues/995), KO-2 voor presentatie en bestaande vervolgnavigatie; KO-4 voor centrale transitiewachters.
Productacceptatie: [#990 / MET-53](https://github.com/WilliamGomes41/Metis-DS/issues/990), met de bestaande reviewerproef uit #863 / MET-46.

Deze vastlegging hoort bij het [KO-programma](../plans/ko-statechart-program.md).
Zij werkt de goedgekeurde kaart en bon uit en vervangt de eerdere uitleg waarin
het bonnetje vóór akkoord werd geplaatst. Voor de timing, inhoud en interactie
van kaart en bon is dit document de gedetailleerde ontwerpafspraak. Het
KO-programma blijft eigenaar van volgorde, gates en implementatieslices;
protocol, domeincontracten en bestaande autorisatie blijven leidend.

## 1. Besluit en afbakening

De volgorde is:

**Duidelijke reviewkaart → beoordelen en opslaan → bon van het opgeslagen resultaat.**

De reviewer beoordeelt op de kaart. Daarna maakt de bon zichtbaar wat die
persoon heeft gedaan en hoe de onderdelen van het kennisobject in de kernel
samenhangen. De bon is een afgeleide weergave, geen nieuwe domeinautoriteit.

William heeft eerst de kaart en bon mooi en beter dan de eerdere situatie
bevonden. Bij de kaart bleek vervolgens informatie voor vraag 2 en 3 te
ontbreken. De aangepaste kaart met documentcontext én de eerdere bon zijn op
6 november 2026 geaccepteerd met de opdracht deze afspraken gedetailleerd in
de architectuur vast te leggen.

De goedgekeurde composities zijn bewaard:

- [Reviewkaart met geopende documentcontext](../design/review-card-receipt/review-card.png).
- [Bon met zichtbare samenhang na opslag](../design/review-card-receipt/receipt.png).
- [Herkomst en hashes van de mock-ups](../design/review-card-receipt/provenance.json).

Dit zijn mock-ups met fictieve inhoud. Teksten, bronnummering, versies en
personen in de beelden zijn geen bestaande richtlijn, productiedata of
bewijs dat KO-2 al werkt. De functionele afspraken hieronder zijn leidend
bij een verschil met een afbeeldingsdetail.

Deze documentatiewijziging is Class C, Rewrite risk: none: zij legt het
goedgekeurde ontwerp vast zonder runtime-, schema- of lifecyclewijziging.
De toekomstige implementatie behoudt de bestaande classificatie per slice;
deze vastlegging verlaagt het Class A-risico van KO-4 niet.

## 2. Wat de reviewer moet kunnen vaststellen

| Hoofdvraag | Informatie die beschikbaar moet zijn | Wat de interface niet beweert |
| --- | --- | --- |
| Is dit toepasbaar? | Claim, doelgroep/scope, voorwaarden, uitzonderingen en relevante onderbouwing, vergelijkbaar met de bron. | Een modelvoorstel is nog geen menselijke inhoudelijke bevestiging. |
| Is dit compleet? | Geselecteerde passage, alinea ervoor en erna, uitbreidbaar naar de hele sectie; alle bekende betekenisdragende context en gekoppelde onderbouwing met hun tekst en herkomst. | Eén uitgelicht fragment bewijst geen volledigheid van de hele bron. |
| Staat dit op de juiste plek? | Volledige koppenhiërarchie, gemarkeerde huidige plek en naburige passages onder die kop. | Een kruimelpad of voorgestelde kopnaam alleen bewijst geen juiste plaatsing. |

De drie vragen zijn de hoofdstructuur van de beoordeling. Er komen geen
extra bevestigingsvragen, verplichte boncontrole of automatisch verplicht
tweede paar ogen bij. Bestaande vereisten rond type, sterkte, broncontext,
relaties, rollen en four-eyes verdwijnen evenmin stilzwijgend. Hun projectie
in deze kaart gebruikt één gedeelde, pure projectie van de werkelijk getoonde
interpretatie. Drie expliciete Ja-antwoorden bevestigen uitsluitend de
getoonde, bekende waarden via de bestaande kernelopdracht. Onbekende semantiek
of onoplosbare voorstellen blokkeren goedkeuren en verwijzen naar gerichte
correctie; ontbrekende waarden krijgen geen stilzwijgende standaard.

De drie daadwerkelijke antwoorden (`applicable`, `complete`,
`placed_correctly`: `yes`, `adjust` of niet ingevuld) staan als optionele
`review-assessment-v1` in het bestaande, atomair opgeslagen interactiebewijs.
Goedkeuren vereist driemaal `yes`. Dit is menselijk bewijs en geen nieuwe
bindingsautoriteit. De bon leest deze antwoorden van de exacte opgeslagen
handeling; historische events zonder dit bewijs tonen ‘Niet afzonderlijk
vastgelegd’ en krijgen geen afgeleide vinkjes.

## 3. Reviewkaart vóór opslag

### 3.1 Kop en navigatie

De kop toont Review, het document-/sectiepad, de voortgang binnen de actuele
werklijst en de afgeleide toestand van het betrokken kennisobject. Een
kruimelpad biedt navigatie; het vervangt de documentcontext niet.

Metadata blijft compact. De kaart toont geen opgeslagen akkoord voordat de
reviewer een geldige handeling heeft opgeslagen. Radioantwoorden starten
zonder selectie. De eerdere mock-up met reeds geselecteerde Ja-antwoorden
was een voorbeeld van ingevulde invoer, geen ontwerpbesluit voor defaults.

### 3.2 Twee vergelijkbare werkvlakken

Op desktop staan documentcontext links en het kennisobject met beoordeling
rechts, zoals in de goedgekeurde mock-up. De reviewer kan bron en voorstel
vergelijken zonder tussen losse processen of pagina's te wisselen.

De voorgestelde claim staat prominent, met de bijbehorende context direct
zichtbaar. De documentcontext is uitklapbaar en staat in de goedgekeurde
desktopcompositie open. Inklappen is een weergavehandeling en schrijft niets.

Bij een smal scherm staan dezelfde onderdelen onder elkaar. Geen belangrijke
inhoud wordt door een andere viewport weggelaten; een inhoudelijke selectie
mag niet door responsive styling veranderen.

### 3.3 Te beoordelen kennisobject

De kaart toont minimaal de volgende gegevens voor zover het bestaande
kennisobjectcontract ze kent:

| Onderdeel | Weergave |
| --- | --- |
| Claim | De exacte te beoordelen claimtekst en het bestaande of voorgestelde type, met een helder onderscheid als het type nog niet is bevestigd. |
| Doelgroep/scope | De brongebonden doelgroep en relevante afbakening. Een ontbrekende doelgroep wordt niet uit algemene modelkennis ingevuld. |
| Voorwaarden | De omstandigheden waaronder de claim geldt, met de betekenisdragende tekst direct leesbaar. |
| Uitzonderingen | Wanneer de claim anders of niet geldt. Een opdracht die bij de uitzondering hoort, zoals een keuze vastleggen, blijft zichtbaar. |
| Onderbouwing en overwegingen | De bestaande gekoppelde onderbouwing, met tekst en een verwijzing naar het betreffende bronbewijs. Een relatie-ID alleen is onvoldoende. |
| Herkomst | De exacte bronplek en de mogelijkheid de oorspronkelijke bron te openen. |

Meerdere voorwaarden, uitzonderingen of onderbouwingen worden niet stil tot
één rij teruggebracht. Extra informatie kan worden uitgeklapt; de aanwezigheid
en aantallen blijven herkenbaar en betekenisdragende tekst mag niet afgekapt
worden alsof ze volledig is.

Een leeg veld wordt niet automatisch 'niet van toepassing'. Maak onderscheid
tussen ontbrekend, onzeker, niet gekoppeld en een expliciet vastgelegde
niet-van-toepassingkeuze. De UI verzint geen zekerheidsscore of groene
betrouwbaarheidsstempel. De bestaande kernel bepaalt toelating en blokkades.

De nieuwe kaart is geen opdracht om voorwaarden of uitzonderingen naar een
nieuwe opslagvorm te migreren. Of zulke informatie een brongebonden veld of
een gekoppeld object is, volgt het geldende contract. De presentatie maakt
de betekenis en samenhang leesbaar zonder die nog open domeinkeuze in te
vullen; zie #986 en de betreffende broncontextcontracten.

### 3.4 Bekijk in documentcontext

Dit onderdeel bevat drie samenhangende weergaven:

1. **Plek in het document.** De volledige koppenhiërarchie van de vastgelegde
   bronrepresentatie, met de huidige sectie gemarkeerd. De hiërarchie mag
   uitklapbaar zijn; bovenliggende en naburige koppen blijven bereikbaar.
2. **Bronpassage en omliggende tekst.** De geselecteerde passage is gemarkeerd;
   de voorafgaande en volgende alinea zijn zichtbaar met hun volgorde. Via
   Toon hele sectie wordt de broncontext uitgebreid. Open volledige bron
   opent de bestaande oorspronkelijke-bronroute.
3. **Naburige passages onder deze kop.** Leesbare tekst of een herkenbaar
   fragment van de aangrenzende passages; geen lijst met alleen identifiers.
   De actuele passage is herkenbaar en de volgorde komt uit de bron.

Een passage aan het begin of einde van een sectie krijgt geen verzonnen
buuralinea. Koploze, grafische, tabel- of beslisboombronnen gebruiken hun
bestaande bronrepresentatie en bewijsnavigatie. De renderer fabriceert geen
proza-alinea's of lineaire structuur waar de bron die niet bevat.

Context uit een andere sectie blijft bereikbaar wanneer die daadwerkelijk
aan het object is gekoppeld. Alleen 'alinea ervoor en erna' is niet voldoende
als een bekende voorwaarde elders staat. De kaart toont die koppeling met
tekst en herkomst; uitbreiden naar de hele sectie is aanvullend.

De geselecteerde bronplek, omringende bron en koppenboom moeten bij dezelfde
source snapshot horen als de beoordeelde versie. Broncontext openen is een
geautoriseerde leeshandeling. Zij start geen modelrun, herextractie, backfill,
nieuwe beoordeling of documentbrede publicatiecontrole.

### 3.5 Antwoorden en acties

De hoofdvragen zijn exact:

- Is dit toepasbaar?
- Is dit compleet?
- Staat dit op de juiste plek?

De voorbeeldantwoorden Ja en Aanpassen maken de keuze begrijpelijk.
Ja wordt niet voorgeselecteerd. Andere plek kiezen biedt de bestaande
plaatsings-/correctieroute; het aanklikken van een andere kop is niet zelf
een opgeslagen inhoudelijk besluit.

Goedkeuren en opslaan gebruikt de bestaande geautoriseerde reviewopdracht.
Correctie nodig gaat naar de bestaande brongebonden correctie- of
herstelroute. Later beoordelen behoudt het bestaande uitstelcontract.
Afwijzen blijft via de bestaande beslisroute beschikbaar; de beperkte
positieve voorbeeldmock-up is geen besluit om afwijzing te verwijderen.

De geldige combinaties van geschiktheid en besluit komen uit de kernel en
uiteindelijk de KO-4-transitietabel. De UI krijgt geen tweede beslisregel.
Verborgen of vervallen vragen mogen geen achtergebleven antwoorden laten
meeschrijven. Bestaande autorisatie, bronintegriteit, stale checks en
verplichte toelichtingen blijven gehandhaafd.

## 4. Bon ná succesvolle opslag

### 4.1 Functie en moment

De bon beantwoordt twee vragen:

1. Wat heb ik daadwerkelijk gedaan en wat is opgeslagen?
2. Hoe hangen de onderdelen van dit kennisobject nu samen in de kernel?

De bon verschijnt pas na de bevestigde duurzame opslag van de betrokken
handeling. Alleen verzonden formulierwaarden, HTTP 200 of het openen van een
herstelpagina bewijzen geen opgeslagen reviewbesluit.

De bon hoort bij de bestaande vervolgnavigatie. Geen extra formulier,
akkoordknop, bevestigingsklik of verplichte controle van het bonnetje. De
reviewer kan verder naar de volgende passage of terug naar het overzicht.
De bon is een eigen, nieuw vormgegeven pagina na de bestaande POST → 303 →
GET. De volgende reviewkaart staat daar niet onder. De knop Volgende passage
opent de bestaande vervolgbestemming zonder bonparameters. Er komt geen
extra akkoord of formulier bij: de bon bevestigt uitsluitend de al opgeslagen
handeling.

### 4.2 Kop en opgeslagen handeling

Gebruik Review opgeslagen als de review daadwerkelijk is opgeslagen. Het
bijschrift past bij de uitkomst: Dit heb je goedgekeurd alleen bij een
opgeslagen goedkeuring; bij correctie, afwijzing of uitstel benoemt het
overzicht die werkelijke handeling. Een correctie kan een nieuwe versie ter
review opleveren en mag dan niet als goedkeuring worden voorgesteld.

Toon de afgeleide objecttoestand, de exacte betrokken objectversie en de
werkelijke publicatiestatus. Gebruik geen fictief versienummer uit de
mock-up en verhoog de inhoudsversie niet om een bon te maken. Een
governance-onlybesluit kan dezelfde canonieke objectversie behouden.

De status betreft het kennisobject, niet automatisch het hele document.
De metadataregel in de fictieve afbeelding mag niet worden geïmplementeerd
als een documentbreed akkoord. Een bronlabel noemt het document; een
reviewstatus hoort bij het object en de geldende reviewverplichtingen.

### 4.3 Zo is het kennisobject vastgelegd

Dit is het belangrijkste deel van de bon. Een algemene succesmelding of
alleen drie vinkjes voldoet niet.

Een centraal claimblok toont de exact opgeslagen claim met type. Vanuit dit
blok zijn de relaties naar de bijbehorende onderdelen visueel te volgen:

| Verbinding | Wat de reviewer kan lezen |
| --- | --- |
| Geldt wanneer | De opgeslagen voorwaarden en afbakening voor deze claim. |
| Tenzij | De opgeslagen uitzonderingen, inclusief betekenisdragende gevolgen of acties. |
| Onderbouwd door | De daadwerkelijk gekoppelde onderbouwing en overwegingen. |
| Herkomst | De bronverwijzing(en) waaruit claim en gekoppelde onderdelen afkomstig zijn. |

De doelgroep blijft terugvindbaar bij de claim/context. Bij meerdere
verbindingen toont de bon alle relevante onderdelen, eventueel met
uitklappen voor omvang. De rustige voorbeeldcompositie met drie takken is
geen beperking op aantallen of relatietypen.

Gebruik leesbare Nederlandse verbindingslabels en inhoudelijke tekst.
Pijlen mogen geen tekst kruisen en de richting moet ondubbelzinnig zijn.
Kleur alleen draagt geen betekenis. Op mobiel kan dezelfde samenhang als
hiërarchische lijst met expliciete verbindingslabels worden weergegeven.

De weergave is een afgeleide projectie van de bestaande kennis- en
bronrelaties, geen nieuwe graaf, database of pakketopslag. Geen koppeling
wordt toegevoegd alleen om het diagram te vullen. Ontbrekende, onzekere of
niet-van-toepassinginformatie wordt overeenkomstig de opgeslagen gegevens
benoemd. Als onderdelen verschillende bronplekken hebben, blijven hun
eigen verwijzingen zichtbaar; een gedeelde bronstrook is geen reden om
herkomst samen te voegen.

### 4.4 Jouw beoordeling en vervolg

Een compacte samenvatting toont de daadwerkelijk vastgelegde antwoorden
en het besluit, voor zover het bestaande reviewbewijs die bevat. Een vinkje
wordt niet uit een andere reviewer, ontbrekende invoer of alleen een
toegestane status afgeleid. De samenvatting ondersteunt de samenhangweergave
en mag deze niet vervangen.

De bon vermeldt bij welke opgeslagen versie het overzicht hoort. Hetzelfde
overzicht kan via de bestaande geautoriseerde leesroutes opnieuw bekeken
worden als het opgeslagen bewijs daarvoor beschikbaar is. Dit ontwerp
introduceert geen aparte historiepagina of nieuwe bewaarautoriteit.

Bij een vereiste tweede review toont de eerste bon dat het eigen akkoord
is opgeslagen en de tweede beoordeling nog openstaat. Wanneer één reviewer
volgens het bestaande beleid voldoende is, wordt geen tweede reviewer
gevraagd. De bon wijzigt reviewconfiguratie of risicoregels niet.

Goedkeuring is geen publicatie. Nog niet gepubliceerd wordt alleen getoond
als dat werkelijk de registry-uitkomst is. Publicatie per object en het
bijbehorende Class A-contract blijven bij #991 / MET-54.

## 5. Opslag, identiteit en contextbehoud

| Grens | Contract |
| --- | --- |
| Reviewopdracht | Bestaande geautoriseerde command-/store-grens blijft eigenaar van validatie en mutatie. |
| Atomiciteit | Objectwijziging, reviewbinding, audit en vereiste afleidingen behouden hun bestaande gezamenlijke commit/rollback. |
| Reviewbewijs | Bestaande actuele bindingen en versie-/hashgebonden bewijs blijven autoriteit; de bon schept geen akkoord. |
| Bron | Bestaande immutable source snapshot en opgeslagen bronrepresentatie blijven autoriteit. |
| Bon | Afgeleid uit de exacte duurzaam opgeslagen handeling, objectidentiteit/versie, bindingen en relaties. Geen eigen persisted status of success-authority. |
| Serving | Alleen het publicatieregister bepaalt wat uitgegeven wordt. |

De implementatie moet de context van de opgeslagen handeling behouden over
POST, redirect en daaropvolgende GET: source snapshot, objectidentiteit,
betrokken versie/hash en bestaande command-/interaction- of bewijskoppeling
voor zover die route die kent. Een objectversie alleen onderscheidt twee
reviewers of twee governancebesluiten niet altijd.

Herbruik de aanwezige commandresultaten en bewijsreferenties. Voeg geen
algemene tokenlaag, receipt-store of tweede eventlog toe. Leg bij het
geraakte entrypoint vast welke bestaande referentie de handeling identificeert.
Als de huidige resultaatsgrens dat niet betrouwbaar kan uitdrukken, is dit
een implementatiebevinding om expliciet te behandelen; toon niet alsnog een
bon op basis van 'meest recente object'.

Een latere wijziging mag niet stil als resultaat van de eerdere handeling
worden getoond. Toon het historische opgeslagen resultaat met de betreffende
versie en zo nodig de melding dat er inmiddels een nieuwere versie bestaat.
Kan de oorspronkelijke handeling niet met bestaand bewijs worden opgelost,
dan is de uitkomst niet bevestigd en verschijnt geen succesvolle bon.

Navigatie-/weergaveparameters verlenen geen toegang. Controleer rol,
documentdeelname, accountstatus en bron-/objectscope op de bestaande
geautoriseerde grenzen. Een verwijzing naar een ander object, document of
reviewer mag niet een andere bon openen of als het eigen resultaat gelden.

## 6. Fout- en herstelgedrag

| Situatie | Wat zichtbaar is | Wat niet gebeurt |
| --- | --- | --- |
| Vereiste informatie of geldige keuze ontbreekt | Gerichte melding bij de kaart; bestaande invoer blijft volgens het huidige draftcontract beschikbaar. | Geen opgeslagen-akkoordmelding of succesvolle bon. |
| Een ander wijzigde relevante invoer | Bestaande conflictrespons en actuele context; opnieuw beoordelen waar nodig. | Geen stille overschrijving of bon voor de geweigerde actie. |
| Geen bevoegdheid, ingetrokken deelname of gepubliceerde immutable versie | Bestaande weigering, zonder verboden mutatie. | De bon omzeilt geen rol-, bron- of publicatiegrens. |
| Fout vóór of tijdens commit | Bestaande rollback en foutpresentatie. | Geen half opgeslagen besluit of succesvolle bon. |
| Commit slaagt, antwoord gaat verloren | Uitkomst eerst vaststellen met de exacte bestaande command-/interaction- en opslagbewijzen. | Geen automatische herhaling, geen verzonnen rollback, geen tweede goedkeuring. |
| Opgeslagen resultaat teruggevonden | Bon van precies dat resultaat. | Geen nieuw besluit om de bon opnieuw te tonen. |
| Uitkomst niet vast te stellen | Benoem dat opslag niet bevestigd is; gebruik de bestaande herstelroute. | Een leeg eventvenster geldt niet als bewijs van rollback. |
| Herstart | Opgeslagen besluit blijft zichtbaar via bestaande duurzame autoriteiten. | Succes hangt niet af van alleen browser- of procesgeheugen. |
| Context laden mislukt | Expliciete fout of ontbrekende-contextmelding met passende bestaande vervolgactie. | Lege context wordt niet als 'geen context nodig' gepresenteerd. |

## 7. Aansluiting op de bestaande architectuur

Navigatiekaart, geen nieuwe eigenaren:

- `src/operations_console_app.py::_render_review_card`: bestaande kaart en
  HTTP-ingang; volg de gedelegeerde response-/navigatieowner per route.
- `src/review/review_cockpit_v1.py`: bestaande inhoudelijke kaartprojectie.
- `src/review/review_workboard_v1.py`: werkbord en afgeleide toestanden.
- `src/review/knowledge_object_state_v1.py`: KO-1-afleiding, zonder schrijven.
- `src/review/review_passage_read_v1.py`, bestaande source-/revision-readers:
  coherente actuele passage-invoer en geverifieerde broncontext.
- `src/review/review_command_v1.py`, bestaande command response en workflow
  stores: commandcontext, conflict, atomiciteit en vervolgnavigatie.
- `src/review/closed_review_loop_v1.py` en
  `src/review/deterministic_review_repair_v1.py`: bestaande beslissing en
  brongebonden herstelroute, aansluitend op KO-4.
- `src/review/ko_receipt_ui_v1.py`: geplande renderer uit KO-2; uitsluitend
  presentatie van door bestaande readers opgeloste opgeslagen resultaten.
- `src/integrity_kernel.py`, reviewbindings en publication registry:
  bestaande identiteit, review- en servingautoriteit.

Traceer vóór implementatie echte callers, MRO-overrides, normale en
compacte routes en de PostgreSQL-composities. Bestandsnamen alleen bewijzen
niet dat alle entrypoints dezelfde grens gebruiken. De huidige kaart met
vele losse vragen wordt niet als bijwerking van deze documentatie aangepast.

## 8. Leesgrenzen en prestaties

Meer zichtbare context is geen vrijbrief om bij iedere kaart alle
objecthistorie, alle processingarchieven of de volledige envelope te laden.
Gebruik het bestaande passage-/dependencyvenster en voorbereide
bronrepresentatie. Koppenboom en buurpassages komen uit dezelfde
source snapshot; aanvullende sectie-inhoud wordt begrensd bij de bestaande
read-owner opgehaald wanneer zij wordt geopend.

Een geselecteerd venster is geen volledige documentclosure. Voor een
noodzakelijke inhoudelijke koppeling mag context niet worden afgekapt om
een budget te halen. Overgrootte, ontbrekend bewijs of onbeschikbaarheid
krijgt de bestaande expliciete uitkomst in plaats van een misleidend leeg
scherm. GET doet geen backfill of stille reparatie.

Meet afzonderlijk kaart openen, documentcontext uitbreiden en de volledige
handeling opslaan → zelfstandige bon → volgende passage → heropenen.
Reken redirect en bonrender mee; verplaats wachttijd niet naar een volgende
pagina. De bestaande KO-2-budgets en MET-36/MET-48-metingen blijven gelden.
Synthetische of lokale metingen zijn geen gemeten Azure-SLO.

## 9. Vormgeving, toegankelijkheid en inhoud

Behoud de Metis-vormgeving uit de goedgekeurde beelden: witte werkruimte,
lichte waterkleur voor broncontext, paarse acties, rustige cyan scheidingen,
leesbare donkere tekst en consistente native formulierbediening. Gebruik
de bestaande brandtokens en toegestane fonts.

De documentcontext gebruikt een bedienbaar disclosure met zichtbare
open/dicht-toestand. Koppen en huidige plek zijn ook zonder kleur herkenbaar.
De drie vragen hebben geassocieerde labels, geen voorselectie en zichtbare
toetsenbordfocus. Benodigde bron- en relatie-informatie is zonder hover te
lezen. Een diagram krijgt een gelijkwaardige tekstuele volgorde met
verbindingslabels. Zonder JavaScript blijven beoordeling, broncontext en
de bon na een geslaagde serverhandeling bereikbaar.

Mobiel stapelt de broncontext, het kennisobject en de vragen. Lange claims,
meerdere relaties en koppen mogen geen horizontale scroll vereisen. De bon
is begrijpelijk voor iemand die de technische term kernel niet kent.

Geen betrouwbaarheidsscore, certificaat, extra vierogenverplichting,
auditkamer of nieuw modelgesprek toevoegen. Het beoogde vertrouwen komt
uit begrijpelijke broninformatie, herkenbare samenhang en een controleerbaar
opgeslagen besluit, niet uit een extra laag controles.

## 10. Implementatieverdeling en resterende besluiten

| Onderdeel | Bestaande owner / grens |
| --- | --- |
| Afgeleide toestand | KO-1, geleverd via #996; geen nieuwe opgeslagen status. |
| Kaart, documentcontext, bon en aansluiting bestaande vervolgnavigatie | KO-2 binnen #995. |
| Drie vragen als centrale wachters, geldige transities | KO-4; autorisatie/atomiciteit blijven bij #952 / MET-43. |
| Eén bronrolschrijver | #942 / MET-35; het broncontextdeel van KO-4 sluit hierop aan. |
| Inhoudelijke maatstaf en representatie van voorwaarden/uitzonderingen | #986 / MET-49; dit ontwerp kiest geen nieuwe opslagvorm. |
| Objectgereedheid en afgeleid pakket | KO-3; geen publicatieactie. |
| Publicatieactie per object | #991 / MET-54. |
| Productacceptatie kaart en bon | #990 / MET-53, met bestaande reviewerproef #863 / MET-46. |
| Incidentherstel en historische opslaguitkomsten | #974 / MET-48; dit ontwerp bewijst geen productieherstel. |

De reeds goedgekeurde layout en timing hoeven niet opnieuw als open
productvraag te worden behandeld. Nog te bepalen inhoudelijke criteria
worden bij #986 expliciet gesloten. Het mock-upvoorbeeld mag niet als
klinische referentie of inhoudelijke acceptatiemeting worden gebruikt.

Deze opdracht autoriseert de vastlegging en reviewbare documentatie-PR.
Zij voert geen KO-2/KO-4-productcode, merge, deployment, datamigratie of
productiereview uit. Bestaande uitvoeringsafspraken blijven van kracht.

## 11. Acceptatiematrix voor de implementatie

De onderstaande checks zijn vereisten voor toekomstige uitvoering; een vakje
is niet automatisch bewezen doordat dit document of een afbeelding bestaat.

| ID | Scenario | Vereist observeerbaar resultaat |
| --- | --- | --- |
| RC-01 | Open een nog niet beoordeelde passage. | Duidelijke kaart, afgeleide toestand, geen bon en geen vooraf gekozen antwoorden. |
| RC-02 | Beoordeel toepasbaarheid. | Claim, doelgroep, voorwaarden, uitzonderingen en bekende relevante context zijn leesbaar naast de bron. |
| RC-03 | Controleer volledigheid. | Bronpassage met alinea ervoor/erna; hele sectie en oorspronkelijke bron bereikbaar zonder besluit te wijzigen. |
| RC-04 | Controleer plaatsing. | Volledige bereikbare koppenstructuur met huidige plek en naburige passages uit dezelfde source snapshot. |
| RC-05 | Context is elders, meervoudig, onzeker of ontbreekt. | Bekende koppelingen zijn zichtbaar met hun tekst/herkomst; ontbrekend wordt niet niet-van-toepassing en niets wordt verzonnen. |
| RC-06 | Verplaatsings-/correctiekeuze of afwijzing. | Bestaande geldige beslis- en herstelroute, geen nieuwe approve-default en geen verwijderde afwijsmogelijkheid. |
| RC-07 | Sla een geldige goedkeuring op. | Zelfde geautoriseerde kernelbesluit/binding als de bestaande route; daarna bon van precies dat opgeslagen resultaat. |
| RC-08 | Bekijk de bon. | Claim met zichtbare, gelabelde verbindingen naar voorwaarden, uitzonderingen, onderbouwing en juiste bronverwijzingen; vinkjes alleen voldoen niet. |
| RC-09 | Ga verder. | Bestaande volgende passage of overzicht, zonder extra formulier, akkoord of verplichte bonbevestiging. |
| RC-10 | Ongeldige keuze, onvoldoende rechten of stale input. | Bestaande weigering/conflict, behouden invoer waar het contract dat voorschrijft, geen verboden mutatie en geen succesvolle bon. |
| RC-11 | Fout bij write/audit/commit. | Bestaande atomaire rollback; geen gedeeltelijk besluit en geen succesvolle bon. |
| RC-12 | Commit geslaagd, response verloren. | Exact opgeslagen resultaat kan via bestaand bewijs worden herkend; geen blinde herhaling of afleiding uit alleen een eventvenster. |
| RC-13 | Een andere handeling of versie volgt vóór de bon-GET. | De bon blijft aan de oorspronkelijke opgeslagen handeling gebonden; geen andere versie, reviewer of object als het eigen resultaat. |
| RC-14 | Herstart en opnieuw lezen. | Hetzelfde duurzame besluit en dezelfde inhoudelijke samenhang zijn terug te vinden. |
| RC-15 | Eén reviewer volstaat volgens beleid. | Geen extra tweede-reviewverplichting door kaart of bon. |
| RC-16 | Bestaand beleid vereist onafhankelijke tweede review. | Eerste bon bevestigt alleen het eigen akkoord en toont resterende verplichting; tweede akkoord betreft dezelfde geldige versie. |
| RC-17 | Opgeslagen correctie, afwijzing of uitstel. | Overzicht benoemt de werkelijk opgeslagen handeling; correctie of uitstel heet niet goedgekeurd. |
| RC-18 | Nog niet gepubliceerd object. | Reviewakkoord verleent geen serving/publicatierecht; status komt van bestaande autoriteit. |
| RC-19 | Desktop, mobiel, toetsenbord en zonder JS. | Alle benodigde inhoud en acties bereikbaar; tekstalternatief voor relaties; geen verplichte extra klik om akkoord te bevestigen. |
| RC-20 | Meet kaart, contextuitbreiding en save/vervolg/readback op dezelfde versie. | Bestaande budgets blijven toetsbaar; bytes en tijd omvatten ook de bon/redirect, met meetomgeving expliciet. |
| RC-21 | Echte reviewer doorloopt de goedgekeurde compositie. | Reviewer kan uit bron/context het besluit onderbouwen en na opslag uitleggen wat is vastgelegd en hoe de onderdelen samenhangen; vastgelegd bij #990/#863. |

De bestaande automatische regressies en gebruikersproef worden voor deze
criteria hergebruikt. Er wordt geen afzonderlijk acceptatieprogramma of
nieuw proces voor de reviewer toegevoegd. Lokale tests, browserproeven,
deployment en productieacceptatie blijven afzonderlijke bewijssoorten.
