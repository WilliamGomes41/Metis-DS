# V&VN Data Services — Protocol v3

**Status:** Candidate voor consolidatie en activatie  
**Versie:** 3.0.0-rc1  
**Datum:** 2026-09-10  
**Doel:** één korte, actuele norm voor Metis. Historische besluiten, implementatiegolven en supersessies horen niet in deze tekst.

## 1. Functie en normatieve hiërarchie

Dit protocol beschrijft wat Metis **nu** moet waarborgen. Het is geen roadmap, changelog, runbook of implementatiegeschiedenis.

Na activatie van Protocol v3 geldt de volgende hiërarchie:

1. `PROTOCOL.md` — actuele product-, veiligheids- en governance-invarianten;
2. `ROADMAP.md` — actieve veranderopgaven, experimenten en beslispoorten;
3. acceptatie- en regressietests — uitvoerbare bewijzen van de invarianten;
4. code, configuratie en infrastructuur — implementatie.

Bij strijdigheid wint de hogere laag. Historische protocollen, delta's, roadmaps en rapporten zijn auditbewijs en **niet sturend** voor nieuwe implementatie.

Een tijdelijke workaround, incidentroute of deploymentprocedure wordt niet automatisch protocol. Alleen blijvende product- of veiligheidsgrenzen horen hier.

## 2. Kern van Metis

Metis zet gezaghebbende brondocumenten gecontroleerd om in brongebonden kennisobjecten die kunnen worden gereviewd, gepubliceerd en teruggevonden.

Metis moet drie eigenschappen tegelijk behouden:

- **brontrouw:** iedere gepubliceerde inhoud is aantoonbaar herleidbaar tot een vastgelegde bron;
- **menselijke controle:** inhoudelijke publicatie vereist passende menselijke beoordeling;
- **fail-closed gedrag:** bij ontbrekend bewijs, ontbrekende bronbinding of ongeldige status wordt niet gepubliceerd of als ondersteund uitgegeven.

Metis is geen autonoom auteursysteem. Het systeem mag geen niet-brongebonden feiten als canonieke kennis toevoegen.

## 3. Bron en provenance

### 3.1 Bevroren bron

Iedere ingest gebruikt een vastgelegde bronversie. De originele bronbytes of een equivalent immutabel bronartefact moeten identificeerbaar blijven met ten minste een cryptografische hash en bronidentiteit.

Voor HTML geldt: Metis verwerkt een vastgelegde HTML-freeze; live URL-HTML is geen canonieke ingestbron.

### 3.2 Locator

Ieder kennisobject dat kan worden gepubliceerd of extern ondersteund moet een geldige bronlocator hebben waarmee een reviewer de relevante bronpassage kan terugvinden.

Ontbreekt de locator of kan de bronbinding niet worden bewezen, dan faalt toelating/publicatie gesloten.

### 3.3 Geen stille bronwijziging

Een nieuwe bronversie is een nieuwe versie van het bronartefact. Re-extractie of herclassificatie mag de oorspronkelijke bronidentiteit, hash of auditgeschiedenis niet overschrijven alsof de bron niet is veranderd.

## 4. Kennisobjectcontract

Een inhoudelijk kennisobject is één complete, zelfstandig begrijpelijke betekeniseenheid die binnen de bron kan worden verantwoord.

Een object mag niet uitsluitend bestaan uit:

- een nummer, label of kopwoord;
- navigatie- of interfacechrome;
- een losse stempel;
- een grammaticaal of inhoudelijk onaf zinsfragment;
- een duplicaat dat alleen door herhaalde bronmarkup is ontstaan.

Voorwaarden, uitzonderingen, doelgroep, modaliteit en andere context die de betekenis van een uitspraak wezenlijk begrenzen, mogen niet door passagevorming verloren gaan.

Objecttype en relaties moeten uit de gesloten, geldende taxonomie komen. Onzekerheid wordt expliciet behandeld; het systeem mag niet stilzwijgend een sterker type, sterkere modaliteit of sterkere relatie afleiden dan de bron ondersteunt.

## 5. Semantische interpretatie en harde invarianten

Metis onderscheidt twee soorten logica:

1. **semantische interpretatie** — bepalen welke brontekst inhoudelijk bij elkaar hoort en welke context voor betekenis nodig is;
2. **harde invariant** — controleerbaar bewaken dat bronbinding, volledigheid, geldige status, review, publicatiebevoegdheid en andere veiligheidsvoorwaarden zijn vervuld.

Nieuwe taalgevallen mogen niet automatisch leiden tot een nieuwe lexicale uitzonderingsregel. Voor een nieuwe regel wordt eerst vastgelegd of deze:

- een harde, algemeen geldende invariant afdwingt; of
- natuurlijke taal probeert te interpreteren.

Deterministische controles blijven de autoriteit voor harde veiligheids- en publicatievoorwaarden.

### 5.1 Huidige productiegrens

Zolang geen afzonderlijk, evidence-backed besluit tot wijziging is genomen, blijft de bestaande productiepassagevorming leidend. Een semantisch model mag in een experiment voorstellen doen, maar mag niet zelfstandig canonieke kennis schrijven of publiceren.

## 6. Review

### 6.1 Menselijke beoordeling

Canonieke publicatie is gebonden aan menselijke review. De reviewer moet de kennisinhoud kunnen beoordelen tegen de relevante bronpassage en locator.

Review is proportioneel aan risico en disposition. Niet ieder bronfragment hoeft als gelijkwaardige, handmatige reviewkaart te worden behandeld, maar iedere route moet aantoonbaar bepalen waarom een passage:

- reviewplichtig is;
- structureel of informatief wordt afgehandeld;
- wordt verworpen;
- of niet publiceerbaar is.

### 6.2 Four-eyes

Voor high-risk inhoud en andere door de geldende reviewpolicy aangewezen gevallen blijft vier-ogenbeoordeling verplicht. De tweede beoordeling moet onafhankelijk identificeerbaar en auditbaar zijn.

### 6.3 Wijzigingen tijdens review

Een reviewcorrectie mag de bronbinding niet verbreken. Wanneer een reviewer inhoud toevoegt of wijzigt die niet uit de bron kan worden verantwoord, mag die versie niet als brongetrouw kennisobject worden gepubliceerd.

## 7. Toelating en publicatie

### 7.1 Fail closed

Een object mag alleen naar publicatie wanneer alle toepasselijke toelatings-, review- en prepublicatievoorwaarden aantoonbaar zijn geslaagd.

Onbekende, ontbrekende, stale of tegenstrijdige status geldt niet als toestemming.

### 7.2 Publicatiebevoegdheid

Publicatie is een expliciete statusovergang en geen neveneffect van ingest, review, retrieval, deployment of configuratie.

De G2-publicatieroute kan operationeel geactiveerd zijn, maar blijft onderworpen aan de geldende prepublication checks, bronbinding, reviewstatus en autorisatie. Activatie betekent niet dat brede of automatische publicatie is toegestaan.

### 7.3 Ongepubliceerde documenten verwijderen

Een geautoriseerde operator mag een ongepubliceerde snapshot verwijderen wanneer de console expliciete bevestiging vraagt en een auditeerbare gebeurtenis vastlegt.

Deze route mag geen gepubliceerde projectie verwijderen en mag geen delen van een nog bestaande review-freeze stilzwijgend verbergen.

## 8. Audit en statusovergangen

Betekenisvolle statusovergangen in ingest, review, tweede review, herclassificatie, verwijdering en publicatie moeten reproduceerbaar en auditbaar zijn.

Auditbewijs moet voldoende zijn om achteraf vast te stellen:

- welk bronartefact en welke versie zijn gebruikt;
- welke relevante pipeline-/policyversie is gebruikt;
- welke actor of gecontroleerde systeemstap de overgang uitvoerde;
- welke review- en publicatievoorwaarden golden;
- wat de uitkomst was.

Auditlogica mag geen alternatieve publicatieroute creëren.

## 9. Experimenten

Experimenten horen in het Audit-domein en zijn strikt gescheiden van canonieke productie.

Een experiment mag baseline en kandidaatroute op dezelfde vastgezette brondata vergelijken. Voor semantische passagevorming geldt minimaal:

- dezelfde bevroren bron als uitgangspunt;
- brongebonden voorstellen;
- deterministische verificatie van harde invarianten;
- blinde of anderszins vergelijkbare menselijke beoordeling waar relevant;
- vastgelegde metrics en besluitcriteria;
- geen directe schrijfrechten naar canonieke publicatie.

Een experimentele kandidaat mag pas productielogica vervangen na een expliciet besluit op basis van bewijs. De standaard beslisuitkomst is `KEEP`, `ITERATE` of `PROCEED`.

Voor onverifieerbare toevoegingen in een brongebonden passagevormingsexperiment geldt nul tolerantie als publicatieveiligheidscriterium.

## 10. Console, Product API en runtimegrenzen

### 10.1 Console

De operations console is het menselijke werkoppervlak voor onder meer ingest, review, documentbeheer en gecontroleerde publicatiehandelingen.

De huidige console blijft server-rendered en gebruikt browser-native formulieren waar dat volstaat. Een frontend-framework, SPA-laag of vergelijkbare complexiteit wordt alleen toegevoegd wanneer een aantoonbare productbehoefte dat rechtvaardigt.

### 10.2 Product API

De Product API levert brongebonden objecten en moet kunnen abstainen wanneer ondersteuning ontbreekt. De API mag geen unsupported object als `supported` presenteren.

De Product API genereert in de huidige productgrens geen vrije prozaconclusies alsof die canonieke bronkennis zijn.

### 10.3 Runtime- en datagrens

Console/review en retrieval/distributie mogen verschillende runtimepakketten hebben, maar delen één kennis- en publicatiewet.

Ongepubliceerde reviewdata en console-accounts mogen niet via Product API-credentials of subscriber-routes toegankelijk worden.

De dunne console-runtime mag niet onnodig retrieval-/embeddingdependencies binnenhalen wanneer die niet nodig zijn voor de reviewtaak.

## 11. Retrieval en externe distributie

Retrieval mag uitsluitend publiceren/uitgeven wat volgens de geldende publicatieprojectie beschikbaar is.

Een ondersteund resultaat moet herleidbaar blijven tot het gepubliceerde kennisobject en de bronprovenance. Wanneer voldoende ondersteuning ontbreekt, moet de retrievalroute abstainen in plaats van een antwoord te construeren dat sterker is dan de bron of publicatiestatus.

Retrieval- of rankinglogica mag publicatiestatus, menselijke review of bronbinding niet omzeilen.

## 12. Security, topology en deployment

Productie- en testomgevingen, credentials en opslagrechten moeten zodanig gescheiden zijn dat een fout in een niet-productieroute geen impliciete productierechten oplevert.

Deployment gebeurt vanaf een identificeerbare, gecontroleerde commit en met een reproduceerbaar pakket. Deployment mag runtime-data niet wissen en mag geen publicatierechten openen doordat applicatiecode of configuratie aanwezig is.

De normale deploymentroute en noodprocedure worden in het actuele runbook/roadmap vastgelegd; tijdelijke incidentworkarounds worden niet als blijvende protocolwet gecodificeerd.

## 13. Test- en bewijsdiscipline

Een protocolinvariant die technisch afdwingbaar is, moet waar mogelijk door een gedrags- of integratietest worden bewezen.

Tests horen primair gedrag en veiligheidsgrenzen te bewijzen. Tests die uitsluitend historische formuleringen, deltatext of supersessiezinnen in actuele stuurdocumenten afdwingen, zijn geen blijvende V3-governancevorm.

Historische protocoltests mogen historische artefacten blijven verifiëren, maar mogen niet vereisen dat oude tekst in het actuele protocol of de actuele roadmap blijft staan.

## 14. Wijzigingsgovernance vanaf v3

Vanaf v3 wordt geen nieuwe keten van `PROTOCOL_V3_x_DELTA.md`-bestanden opgebouwd voor normale productontwikkeling.

Een blijvende wijziging in product- of veiligheidsinvarianten volgt deze route:

1. wijzigingsbesluit met reden en bewijs;
2. directe wijziging van de actuele `PROTOCOL.md`;
3. passende tests aanpassen of toevoegen;
4. vorige protocolstand als onveranderde historische snapshot bewaren;
5. actieve vervolgstappen in `ROADMAP.md` bijwerken.

Implementatiegeschiedenis, incidentdetails, tijdelijke volgordes en uitgevoerde golven horen in changelog, auditrapport of `docs/history/`, niet in het actuele protocol.

## 15. Relatie tot Protocol v2

Protocol v3 consolideert de blijvende product-, veiligheids- en governancegrenzen uit de Protocol-v2-reeks tot één actuele norm.

Na activatie van v3 zijn de v2-documenten en hun approval-manifests historisch auditbewijs. Zij zijn dan niet langer een aanvullende stuurlaag en hoeven niet te worden gelezen om te bepalen wat nu geldt.

Waar v3 bewust geen historisch implementatiedetail overneemt, is dat detail niet automatisch verboden of verplicht; de actuele code, tests, configuratie en roadmap bepalen de implementatiestatus binnen de grenzen van dit protocol.

## 16. Activatiecriteria

`3.0.0-rc1` wordt pas `3.0.0` en de actuele root-norm wanneer:

- de volledige v2-protocolstand en pre-v3-roadmap als bevroren historie beschikbaar zijn;
- historische approval-manifests controleerbaar blijven;
- governance-tests niet langer vereisen dat actuele stuurdocumenten de volledige v2-deltageschiedenis dupliceren;
- de korte actuele roadmap afzonderlijk is vastgesteld;
- CI groen is op de activatie-PR.

Tot dat moment is dit document een consolidatiekandidaat en blijft de bestaande root-baseline formeel leidend.
