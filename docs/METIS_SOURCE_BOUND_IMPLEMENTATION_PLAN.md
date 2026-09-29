# Metis — domeingedreven implementatieplan en legacyregister

Datum: 29 september 2026
Planversie: 1.1 — aangescherpt op exactheid, betekenisbehoud en menselijke curatie na analyse van Dense X Retrieval en Project Alexandria.
Codebasis: lokaal onderzochte commit `092cf411acf8ebed75c6b27d8659ac91aaa8c4d5` van Metis-DS. Dit is geen bevestiging van de huidige GitHub-main of productieversie.
Status: implementatievoorstel. De legacyclassificaties hieronder zijn ontwerpbesluiten voor uitvoering; met dit document is nog geen runtimepad uitgeschakeld of code gewijzigd.

## 1. Besluit en gebruikersbelofte

Metis krijgt één proces voor brongebonden kandidaatvorming en menselijke beoordeling. Binnen dat proces kunnen een structurele methode en een semantische methode voorstellen produceren. Zij gebruiken hetzelfde voorstelcontract, dezelfde broncontrole en dezelfde opslaggrens.

Belofte: een beoordelaar ontvangt een herleidbare bronpassage met een onderbouwd betekenisvoorstel en de noodzakelijke context; ontbrekende informatie en onbehandelde broninhoud blijven zichtbaar. De beoordelaar hoeft geen technische route te kiezen.

### Oorspronkelijke opdracht als grens

Metis maakt bestaande bronkennis gecontroleerd en gecureerd herbruikbaar. Het bewaart de exacte bronpassage en haar herkomst, ondersteunt inhoudelijke beoordeling en publiceert alleen via de bestaande bevoegde besluitvorming. Het wordt met deze wijziging geen systeem dat zelfstandig nieuwe kennis, samenvattingen of vervangende formuleringen publiceert.

- **Exact:** objecttekst en betekenisdragende veldtekst worden opgebouwd uit vastgelegde bronselecties. Toegestane technische normalisatie mag inhoud niet wijzigen. De koppeling naar oorspronkelijke bytes, pagina/HTML-positie en extractieversie blijft behouden. Exacte overname van extractietekst bewijst nog geen correcte PDF/OCR-extractie; twijfel daarover moet in review controleerbaar zijn.
- **Gecontroleerd:** technische controles toetsen bronbinding, versies en contract. Inhoudelijke controle toetst of selectie, type en relaties dezelfde betekenis behouden. Een modelscore of geldig JSON-object is geen inhoudelijk akkoord.
- **Gecureerd:** de bevoegde mens beoordeelt de passage, het type, context en relevante relaties binnen het bestaande reviewproces. Correcties op bronselectie en interpretatie zijn versioneerbaar; de oorspronkelijke bron blijft intact. Een redactionele notitie blijft apart en wordt niet als letterlijk broncitaat gepresenteerd.
- **Herleidbaar gepubliceerd:** technische toelating, menselijke beoordeling en publicatie zijn afzonderlijke beslissingen. Bestaande tweede-review- en publicatievereisten blijven gelden.

De deterministische basis blijft: extractie, bronreconstructie, locators, exacte tekstvorming, contractvalidatie en opslag. Het model krijgt geen bevoegdheid eigen kenniszinnen te schrijven. Voor vrije tekst is de meerwaarde van modelvoorstellen nog een te toetsen hypothese. Dit plan schakelt daarom de bestaande productievoorbereiding pas uit na een inhoudelijke en operationele acceptatieproef.

## 2. Classificatie en eigenaarschap

Programma: **Class B, Rewrite risk: high** voor vervanging van de gedeelde voorstel- en toelatingsaansluiting, met gefaseerde compatibiliteit. De bron-, document-, review- en publicatielevenscyclus blijft inhoudelijk gelijk. Een deelissue dat deze waarheden toch verandert wordt vóór uitvoering Class A en volgt het volledige lifecycle-contract; dit plan autoriseert die wijziging niet impliciet.

Het rekenen aan bronselecties en het valideren van een voorstel zijn stateless. Bewaren van verwerkingspogingen, voorstelsets, beoordelingsbewijs en het toepassen op een WorkingRevision zijn stateful.

Bestaande autoriteiten blijven leidend:

| Waarheid | Eigenaar |
|---|---|
| Bronbytes en hash | Immutable source store / SourceSnapshot |
| Bewerkbare objecten, review en reparatie | Bestaande duurzame workflowopslag / WorkingRevision |
| Historisch gepubliceerde objectversies | Canonical publication store |
| Actief beschikbaar gestelde releases | Publication registry |
| Schermselecties, open tab, oningediend formulier | Tijdelijke consoletoestand |

De Azure-kernel valideert en commit domeincommando's. Een componentnaam zoals OperationsConsole maakt zijn huidige backendlogica niet automatisch browserlogica. Dit plan vereist geen verplaatsing van alle klassen; het beschermt de bestaande duurzame grenzen. Geen tweede objectstore, reviewstatus of publicatieautoriteit invoeren.

## 3. Domeinmodel en contract

Hergebruik LogicalDocument, SourceSnapshot, WorkingRevision en PublicationRelease zoals beschreven in `docs/agents/lifecycle-vsa.md`.

- **Bronpassage:** geselecteerde tekst uit een vastgelegde bron, inclusief positie, sectie en herkomst. Dit is nog geen inhoudelijk goedgekeurd kennisobject.
- **Kandidaat-kennisobject:** voorstel tot betekenisvolle ordening van een bronpassage. Type, betekenisvelden en relaties zijn voorstellen. Het object representeert wat deze bron stelt, niet automatisch een algemeen vastgestelde waarheid. Een hypothese, bevinding, modelvoorspelling en aanbeveling mogen door omzetting niet van strekking veranderen.
- **Beoordeling:** menselijk besluit binnen de bestaande reviewbevoegdheden. Een machinebesluit of technische validatie vervangt dit niet.
- **Verwerkingspoging:** bewijs over één uitvoering, gebonden aan bron, werkrevisie, basisversie en contract. Breid bestaande verwerkingsevidence uit; maak geen tweede autoriteit voor objectstatus.
- **Brondekking:** administratieve verantwoording van aangeboden en afgehandelde bronbereiken. Dit bewijst niet automatisch dat alle inhoud correct begrepen is.

Voorgesteld gedeeld contract v2:

1. Bronidentiteit, werkrevisie, bronblokkenversie en contractversie.
2. Geselecteerde bronbereiken: blok-ID plus begin- en eindpositie.
3. Voorgesteld type uit de bestaande gesloten taxonomie.
4. Bewijs per verplicht typeveld als bronbereik, of expliciete ontbreekreden. Actor, handeling en doel worden niet als vrije modeltekst aanvaard.
5. Aanbevelingsrichting en expliciete sterkte als gesloten waarden met bronbewijs.
6. Benodigde context als verwijzingen met een gesloten rol, bijvoorbeeld voorwaarde, uitzondering of antecedent. Context mag brongetrouw buiten de geselecteerde kernpassage liggen; de kernpassage hoeft niet kunstmatig over sectiegrenzen te worden samengevoegd.
7. Relatievoorstellen met beide uiteinden en exact bewijs voor de volledige voorgestelde relatie: inclusief richting, ontkenning, onzekerheid en eventuele voorwaarden. Bewijs dat alleen beide entiteiten noemt is onvoldoende.
8. Afhandeling van ieder aangeboden bronbereik: geselecteerd, context, geen kandidaat of onzeker. Gedeeltelijke selectie laat restbereiken expliciet over. Ontbrekende uitvoer is een onvolledige poging, geen modelbesluit 'geen kandidaat'.
9. Herkomst van ieder voorstel: methode, regel/modelversie, uitvoeringspoging en bewijsverwijzingen.
10. Behoud van betekenisdragende kwalificaties via exacte bronverwijzingen: bronspreker/toeschrijving, onzekerheid, tijd, doelgroep, voorwaarden, uitzonderingen, getallen en eenheden, voor zover aanwezig. Start met bewijs en review binnen de bestaande taxonomie; introduceer niet automatisch nieuwe objecttypen of een universele kennisgraaf.

### Twee afzonderlijke kwaliteitsvragen

**Bronbinding:** komen tekst en bewijs daadwerkelijk uit de vastgelegde bron? Dit is grotendeels deterministisch controleerbaar.

**Betekenisbehoud:** drukt de combinatie van selectie, metadata en relaties uit wat de bron zegt, zonder verzwakking, versterking of verandering van toepassingsgebied? Dit vraagt inhoudelijke evaluatie en menselijke curatie. Een brongetrouwe selectie kan toch een uitzondering missen. De reviewweergave moet beide vragen afzonderlijk controleerbaar maken, zonder een tweede reviewlevenscyclus in te voeren.

Voorbeeld (fictief): bij 'De auteurs vermoeden dat X samenhangt met Y' is een relatie 'X veroorzaakt Y' niet onderbouwd. Geldige verwijzingen naar X en Y herstellen die fout niet. Voorgestelde interpretaties blijven herkenbaar als voorstel tot de bestaande menselijke bevestiging.

Metis reconstrueert alle getoonde bron- en veldtekst zelf. Als een vereiste actor of handeling niet expliciet aanwijsbaar is, rapporteert het systeem ontbrekend. Het mag niet raden om door toelating te komen. Blijkt een bestaande eis onjuist voor een geldige bronuitspraak, behandel dat als een afzonderlijke domeinbeslissing met voorbeelden; versoepel het niet stilzwijgend.

## 4. Invarianten en beleidskeuzes

### Harde invarianten

- Geen modelgeschreven kandidaattekst; onbekende extra tekstvelden worden afgewezen.
- Iedere tekstselectie en bewijsverwijzing is geldig binnen de gebonden bronversie. Normalisatie is gedocumenteerd en terug te voeren op bronposities.
- Voorstel, bewijs en voorgestelde relaties verwijzen naar dezelfde object-/bronversies.
- Bronwoorden alleen zijn geen bewijs van betekenisbehoud. Voorwaarden, uitzonderingen, negatie, onzekerheid, toeschrijving, tijd, getallen, eenheden en toepassingsbereik worden apart geëvalueerd.
- Een gegenereerd voorstel, eerdere Knowledge Unit, samenvatting of modelantwoord geldt nooit zelfstandig als bronbewijs voor een nieuw voorstel. Ondersteunende context moet naar oorspronkelijke broninhoud terug te voeren zijn.
- Menselijke review kan selectie en interpretatie corrigeren, maar geen gewijzigde woorden als letterlijk afkomstig uit de ongewijzigde bron presenteren.
- Machinevalidatie en een modelconfidence-score kunnen geen menselijke bevestiging of bestaande publicatievoorwaarde vervangen.
- Resttekst blijft behouden en wordt nooit automatisch als inhoudelijk afgewezen geregistreerd.
- Een nieuwe poging wijzigt geen bestaande menselijke beoordeling of gepubliceerd werk.
- Published work blijft immutable; live v1 kan naast working v2 bestaan; publicatie vervangt de serving-release atomair; maximaal één actieve release per LogicalDocument; ingetrokken inhoud blijft buiten serving na herstart.

### Beleidskeuzes

- Expliciete beslisboomstructuur wordt structureel verwerkt; vrije tekst mag semantische voorstellen krijgen binnen hetzelfde contract.
- Geen automatische stille terugval naar legacy bij modeluitval. Een fout blijft zichtbaar; bronmateriaal blijft beschikbaar voor bestaande menselijke verwerking.
- Onzekerheid leidt tot review of een begrensde vervolgpoging. Twee uitvoeringspogingen per onopgelost bereik is een voorgestelde startlimiet, geen domeinwaarheid.
- Scheiding in kleinere modelaanvragen pas invoeren bij bewijs dat de huidige omvang of dekking daarom vraagt. De 200–500 tokens/200 woorden uit Alexandria worden geen standaard voor Metis.
- De kleinste betekenisvol complete passage is het uitgangspunt; een zin of alinea is geen verplichte objectgrens. Noodzakelijke context mag groter zijn dan de kernpassage.
- Tabellen, procedures, formules en beslisbomen behouden hun betekenisdragende structuur. Waar omzetting niet ondersteund wordt, blijft een herleidbare bronrepresentatie met zichtbaar open beoordelingswerk beschikbaar; geen geforceerde omzetting naar losse feitjes of automatische uitsluiting. Nieuwe ondersteuning mag geen publicatieomweg creëren.
- Scheiding van zoekeenheid en kennisobject blijft een mogelijke latere retrievalstudie. Geen nieuwe embedding-, generatie- of kennisgraafroute toevoegen aan deze migratie.

### Nog te toetsen

De kwaliteit en correctietijd van beide voorstelmethoden; de toereikendheid van het huidige typecontract; de omvang van een geschikt referentiecorpus. Deze aannames blokkeren het schrijven van contract en meting niet, maar wel het uitfaseren van een methode zonder vervangende functionaliteit.

## 5. Autoriteiten, aanroepers en grenzen van de inventarisatie

Gecontroleerde paden in deze codeversie:

- `OperationsConsole._fragments_and_spec`: standaard vrije-tekstvoorbereiding en beslisboomtak.
- `bind_pre_review_semantic_processing`: routebinding bij ASGI en CLI; de backendmethode wordt per instantie vervangen.
- Nieuwe verwerking en `reextract_unpublished`: transformeren en roepen `apply_admission_gate` aan.
- `_reextract_objects_for_klasse`: herverwerking bij klassewijziging; bevat een directe `_spec_from_fragments`-aanroep bij conversie vanuit een beslisboom. Ook dit pad moet het nieuwe contract gebruiken.
- `correct_object`: kan toelating opnieuw toepassen na correctie. Contractselectie mag hier niet onbedoeld v1-bewijs als v2 behandelen.
- `deterministic_review_repair_v1.source_fragment_catalog`: gebruikt `_fragments_and_spec`; de semantische binding onderdrukt modelgebruik voor deze read-only catalogus.
- Routevergelijking roept de twee bestaande passagevormers direct aan, buiten gewone Review.
- Frozen semantic safety gebruikt de deterministische splitter als baseline.
- De semantische route gebruikt dezelfde splitter voor koppen.

Opslagtopologieën: de code bevat PostgreSQL-adapters en lokale runtimepaden, met combinatieregels in `console_asgi.py`. De daadwerkelijke productieconfiguratie is hier niet vastgesteld. Fase 0 legt de ondersteunde combinaties en CLI/service-ingangen expliciet vast. Geen volledige decommission claim zonder zo'n manifest en bereikbaarheidstest.

## 6. Expliciet legacyregister

De namen hieronder zijn voorgestelde engineeringstatussen, geen nieuwe documentlevenscyclus. De onderzoeksartikelen wijzigen de acht legacy-items niet. Hun vervanging moet voortaan ook de expliciete toetsen op betekenisbehoud hieronder doorstaan; legacy uitzetten is nooit een manier om resterend curatiewerk te laten verdwijnen.

- **ACTIVE:** ondersteunde doelarchitectuur.
- **LEGACY-FROZEN:** oud gedrag; uitsluitend compatibiliteit, vergelijking en tijdelijk begrensde rollback. Geen nieuwe functionaliteit.
- **LEGACY-READ:** historische resultaten leesbaar; nieuwe uitvoeringen via dit pad verboden.
- **REMOVED:** code verwijderd na aantoonbaar nul noodzakelijke aanroepers; historisch bewijs blijft leesbaar via ondersteunde lezers.

| ID | Bestaand pad / gedrag | Status in plan | Vervanging en moment |
|---|---|---|---|
| L01 | Vrije tekst via `_spec_from_fragments` → `split_context_aware_units` → oude type-/relatieheuristiek als zelfstandige productieroute | LEGACY-FROZEN | Eén voorstelproces met gedeeld contract. Na acceptatie G1–G4 geen nieuwe productieopdrachten; alleen vergelijking/rollback tot afsluiting rollbackvenster. Daarna LEGACY-READ voor oude resultaten. |
| L02 | Semantische v1-opdracht en v1-schema in `pre_review_semantic_v1`, zonder veldbewijs/dekkingsverantwoording | LEGACY-FROZEN | V2-voorstelcontract met bronverwijzingen. Oude uitvoer en replay leesbaar houden; na cutover geen nieuwe v1-inferentie in gewone verwerking. |
| L03 | `_enrich_from_text` / `_enrich_recommendation` als verplichte herinterpretatie van een semantisch voorstel | LEGACY-FROZEN, alleen rol als automatische invuller | V2-producent levert veldbewijs; toelating controleert het. V2 mag deze invuller niet aanroepen. V1-lezer/validator blijft versiegebonden beschikbaar waar nodig. |
| L04 | Globale keuze `deterministic-v1` versus `semantic-source-bound-v1` als normale productbesturing | LEGACY-FROZEN | Eén ondersteund proces; interne methodekeuze volgens bronstructuur. Oude configuratiewaarden uitsluitend expliciete compatibiliteit/rollback; na venster duidelijke configuratiefout, geen stilzwijgende mapping. |
| L05 | Herstelcatalogus via volledige specvorming plus `semantic_suppressed` als omweg | LEGACY-FROZEN | Read-only broncatalogus rechtstreeks via extractie/reconstructie. Daarna omweg verwijderen; de menselijke herstelfunctie zelf blijft ACTIVE. |
| L06 | Afzonderlijke v1-uitvoerders in `route_comparison_app_v1.execute_arm` | LEGACY-FROZEN als adapters | Vergelijkingsfunctie blijft ACTIVE. Nieuwe pogingen gebruiken dezelfde producenten en contractversies als productie; oude armen alleen historische baseline. Geen tweede implementatie van productiegedrag. |
| L07 | `semantic-replay-v1` hergebruik voor oude contracten | LEGACY-FROZEN voor oude writes, LEGACY-READ na cutover | Replaymechanisme blijft ACTIVE; v2-identiteit bindt schema, prompt, bron en model. V1-records nooit als v2-cachehit gebruiken of achteraf aanvullen alsof bewijs destijds bestond. |
| L08 | Impliciete deterministische specvorming bij klasseconversie in `_reextract_objects_for_klasse` | LEGACY-FROZEN voor deze aanroep | Klassewijziging behoudt bestaande bevoegdheden en levenscyclus, maar gebruikt hetzelfde contract. Geen omweg om nieuwe validatie te ontwijken. |

Niet als geheel op legacy zetten:

| Onderdeel | Status en reden |
|---|---|
| Extractie, `source_reconstruction_v1`, locator-/broncontrole | ACTIVE; gedeelde basis. |
| Beslisboomroute, `boom_spec_from_fragments` | ACTIVE; expliciete bronstructuur draagt eigen domeinwaarde. |
| Deterministische kopvorming | ACTIVE; gebruikt nu code uit de splitter. Hergebruik veilig losmaken vóór verwijderen van L01-modules. |
| `semantic_passage_v1` bronvalidatie en reconstructie | ACTIVE mechanismen; versiegebonden contractdelen vervangen. Niet modulebreed verwijderen. |
| `admission_gate_v1` toelatingsfunctie | ACTIVE; alleen de oude invulrol L03 wordt legacy. |
| `context_scan_v1` | ACTIVE als ondersteunend signaal; geen bewijs dat context volledig is opgelost. V2-context moet verifieerbaar worden gekoppeld. |
| `candidate_eligibility_v1` en passage-register | ACTIVE domeinfuncties; naar versiegebonden gedeelde bewijsregels brengen, met historische compatibiliteit. |
| Menselijke review, correctie en deterministische repair | ACTIVE; nooit uitfaseren alleen vanwege het woord deterministisch. |
| Routevergelijking, frozen safety suite, verwerkingsexport | ACTIVE kwaliteitsinstrumenten; adapters aanpassen en historische resultaten bewaren. |
| Retrieval en publicatie | Buiten deze migratie; geen legacylabel zonder afzonderlijke noodzaak. |

In uitvoering krijgt ieder L-item: eigenaar, vervangende slice, resterende aanroepers, contractversie, deprecation-release, laatste toegestane writer en verwijdercriterium. Leg dit vast in `docs/LEGACY_ROUTES.md` en een klein machineleesbaar register. Een beperkte architectuurtest verbiedt nieuwe productie-imports van uitgeschakelde adapters. Labels alleen zijn onvoldoende: dispatcher, configuratie en alternatieve ingangen moeten het gebruik daadwerkelijk blokkeren.

## 7. Toestanden, transacties en herstel

Gebruik bestaande WorkingRevision-toestanden: `processing`, `in_review`, `blocked`, `ready_for_publication`, `closed`. Verwerkingsbewijs is geen tweede reviewstatus. Een geslaagde modelaanroep maakt een werkrevisie niet publicatieklaar.

Voorgestelde commandosemantiek:

1. Een bevoegde actor start voorbereiding op een open werkrevisie met verwachte revisie en request-ID. Bewaar poging en contractbinding vóór de externe aanroep.
2. De modelaanroep loopt buiten een langdurige databasetransactie. Bewaar ontvangen aanvraag-/responsebewijs met bron- en pogingbinding; sluit credentials en autorisatieheaders uit.
3. Valideer een complete voorstelset. Leg objecten, brondekking, bewijslinks en bijbehorende workflowwijziging atomair vast via de bestaande workflowgrens. Bestaande review-invalideringsregels blijven leidend.
4. Bij een versieconflict wordt de set niet toegepast. Het pogingbewijs blijft beschikbaar; de gebruiker kan opnieuw voorbereiden op de actuele basis.
5. Bij time-out of ongeldige uitvoer blijft bestaande curatorarbeid intact. Een retry gebruikt een nieuwe poging onder hetzelfde commando; een reeds gecommitteerd commando retourneert hetzelfde resultaat.
6. Bij crash na responseopslag maar vóór toepassing kan validatie/toepassing worden hervat. Bij een crash vóór responseopslag is een herhaalde externe aanroep mogelijk; beloof geen exactly-once provideruitvoering. Wel maximaal één lokale toepassing.
7. Volledige herverwerking van reeds beoordeelde inhoud volgt het bestaande expliciete werkrevisie-/herbeoordelingspad. Gepubliceerd werk wordt niet in-place herverwerkt.

Bewaar operationele poginglogs apart van domeinbesluiten. Toepassen van een voorstelset en menselijke correcties krijgen een auditkoppeling naar exacte versies. Rolgebaseerde toegang voor bron- en modelbewijs blijft minimaal dezelfde als voor het brondocument. Geen nieuw onbeperkt bewaarbeleid; sluit aan op bestaande retentie en voorkom verwijdering van bewijs dat nog nodig is voor reproduceerbare besluiten.

## 8. Implementatieslices en acceptatiepoorten

### Fase 0 — Bereik en contract vastzetten

Lever een ADR, bijgewerkt legacyregister en writer/reader-map op. Pin de werkelijk te wijzigen GitHub-commit vóór coderen. Inventariseer web/ASGI, CLI, service/product-API, herextractie, klassewijziging, correctie, herstel en tests. Leg de ondersteunde opslagconfiguraties vast. Iedere route krijgt een bestemming uit het register.

**G0:** geen ongeclassificeerde writer naar kandidaatvorming; bestaande publicatie- en reviewbevoegdheden zijn beschreven. Alleen documentatie opleveren is nog geen productcutover.

### Slice 1 — Een beoordelaar kan één brongebonden voorstel volledig controleren

Implementeer het gedeelde v2-contract en laat veldtekst uitsluitend uit bronbereiken ontstaan. Pas semantische producent, reconstructie, toelating, reviewweergave en export samen aan. Gebruik de screeningpassage als positief onderzoeksgeval en een beschrijvende passage als negatief geval. Een ontbrekend gegeven blijft expliciet zichtbaar.

**G1:** vrije modeltekst wordt afgewezen; technisch ongeldig bewijs wordt geblokkeerd; de reviewer ziet bron, betekenisvoorstel, kwalificaties en ontbrekende onderdelen. Inhoudelijk onvoldoende bewijs wordt in de referentiegevallen herkend en blijft zonder vereist menselijk akkoord buiten publicatie; bronvalidatie alleen mag dit niet als opgelost presenteren. Een inhoudelijk geldige passage hoeft niet zonder verdere domeinbeslissing automatisch alle huidige eisen te passeren.

### Slice 2 — De beoordelaar ziet wat van de bron is behandeld

Voeg bereikdekking, onzekere delen en contextafhankelijkheden toe. Bewaar input, output, stopreden, tokengebruik en contract-/codeversie voor nieuwe pogingen. Maak onderscheid tussen technische voltooiing, volledige administratieve dekking en inhoudelijke juistheid. Meet naast de afhandeling van bronbereiken ook het behoud van relevante uitspraken en hun beperkingen ten opzichte van de menselijke referentie. Een bereikstatus bewijst geen inhoudelijke volledigheid. Verbeter tevens de begin/eindlocators en normaliseer het grote revisietoken in de export naar één manifestvermelding plus korte verwijzingen.

**G2:** niet-geselecteerde tekst blijft zichtbaar; een afgebroken of onvolledige respons wordt niet als complete verwerking toegepast; contextverlies wordt in referentiegevallen gevonden. Historische ontbrekende traces worden niet gefabriceerd.

### Slice 3 — Structuurbron en vrije tekst gebruiken hetzelfde beoordelingscontract

Breng de structurele producent en semantische producent achter dezelfde bestaande verwerkingsgrens. Houd beslisbomen op hun expliciete structuurroute. Leg voor tabellen, procedures en formules vast wat nu ondersteund is en hoe niet-ondersteunde structuren brongetrouw beschikbaar blijven voor curatie. Behoud koppen, kolom-/rijverbanden, volgorde en voorwaarden waar die de betekenis bepalen; vlak deze niet stilzwijgend af. Lever waar regels niet voldoende betekenisbewijs geven bronpassages voor review met onbekende velden. Koppel de broncatalogus los van specvorming. Gebruik dezelfde producenten voor kwaliteitsvergelijking.

**G3:** web, CLI, herextractie, klassewijziging en correctie kunnen het contract niet omzeilen; openen van de broncatalogus triggert geen modelaanroep; objecten en menselijke besluiten blijven stabiel waar dit contractbehoud vereist.

### Slice 4 — Vergelijk de inhoudelijke waarde en schakel gecontroleerd om

Stel vóór vergelijking een menselijke referentieset vast. Voorstel: minimaal 40 passages verdeeld over ten minste 4 documenten, met PDF/HTML, koppen, opsommingen, definities, negatieve aanbevelingen, voorwaarden, uitzonderingen en paginagrenzen; voeg beslisboomfixtures toe. Dit is een startacceptatieset, geen bewijs van algemene betrouwbaarheid.

Vergelijk blind: v1-baselines, v2-structureel en v2-semantisch waar toepasbaar. Meet correcte voorstellen, gemiste uitspraken, foutieve types/relaties, ontbrekende context, correctietijd en uitvoeringskosten. Rapporteer absolute aantallen en beoordelingsverschillen.

Breid de startset uit met gecontroleerde contrastparen: dezelfde uitspraak met/zonder ontkenning; een uitzondering in de volgende alinea; associatie versus causaliteit; hypothese versus bevinding; veranderde getallen, eenheden, doelgroep of tijd; een tabel waarvan een kolomkop de waarde kwalificeert; en een foutief eerder modelvoorstel dat als context wordt meegegeven. Gebruik synthetische contrasten naast echte brongevallen en label ze als testmateriaal.

Beoordeel fouten in beide richtingen:

- **Weglating:** relevante uitspraak, uitzondering of noodzakelijke context ontbreekt.
- **Toevoeging/vervorming:** niet-onderbouwd type, relatie, zekerheid, toepassingsgebied of numerieke betekenis verschijnt.

Definieer vooraf welke fouten kritisch zijn en tel die afzonderlijk. Laat kritieke gevallen door twee beoordelaars onafhankelijk toetsen en geschillen expliciet beslechten. Houd een deel van de referentiegevallen buiten prompt- en regelontwikkeling; rapporteer resultaten per brontype en foutsoort, niet alleen één gemiddelde.

Meerkeuzevragen kunnen aanvullend downstream-bruikbaarheid onderzoeken met oorspronkelijke bron, voorbereide representatie en zonder context. Laat antwoorden daarbij ook bronbewijs aanwijzen. Goede antwoorden bewijzen geen volledige extractie: voorkennis kan ontbrekende informatie maskeren. Embeddinggelijkenis, modelconfidence, administratieve dekking en MCQ-scores zijn daarom geen zelfstandige toelatings- of cutovercriteria.

**G4:** nul verzonnen objecttekst, nul ongeldige bronverwijzingen, nul gemiste kritieke beperkingen en nul kritieke betekenisversterking of -vervorming in de vooraf afgesproken releasefixtures; geen achteruitgang op relevante selectie en correcte voorstellen tegenover de gekozen baseline; aantoonbare vermindering van correctietijd of verhoging van kwaliteit voor het bronsegment waarvoor de methode wordt ingezet. Een kleine set bewijst geen foutloosheid; tegenvallende resultaten blokkeren de cutover voor dat segment.

### Slice 5 — Legacy afdwingen en opruimen

Schakel v1-writers voor nieuwe productievoorbereiding uit zodra G0–G4 en de herstelproef slagen. Toon oude resultaten als historische contractversies. Behoud een expliciet rollbackvenster van twee aantoonbaar stabiele releases; dit is een voorstel voor releasebeleid. Daarna vervallen runtime rollback-writers en configuratieopties; historische readers blijven zolang opgeslagen v1-data ze nodig heeft.

**G5:** alle L-items hebben aantoonbaar alleen de toegestane aanroepers; geen stil fallbackpad, directe klasseconversie-bypass of oude CLI-writer. Verwijder pas bestanden nadat kopvorming, herstel, tests en historie geen noodzakelijke afhankelijkheid meer hebben.

## 9. Migratie, rollback en bewijs tegen regressies

Rewrite target: voorstelvorming en het gedeelde contract tussen producent, toelating en review. Een lokale extra regex lost de ontbrekende dekkingsverantwoording en verschillen in bewijscontract niet op. Geen herbouw van publicatie of retrieval.

Migratie volgt expand → gecontroleerde cutover → contract. Nieuwe v2-data krijgt expliciete versie; oude data blijft v1. Geen automatische backfill van betekenisvelden, geen herhashing van gepubliceerde historie, geen dual-write naar twee objectautoriteiten.

Rollback betekent: nieuwe v2-opdrachten stoppen en eventueel expliciet v1-voorbereiding voor ondersteunde oude contexten hervatten. V2-resultaten en review mogen niet door een oude binary worden geïnterpreteerd alsof zij v1 zijn. Een rollbackrelease moet beide readers kennen; anders alleen nieuwe verwerking pauzeren en compatibele read/review-functionaliteit behouden. Geen schema-downgrade met dataverlies.

| Aanval / fout | Vereist bewijs |
|---|---|
| Vrije tekst of onbekend modelveld | Voorstel afgewezen; niets toegepast. |
| Letterlijke selectie mist 'tenzij', doelgroep of negatie | Inhoudelijke fixture faalt ondanks geldige offsets. |
| Hypothese wordt feit of associatie wordt causaliteit | Voorstel faalt de betekenisbehoudtoets; geen automatisch menselijk akkoord. |
| Juiste cijfers met verkeerde eenheid, tijd of kolomkop | Numerieke/structurele betekenisfout wordt apart geteld en blokkeert de toepasselijke releasepoort. |
| Foutief modelvoorstel wordt context van volgende poging | Nieuwe bewijsverwijzing moet naar oorspronkelijke bron leiden; afgeleide tekst alleen is onvoldoende. |
| Goede MCQ-score bij ontbrekende bronuitspraak | Volledigheidstoets blijft falen; antwoordscore heft dat niet op. |
| Ruwe response aanwezig, toepassing crasht | Hervatten zonder dubbele objectset. |
| Dubbel commando of gelijktijdige review | Eén toepassing; stale basis krijgt conflict; menselijke arbeid behouden. |
| Oude replay met nieuwe prompt/schema | Geen cachehit; oude historie intact. |
| CLI, klassewijziging of repair omzeilt dispatcher | Zelfde contractcontrole of expliciete legacyweigering. |
| Modeluitval | Zichtbare mislukking; geen stille omschakeling. |
| Nieuwe revisie naast gepubliceerde release | Gepubliceerde hashes en actieve serving blijven gelijk tot bestaande publicatieovergang. |
| Intrekking en herstart | Ingetrokken inhoud blijft niet-actief. |
| Rollback met aanwezige v2-data | Geen verkeerd lezen, herinterpretatie of verlies van review. |
| Lokale testopslag versus ondersteunde PostgreSQL-configuratie | Dezelfde functionele invarianten, bewezen per ondersteunde topologie. |

Vóór merge van de high-risk cutover volgt een afzonderlijke adversarial review volgens repositorybeleid. Dit is een reviewverplichting voor uitvoering, geen uitgevoerde review in dit document.

## 10. Definitie van gereed

Het programma is pas gereed wanneer één ondersteund kandidaatproces end-to-end werkt, de waarde per bronsegment is gemeten, alle legacy-writers aantoonbaar begrensd of uitgeschakeld zijn, historie leesbaar blijft en fout/herstel/rollback geen review of publicatiewaarheid kan wijzigen.

De oorspronkelijke gebruikersbelofte is aantoonbaar behouden: exact uit de bron, technisch gecontroleerd, inhoudelijk gecureerd en alleen via de bestaande bevoegdheden gepubliceerd. Een nieuw scherm, een groen testsuite-resultaat of het woord LEGACY boven een module is op zichzelf geen voltooiingsbewijs. Iedere verwijdering moet worden gekoppeld aan een vervangend gedrag en een geslaagde acceptatiepoort.

## Gecontroleerde codebronnen

`src/pre_review_semantic_v1.py`, `src/semantic_passage_v1.py`, `src/semantic_replay_v1.py`, `src/passage_formation_policy_v1.py`, `src/operations_console_v1.py`, `src/operations_console_app.py`, `src/console_asgi.py`, `src/cli.py`, `src/admission_gate_v1.py`, `src/context_scan_v1.py`, `src/candidate_eligibility_v1.py`, `src/context_aware_split_v1.py`, `src/atomic_split_v1.py`, `src/semantic_transform_generic_v1.py`, `src/deterministic_review_repair_v1.py`, `src/route_comparison_app_v1.py`, `src/audit_semantic_safety_v1.py` en de repositorycontracten voor continuous development en lifecycle VSA. Dit is een afgebakende inventarisatie van de verwerking; geen audit van alle HTTP-routes van Metis.


## 11. Onderzoeksbasis: wat wel en niet is overgenomen

Deze artikelen leveren ontwerpaanwijzingen en evaluatievragen. Zij bewijzen niet dat de voorgestelde Metis-route werkt. De lifecycle, opslagautoriteiten en legacybesluiten komen uit de Metis-domeinlogica en codeanalyse.

### Dense X Retrieval

Chen, T. et al. (2024). *Dense X Retrieval: What Retrieval Granularity Should We Use?* EMNLP 2024. Gelezen versie: arXiv:2312.06648v3, 4 oktober 2024. Bronbestand: `2312.06648v3.pdf`.

- Onderzoeksresultaat: kleinere proposities verbeteren retrieval en downstream-vraagbeantwoording in de onderzochte Engelstalige Wikipedia-opzet. Zie §2–4 en de experimentele resultaten.
- Overgenomen als ontwerphypothese: betekenisvol begrensde eenheden verdienen evaluatie; noodzakelijke context blijft onderdeel van de betekenis. Verwerkt in §3, §4 en Slice 4.
- Niet overgenomen: het herschrijven van bronzinnen en vervangen van voornaamwoorden door modelgegenereerde tekst (figuur 8). Metis gebruikt bronselecties en broncontext.
- Begrenzing: tabel 2 rapporteert niet-brongetrouwe proposities bij 3/408 GPT-4- en 6/445 Propositionizer-uitkomsten in 50 passages. Appendix C telt alleen 'nee', niet twijfelgevallen. Dit is geen veiligheidsnorm voor Metis en geen bewijs van foutloosheid bij richtlijnen.
- Buiten scope: een aparte kleinere zoekindex met terugkoppeling naar volledige kennisobjecten; alleen onderzoeken in een latere retrievalopdracht.

### Project Alexandria

Schuhmann, C. et al. (2025). *Project Alexandria: Towards Freeing Scientific Knowledge from Copyright Burdens via LLMs.* Gelezen versie: arXiv:2502.19413v2, 18 april 2025. Bronbestand: `2502.19413v2.pdf`.

- Onderzoeksopzet: gegenereerde Knowledge Units met entiteiten, relaties en attributen; context uit eerdere units. Zie §2. Metis neemt de vrije herformulering en afgeleide context als bewijs niet over.
- Bewijsgrens: de circa 95%-claim steunt op MCQ-prestaties, niet op een volledige controle van alle bronuitspraken. §4 gebruikt drie vragen per abstract en tien per volledig artikel. Tabel 3 rapporteert bijvoorbeeld voor Gemini bij medische volledige artikelen 94,13% met brontekst versus 81,76% met KUs. Die 12,37 procentpunt verschil bewijst niet welke feiten ontbreken, maar rechtvaardigt geen claim van verliesloze omzetting.
- Overgenomen: afzonderlijke toetsen op informatieverlies, niet-onderbouwde toevoegingen, bronattributie en complexe structuren; vastgelegd in §3–4, Slices 1–4 en de regressiematrix.
- Mogelijk risico, geen aangetoonde frequentie: fouten kunnen via eerder gegenereerde context doorwerken. Daarom mag bewijs uitsluitend op de oorspronkelijke bron rusten.
- De auteurs erkennen in §5.2 beperkingen bij complexe procedures, tabellen en bewijzen en noemen het een position paper met prototype. Dit ondersteunt een begrensde, empirisch getoetste invoering; niet het opbouwen van een generieke kennisgraaf.
- Niet overgenomen: hun juridische standpunt als toestemming voor Metis-gebruik, een beleid om bronmateriaal te verwijderen, vrijgave op basis van lage tekstoverlap of automatische publicatie van afgeleide kennis. Bestaande bronrechten, retentie en publicatiebevoegdheden worden hiermee niet gewijzigd.

### Traceerbaarheid van deze aanscherping

| Les / grens | Gevolg voor uitvoering |
|---|---|
| Kleine eenheid is niet automatisch complete betekenis | Bronselectie met noodzakelijke context; geen vaste minimale lengte als kwaliteitsbewijs. |
| Exacte woorden kunnen een andere strekking krijgen | Bronbinding en betekenisbehoud afzonderlijk toetsen; reviewer ziet beide. |
| Gestructureerde uitvoer kan alsnog eigen interpretatie bevatten | Gesloten labels met bronbewijs; geen vrije tekst in kennisvelden. |
| Bronbewering is niet automatisch vastgestelde waarheid | Onzekerheid, toeschrijving en toepassingsgrenzen behouden. |
| Bereikdekking en QA-score tonen geen volledige inhoudsdekking | Menselijke referentie, contrastparen, foutsoorten en gereserveerde evaluatieset. |
| Beide papers gebruiken generatieve omzetting | De Metis-grens blijft selecteren, structureren en laten cureren; geen generatieve vervanging van bronkennis. |
