# V&VN Data Services — Protocol v3

**Status:** Actief  
**Versie:** 3.0.0  
**Datum:** 2026-09-10  
**Functie:** één actuele norm voor Metis. Historische besluiten, implementatiegolven en supersessies zijn auditbewijs en geen aanvullende stuurlaag.

## 1. Normatieve hiërarchie

Metis wordt gestuurd in deze volgorde:

`PROTOCOL.md → ROADMAP.md → acceptatietests → code`

`PROTOCOL.md` bevat blijvende product-, veiligheids- en governance-invarianten. `ROADMAP.md` bevat alleen actieve veranderopgaven, beslispoorten en stopvoorwaarden. Tests bewijzen de norm; code, configuratie en infrastructuur implementeren haar.

Bij strijdigheid wint de hogere laag. Een tijdelijke workaround, deploymentvolgorde, incidentroute, experiment of implementatiegolf wordt niet automatisch protocol.

Historische protocollen, delta's, roadmaps, approvals en auditrapporten zijn niet sturend voor nieuwe implementatie.

## 2. Productgrens

Metis zet gezaghebbende brondocumenten gecontroleerd om in brongebonden kennisobjecten die kunnen worden gereviewd, gepubliceerd en teruggevonden.

Drie eigenschappen zijn altijd vereist:

- **brontrouw:** gepubliceerde inhoud is aantoonbaar herleidbaar tot een vastgelegde bron;
- **menselijke controle:** inhoudelijke publicatie vereist passende menselijke beoordeling;
- **fail-closed gedrag:** ontbrekend of tegenstrijdig bewijs geeft geen toestemming tot publicatie of ondersteunde distributie.

Metis is geen autonoom auteursysteem. Een model, retrievalcomponent of andere automatische stap mag geen niet-brongebonden feiten als canonieke kennis toevoegen of publiceren.

## 3. Bron en provenance

### 3.1 Bevroren bron

Iedere ingest gebruikt een vastgelegde bronversie. De originele bronbytes of een equivalent immutabel bronartefact moeten identificeerbaar blijven met ten minste bronidentiteit en SHA-256.

Voor HTML geldt een vastgelegde HTML-freeze. Live URL-HTML is geen canonieke ingestbron. PDF-upload en een gecontroleerde PDF-URL mogen binnen de ondersteunde ingestgrens blijven.

### 3.2 Locator

Ieder kennisobject dat kan worden gepubliceerd of extern ondersteund moet een geldige bronlocator hebben waarmee de relevante bronpassage kan worden teruggevonden.

Ontbreekt de locator, de bron of de controleerbare binding daartussen, dan faalt toelating/publicatie gesloten.

### 3.3 Versies

Een nieuwe bronversie is een nieuwe versie van het bronartefact. Re-extractie, review of herclassificatie mag bronidentiteit, bronhash of auditgeschiedenis niet overschrijven alsof de bron niet is veranderd.

## 4. Passage-register en kennisobjectcontract

### 4.1 Passage-disposition

Iedere inhoudelijke bronpassage krijgt een expliciete disposition uit de gesloten set:

- `selected_as_candidate`;
- `used_as_context`;
- `linked_as_support`;
- `excluded_with_reason`;
- `not_yet_assessed` uitsluitend als niet-terminale status zolang beoordeling nog niet gereed is.

Een passage die de toelatingspoort niet haalt is niet automatisch `excluded_with_reason`. Een geblokkeerde kandidaat en een inhoudelijk uitgesloten passage zijn verschillende beslissingen.

### 4.2 Kennisobject

Een bruikbaar kennisobject is één complete, zelfstandig begrijpelijke betekeniseenheid die volledig uit de bron kan worden verantwoord.

Een object mag niet uitsluitend bestaan uit een nummer, label, kopwoord, navigatiechrome, losse stempel, grammaticaal of inhoudelijk onaf fragment, of een duplicaat dat alleen door herhaalde bronmarkup ontstaat.

Voorwaarden, uitzonderingen, doelgroep, modaliteit en andere context die de betekenis wezenlijk begrenzen mogen niet door passagevorming verloren gaan.

Verplichte velden voor het voorgestelde objecttype moeten met letterlijke, lokaliseerbare broninformatie zijn gevuld. Ontbreekt een verplicht veld, dan blijft de kandidaat geblokkeerd; een zachte kwaliteitsscore mag deze harde poort niet openen.

Objecttype en relaties komen uit de geldende gesloten taxonomie. Onzekerheid wordt expliciet behandeld; het systeem mag geen sterker type, sterkere modaliteit of sterkere relatie afleiden dan de bron ondersteunt.

## 5. Semantische interpretatie en harde invarianten

Metis onderscheidt:

1. **semantische interpretatie:** bepalen welke brontekst inhoudelijk bij elkaar hoort en welke context voor betekenis nodig is;
2. **harde invarianten:** controleerbaar bewaken van bronbinding, verplichte velden, status, review, autorisatie, publicatie en andere veiligheidsvoorwaarden.

Een nieuw taalgeval leidt niet automatisch tot een nieuwe lexicale uitzonderingsregel. Eerst wordt bepaald of het probleem natuurlijke taal interpreteert of een algemeen geldende invariant afdwingt.

Deterministische controles blijven de autoriteit voor harde veiligheids- en publicatievoorwaarden.

De bestaande productiepassagevorming blijft leidend tot een afzonderlijk extern ontwikkelde, geautoriseerde en gereleasete vervanging. Een experimenteel semantisch model mag voorstellen doen, maar niet zelfstandig canonieke kennis schrijven of publiceren. `PROCEED` is geen Metis-productievervangingsbesluit. Audit-eindstatus is `READY FOR IMPLEMENTATION`; ontwikkeling gebeurt buiten Metis. Er is geen APPLY-executor.

## 6. Review

### 6.1 Exacte objectbinding

Ieder bruikbaar kennisobject dat richting publicatie kan gaan krijgt menselijke review die gebonden is aan de exacte objectidentiteit, objectversie/canonieke hash, bevestigd type, reviewer en beslissing.

De gebruikersinteractie mag voor coherent normaal-risico-inhoud batchgewijs verlopen, maar de opslag moet per exact object een individuele reviewuitkomst vastleggen. Het protocol vereist geen duizenden afzonderlijke klikken wanneer dezelfde assurance aantoonbaar anders kan worden geleverd.

### 6.2 Proportionaliteit en disposition

Review is proportioneel aan risico en disposition. Structurele/contextuele passages, uitgesloten passages en publiceerbare kennisobjecten hoeven niet als één identieke handmatige reviewplicht te worden behandeld. Iedere route moet wel aantoonbaar vastleggen waarom de passage of het object die route kreeg.

### 6.3 Four-eyes

High-risk inhoud en andere door de geldende reviewpolicy aangewezen gevallen vereisen onafhankelijke tweede beoordeling. De tweede reviewer moet onafhankelijk identificeerbaar zijn en hetzelfde exacte object/snapshot beoordelen.

### 6.4 Correcties

Een reviewcorrectie mag de bronbinding niet verbreken. Inhoud die na wijziging niet uit de bron kan worden verantwoord, mag niet als brongetrouw kennisobject worden gepubliceerd.

## 7. Publicatie en G2

### 7.1 Publicatie is expliciet en per snapshot

Publicatie is een expliciete statusovergang en nooit een neveneffect van ingest, review, deployment, retrieval of configuratie.

G2-publicatie is conditioneel beschikbaar **per snapshot**. Er bestaat geen algemene open publicatiestand.

Een snapshot mag uitsluitend worden gepubliceerd wanneer alle volgende voorwaarden aantoonbaar waar zijn:

1. de actor heeft de `publisher`-rol en geeft expliciete bevestiging;
2. ten minste één niet-documentair kennisobject heeft een actuele `approve`-reviewbinding aan exact object-ID, versie/canonieke hash, bevestigd type, reviewer en beslissing;
3. alle vereiste onafhankelijke review en high-risk four-eyes zijn geslaagd;
4. ieder voor publicatie geselecteerd object is goedgekeurd en schema-valide;
5. ieder geselecteerd object heeft een geldige immutable G2 Azure Blob-bronlocator;
6. de geconfigureerde immutable source store kan de betreffende blob op het publicatiemoment daadwerkelijk lezen;
7. SHA-256 van de gezaghebbende bronbytes is gelijk aan de source hash in de vastgelegde envelope;
8. de afgeleide retrievalprojectie kan worden opgebouwd zonder geblokkeerde records.

Een app-setting, locator-achtige string, UI-status, reviewflag in een envelope of opslagrecht op zichzelf creëert nooit G2 `PASS`.

### 7.2 Succesvolle cutover

Een succesvolle publicatie:

- maakt een immutabel release-manifest met release-identiteit, protocolversie, bronidentiteit en exacte gepubliceerde object-ID's/hashes;
- bouwt en wisselt de retrievalprojectie atomair;
- schrijft een append-only `release_published` auditgebeurtenis;
- markeert de snapshot pas bij geslaagde cutover als gepubliceerd.

### 7.3 Mislukte cutover

Bij een mislukte cutover wordt fail-closed teruggerold naar de vorige geldige projectie en envelopestatus. Een incompleet release-manifest of onterechte `release_published`-gebeurtenis mag niet achterblijven.

Herpublicatie van een reeds gepubliceerde snapshot faalt gesloten. Canonieke objecten en bronbytes worden niet stilzwijgend herschreven.

Reviewgoedkeuring alleen publiceert niets. Het Publiceren-oppervlak mag onderscheid maken tussen blocked, ready en published.

G2-publicatie activeert niet automatisch de externe Product API en is geen besluit tot brede uitrol.

## 8. Ongepubliceerde documenten verwijderen

Een geautoriseerde console-operator mag een ongepubliceerde snapshot verwijderen via de daarvoor aangewezen plek onder **Documenten**, met expliciete type-to-confirm bevestiging en een auditeerbare gebeurtenis.

De verwijderroute mag geen gepubliceerde projectie verwijderen en mag geen delen van een nog bestaande review-freeze stilzwijgend verbergen. Een SSH-wipe of generieke verwijdering van runtime-opslag is geen productroute.

## 9. Audit en statusovergangen

Betekenisvolle statusovergangen in ingest, disposition, review, tweede review, herclassificatie, verwijdering en publicatie moeten reproduceerbaar en auditbaar zijn.

Auditbewijs moet voldoende zijn om achteraf vast te stellen welk bronartefact en welke versie zijn gebruikt, welke relevante pipeline-/policyversie gold, welke actor of gecontroleerde systeemstap de overgang uitvoerde, welke voorwaarden golden en wat de uitkomst was.

Auditlogica mag geen alternatieve publicatieroute creëren.

## 10. Experimenten

Experimenten horen in het Audit-domein en zijn strikt gescheiden van canonieke productie.

Een experiment vergelijkt baseline en kandidaatroute op dezelfde vastgezette brondata. Voor semantische passagevorming geldt minimaal:

- dezelfde bevroren bron als uitgangspunt;
- brongebonden voorstellen;
- deterministische verificatie van harde invarianten;
- blinde of anderszins vergelijkbare menselijke beoordeling waar relevant;
- vooraf vastgelegde metrics en besluitcriteria;
- geen directe schrijfrechten naar canonieke publicatie.

Een kandidaatroute vervangt productielogica niet via `PROCEED` of een APPLY-executor. De terminale Metis-status voor een voldoende onderbouwde verbeterbundel is `READY FOR IMPLEMENTATION`. Die status autoriseert geen codewijziging, GitHub-write, merge, deploy of publicatie; softwareontwikkeling gebeurt buiten Metis. `KEEP` en `ITERATE` blijven experimentbesluiten binnen Audit en zijn geen implementatie-autorisatie.

Voor onverifieerbare toevoegingen die als brongebonden kennis zouden kunnen doorstromen geldt nul tolerantie.

## 11. Console, Product API en runtimegrenzen

### 11.1 Console

De operations console is het menselijke werkoppervlak voor ingest, review, documentbeheer, audit en gecontroleerde publicatiehandelingen. De primaire consolevolgorde blijft herkenbaar als **Inleveren → Review → Publiceren → Documenten**.

De console blijft server-rendered en gebruikt browser-native formulieren waar dat volstaat. Een SPA, frontendframework of vergelijkbare complexiteitslaag wordt alleen toegevoegd na een aantoonbare productbehoefte.

### 11.2 Product API

De Product API is object-level retrieve-and-abstain. Zij mag geen unsupported object als `supported` presenteren, geen ongepubliceerde reviewdata distribueren en geen vrije prozaconclusie als canonieke bronkennis construeren.

### 11.3 Runtime- en datagrens

Console/review en retrieval/distributie mogen verschillende runtimepakketten hebben, maar delen één kennis- en publicatiewet.

Ongepubliceerde reviewdata en console-accounts mogen niet via Product API-credentials of subscriber-routes toegankelijk zijn. Product API-credentials mogen geen toegang geven tot de unpublished review-store.

De console-runtime haalt geen zware retrieval-/embeddingdependencies binnen wanneer die voor de reviewtaak niet nodig zijn.

## 12. Retrieval en externe distributie

Retrieval mag uitsluitend uitgeven wat volgens de geldige gepubliceerde projectie beschikbaar is.

Een ondersteund resultaat blijft herleidbaar tot het gepubliceerde kennisobject en de bronprovenance. Bij onvoldoende ondersteuning, ontbrekende locator, ongeldige publicatiestatus of ontbrekende entitlement wordt geabstaind in plaats van een sterker antwoord te construeren.

Ranking of retrieval mag publicatiestatus, menselijke review of bronbinding niet omzeilen.

## 13. Security, topology en deployment

Productie- en testomgevingen, credentials en opslagrechten zijn zodanig gescheiden dat een fout in een niet-productieroute geen impliciete productierechten oplevert.

De huidige ondersteunde console-topologie blijft single-worker/single-instance met sequentiële writes zolang geen afzonderlijke, geteste multi-writerarchitectuur is vastgesteld. Een schaalwijziging mag niet stilzwijgend de consistency- of reviewgaranties veranderen.

Deployment gebeurt vanaf een identificeerbare gecontroleerde commit en met een reproduceerbaar pakket. Deployment mag runtime-data niet wissen en mag geen publicatierechten openen doordat applicatiecode of configuratie aanwezig is.

De normale deploymentroute en noodprocedure staan buiten het protocol in de actuele operationele documentatie/roadmap. Een tijdelijke incidentworkaround wordt geen blijvende architectuurregel.

## 14. Test- en bewijsdiscipline

Een technisch afdwingbare protocolinvariant wordt waar mogelijk met een gedrags-, integratie- of invarianttest bewezen.

Tests bewijzen primair gedrag en veiligheidsgrenzen. Tests die uitsluitend historische formuleringen, deltatekst of supersessiezinnen in actuele stuurdocumenten afdwingen zijn geen geldige blijvende V3-governancevorm.

Historische protocoltests mogen historische artefacten en approval-manifests blijven verifiëren, maar mogen niet vereisen dat V2-tekst in `PROTOCOL.md` of `ROADMAP.md` blijft staan.

## 15. Wijzigingsgovernance vanaf V3

Vanaf V3 wordt voor normale productontwikkeling geen nieuwe keten van `PROTOCOL_V3_x_DELTA.md`-bestanden opgebouwd.

Een blijvende wijziging in product- of veiligheidsinvarianten volgt deze route:

1. wijzigingsbesluit met reden en bewijs;
2. directe wijziging van de actuele `PROTOCOL.md`;
3. passende tests aanpassen of toevoegen;
4. de vorige protocolstand als onveranderde historische snapshot bewaren;
5. actieve vervolgstappen in `ROADMAP.md` bijwerken.

Implementatiegeschiedenis, incidentdetails, tijdelijke volgordes en uitgevoerde golven horen in changelog, auditrapport of `docs/history/`, niet in het actuele protocol.

## 16. Protocol V2 is historie

Protocol V3 consolideert de blijvende product-, veiligheids- en governancegrenzen uit de V2-reeks. De V2-documenten en approval-manifests blijven onveranderbaar auditbewijs, maar vormen geen aanvullende actuele stuurlaag.

De volledige pre-V3 rootstanden zijn bevroren onder `docs/history/protocol-v2/`. Oude V2-bestanden mogen op hun oorspronkelijke paden blijven wanneer approval-manifests of historische tests hun exacte bytes of paden nodig hebben. Dat maakt ze niet opnieuw normatief.

Om te bepalen wat Metis nu moet doen, hoeft de V2-deltaketen niet meer te worden gelezen.
