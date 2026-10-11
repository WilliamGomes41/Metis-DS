---
name: skill-dispatcher
description: Selecteer en lees de passende beschikbare skills voor analyse, ontwerp, implementatie, verificatie, review en schrijfwerk. Gebruik bij complexe of meerfasige opdrachten, bij twijfel over de juiste skill, bij een gemelde verkeerde skillkeuze en wanneer doel, risico of taakfase verandert. Routeer op het gewenste resultaat en concrete foutgevolgen, niet uitsluitend op trefwoorden.
---

# Skilldispatcher

Kies de kleinste samenhangende set skills die de opdracht dekt. Voer daarna de gevraagde taak uit; blijf niet bij een routeadvies als uitvoering is gevraagd. Behandel deze dispatcher als selectie-instructie, niet als runtimeprogramma, nieuwe autoriteit of toestemming voor externe acties.

## 1. Bepaal de opdracht

Leg kort vast:

- het gewenste resultaat en de grenzen van de opdracht;
- de huidige fase: onderzoeken, ontwerpen, uitvoeren, verifiëren, beoordelen of uitleggen;
- concrete foutgevolgen die de keuze beïnvloeden, zoals verkeerde toegang, verloren werk, onjuiste selectie of misleidende conclusies;
- expliciet gevraagde skills en geldende projectinstructies.

Behandel claims over oorzaak, intentie en opgelost gedrag als hypothesen. Onderzoek ontbrekende feiten gericht. Vraag alleen om informatie als een materiële keuze niet uit de opdracht of beschikbare bronnen volgt.

## 2. Ontdek de actuele skills

Gebruik de actuele skillcatalogus van de sessie of het beschikbare skill-discoverymechanisme. Inspecteer in een repository ook de aanwezige skillmappen en de toepasselijke `AGENTS.md`-instructies. Gebruik een expliciet opgegeven locatie eerst.

Selecteer kandidaten op hun volledige beschrijving. Lees hun actuele `SKILL.md` voordat je ze toepast; lees relevante verwijzingen volgens hun instructies. Namen en onderstaande voorbeelden zijn zoekhulp, geen gesloten catalogus of vervanging voor de bron.

Neem nieuwe beschikbare skills mee zonder deze dispatcher te hoeven wijzigen. Zoek bij een ontbrekende expliciet gevraagde skill gericht naar een andere beschikbare bron. Meld een blijvende ontbrekende skill en de gevolgen; verzin geen inhoud en beweer niet dat je haar hebt toegepast. Ga verder met onafhankelijk uitvoerbaar werk. Gebruik bij een niet-essentiële ontbrekende kandidaat de geldende contracten en benoem de bewijsgrens.

## 3. Kies per fase

Respecteer expliciet gevraagde skills binnen hun toepassingsgebied. Kies daarnaast alleen skills die een concrete behoefte dekken. Gebruik één primaire skill per activiteit; combineer aanvullende skills als ze een ander noodzakelijk deel afdekken. Leg geen willekeurige maximumgrens op en laad geen volledige collectie vooraf.

Gebruik deze voorbeelden alleen na controle tegen de actuele beschrijvingen:

| Behoefte | Kandidaat en selectiegrond |
| --- | --- |
| Gemelde bug of prestatieregressie | `diagnosing-bugs`: reproduceer en onderzoek de oorzaak vóór reparatie. |
| Software implementeren, repareren of voldoende bewijs beoordelen | `risk-proportional-verification`: bepaal vooraf bewijs uit concrete foutgevolgen; voer het bij uitvoering daadwerkelijk uit. Ook relevant bij kleine wijzigingen met grote gevolgen. |
| Domeinregels, eigenaarschap, duurzame toestand of transacties ontwerpen of wijzigen | `domain-first-architecture`: leg het domein vast vóór implementatie. Houd stateless werk licht. |
| Identiteit, versie, selectie, reviewcontext of voortgang over stappen behouden | `preserve-workflow-context`: borg de benodigde context op de geraakte route. |
| Een ontwerp, patch of codebase op onnodige complexiteit beoordelen | `minimal-code-surface-reviewer`: beoordeel de uiteindelijke oppervlakte; leid daaruit geen automatisch refactorwerk af. |
| Een expliciet gevraagde architectuurverkenning | `improve-codebase-architecture`: respecteer eventuele beperking tot expliciete aanroep. |
| Externe agents en hun toegangs- of uitvoeringsgrenzen | `external-agent-gates`: gebruik alleen wanneer de opdracht zulke agents betreft. |
| Onduidelijke voorstellen kritisch uitvragen | `grill-me`: selecteer wanneer gerichte besluitvorming ontbreekt; vermijd een interview bij een al uitvoerbare opdracht. |
| Strategische memo of bestuurlijk advies | `minto`: orden redenering en besluit. |
| Tekst redigeren of herschrijven | `via-negativa-redacteur`: verwijder overbodige tekst met behoud van betekenis en bewijs. |
| Complexe resultaten uitleggen | `heldere-uitleg`: stem uitleg af op lezer en gewenste beslissing. |
| Verandertheorie, beleidseffecten, KPI's of literatuuronderzoek | Zoek de passende actuele domeinskill, zoals `theory-of-change-builder`, `policy-impact-evaluator`, `kpi-designer` of `literature-review-suite`. |
| Bestanden, visuals, apps of andere specialistische uitvoering | Kies de toepasselijke tool- of artefactskill uit de actuele catalogus. Respecteer verplichte prerequisites. |

Kies bij een bugreparatie normaal diagnose en risicogerichte verificatie; voeg domeinontwerp of contextbehoud toe als de geraakte regels of route dat vereisen. Bepaal bewijs vóór de reparatie, en voer controles erna uit. Behandel review als een afzonderlijke activiteit zodra er een concreet ontwerp of definitieve diff is.

Gebruik bij eenvoudige tekstcorrecties of feitelijke antwoorden geen uitgebreid selectieproces. Pas rechtstreeks de relevante instructie toe; forceer geen skill als geen skill past.

## 4. Voer de route uit

Meld bij substantieel werk in één korte zin welke skills je gebruikt en waarom. Vermeld alleen daadwerkelijk gelezen en toegepaste skills.

Hergebruik bevindingen tussen skills: onderzoek dezelfde oorzaak, domeinregel of context niet opnieuw zonder reden. Bewaar in plan of werkcontext alleen het doel, de gekozen bron, de huidige fase, het concrete risico en het nog benodigde bewijs.

Respecteer de instructiehiërarchie en bestaande autorisatie. Een gekozen skill geeft geen extra toestemming om berichten te sturen, te deployen, te publiceren, gegevens te verwijderen, agents te starten of de scope uit te breiden. Volg toepasselijke projectcontracten zonder een tweede classificatie of concurrerend beleid te creëren.

Herselecteer wanneer de taakfase, scope, geraakt domein of materieel risico verandert. Behoud het oorspronkelijke doel en eerdere gebruikerskeuzes. Herlees ongewijzigde skills niet onnodig en routeer niet recursief terug naar deze dispatcher.

## 5. Rond af met bewijs

Controleer of alle noodzakelijke activiteiten zijn uitgevoerd, ook wanneer de primaire skill ze niet dekt. Rapporteer het resultaat, werkelijk uitgevoerde verificatie en materiële beperkingen. Scheid aangetoond gedrag, redelijke afleiding en open onzekerheid waar die het oordeel beïnvloeden.

Noem een gekozen route geen uitgevoerde controle en een geslaagde build geen bewijs voor een opgelost productieprobleem.
