# Implementatieplan voor snellere verwerking in Metis

Datum: 7 november 2026. Status: uitvoeringsplan en Architect-ontwerpschets; productimplementatie nog niet uitgevoerd.

Change class: C
Promise: de prestatieaudit vertalen naar geordende, toetsbare implementatiestappen en volgens het handoffprotocol registreren.
Proof: broncontrole, vergelijking van twee ontwerpen, afzonderlijke ontwerpbeoordeling en volledige dekking van de auditpunten; document- en PR-contractvalidatie bij registratie.
Touches lifecycle invariants: no
Rewrite risk: none

De classificaties bij de werkpakketten gelden voor hun latere implementatie. Dit document is het repositorycontract bij [GitHub #959](https://github.com/WilliamGomes41/Metis-DS/issues/959), primair gekoppeld aan [MET-45](https://linear.app/metis-phoenix/issue/MET-45/959-projectoverzicht-begrensd-lezen-en-schrijven). Het vult het bestaande projectcontract aan; oorspronkelijke domein- en uitvoeringsvoorwaarden blijven gelden.

Registratieopdracht: William vroeg op 7 november 2026 om het Architect-plan volgens het handoffprotocol aan GitHub en Linear te koppelen. Dit legt het ontwerpvoorstel en bewijs reviewbaar vast. Een gedragswijziging, merge of deployment is hiermee niet uitgevoerd of als goedgekeurd vastgelegd.

**Begin met de volledige correctiehandeling `/review/resolve`.** Alle twintig actuele correctiemetingen overschrijden vijf seconden. Bereid de handeling voor binnen de bestaande command-eigenaar, buiten de buitenste schrijftransactie; controleer bij commit de actuele afhankelijkheden en sla correctie, bindings, feiten en bewijs samen op. Optimaliseer daarna het gemeten databasewerk bij vorming. Productiehertests en metingen van gedeelde blokkering kunnen gelijktijdig worden voorbereid.

Dit plan bouwt voort op de [prestatieaudit](../audit/performance-2026-11-07.md) en haar ruwe meetbewijs. Codebasis: GitHub-main `c4db3bd84bfe722ab235eff67d2ccf69b60a785b`. Bronlinks hieronder wijzen naar die commit; de oorspronkelijke lokale checkout is ouder. Implementatie moet starten op de dan actuele main, met controle van het verschil sinds deze basis.

## Probleem en bestaande architectuur

| Bevinding | Bewezen uitgangspunt | Consequentie voor het plan |
| --- | --- | --- |
| A1, P1 | Correctie: mediaan 6,075 s, p95 6,356 s; 20/20 boven 5 s; 1.087 queries en circa 260 MB gedecodeerde DB-JSON per correctie | Eerste volledige gebruikershandeling om te optimaliseren; geen netwerkbytes uit deze JSON-teller afleiden. |
| A2, P2 | Hervatten van 130 vormingstaken zonder externe AI: vijf runs, mediaan 24,690 s | Database-/checkpoint-/activatiekosten onderzoeken voordat meer modelwerk tegelijk wordt uitgevoerd. |
| A3/A4, P1 hertest | Oudere productieproblemen; huidige main bevat al gerichte bronreuse- en reviewverbeteringen | Draaiende versie en productie-effect vaststellen; dezelfde fixes niet opnieuw bouwen. |
| A5/A6, P2 | Historisch langdurige modelvorming en conditionele Docling-extractie | Transport, lokale verwerking en wachtrij apart meten; totale documentduur blijft een eigen maat. |
| R1–R12 | Actuele codebevindingen zonder bewezen >5s-duur | Eerst meten; alleen het aangetoonde probleem krijgt een implementatieslice. |

De workflowdatabase bezit de werkrevisie, objecthistorie, reviewbindings en audit. Immutable bronopslag bezit bronidentiteit en bytes. Het canonieke publicatieregister bezit releases en de actieve serving-set. Afgeleide kaarten, frontiers, indexen en caches krijgen geen beslissingsbevoegdheid. `materialise_knowledge_candidates` blijft de enige pre-review kandidaatmaker.

De bestaande prepared review-uitvoering capturet consistente invoer, voert de oorspronkelijke kernel zonder workflow-I/O uit en controleert vóór de atomaire write de actuele afhankelijkheden. Die techniek bestaat al; de correctie heeft eigen autorisatie, admission-afhankelijkheden, bewijs en resultaatvorm.

Een aanvullende broncontrole tijdens Architect is bepalend: [submit_review_resolution](https://github.com/WilliamGomes41/Metis-DS/blob/c4db3bd84bfe722ab235eff67d2ccf69b60a785b/src/review/deterministic_review_repair_v1.py#L731) opent op regel 788–792 de **buitenste transactie**. Daarbinnen wordt de ingediende volledige objectsetrevisie gecontroleerd. [_source_repair](https://github.com/WilliamGomes41/Metis-DS/blob/c4db3bd84bfe722ab235eff67d2ccf69b60a785b/src/review/deterministic_review_repair_v1.py#L428) roept `correct_object` zonder `expected_revision` aan en schrijft daarna discrepancy- en reparatiebewijs. Alleen voorbereiding buiten de innerlijke correctielock verplaatsen laat dus werk binnen de buitenste transactie staan.

## Gebruik vanuit de aanroeper

De bestaande publieke operaties blijven de grens. De HTTP-handler of worker gaat geen losse prepare-, validate- en commitmethoden orkestreren. Onderstaande voorbeelden gebruiken bestaande signatures; de waarden komen uit de bestaande gevalideerde invoer.

```python
# De werkelijk gemeten correctiehandeling; dezelfde response en 303-navigatie.
corrected = console.submit_review_resolution(
    actor_id=actor_id, snapshot_id=snapshot_id, object_id=object_id,
    expected_revision=shown_revision, suitability=suitability,
    comment=comment, repair_kind=repair_kind,
    source_unit_ids=selected_source_units,
    source_discrepancy=source_discrepancy,
)

# Bestaande hervatting: reeds gecommitteerde taken blijven herbruikbaar.
receipt = console.execute_source_selection(
    actor_id=actor_id, snapshot_id=snapshot_id, attempt=attempt,
)

# Bestaande publicatie en herstelregels.
release = console.publish(actor_id=publisher_id, snapshot_id=snapshot_id)
```

Directe callers van `correct_object` behouden hun huidige signature, optionele revisiestring en object-/documentherbeoordeling. Een onderzoeker behoudt zijn eigen bevoegdheden; de reviewerregels worden niet zonder meer op hem toegepast. De generation-, m2-, None- en receiptvarianten van gewone Review behouden hun afzonderlijke betekenis. Ze worden niet als nieuwe invoervarianten voor correctie geïntroduceerd.

## Gekozen ontwerp en typeschets

**Operatiegericht voorbereiden bij de bestaande eigenaar** vormt de basis. Begrens invoer op de werkelijk benodigde afhankelijkheden, hergebruik immutable broninvoer binnen de geldige capture en laat de huidige kernel beslissen. Onder de bestaande beschermde commit worden alle veranderlijke afhankelijkheden opnieuw gecontroleerd. SQL-groepering blijft een interne techniek van de bestaande writer.

Dit is een conceptuele schets, geen uitvoerbare of toegevoegde productcode:

```python
# Voorstel: private, immutable invoer voor de eerste source-units-variant.
# Normalisatie/validatie blijven bij de bestaande resolution-ingang.
@dataclass(frozen=True)
class _SourceResolutionRequest:
    actor_id: str
    snapshot_id: str
    object_id: str
    expected_revision: str        # volledige objectset, geen nieuw token
    suitability: str
    comment: str
    source_unit_ids: tuple[str, ...]
    source_discrepancy: tuple[str, ...]

# Voorstel: private ingress binnen de bestaande commanduitvoering.
# Omvat correctie plus discrepancy-/repair-evidence; geen losse commit voor callers.
def _execute_prepared_source_resolution(
    console, request: _SourceResolutionRequest,
) -> dict[str, Any]:
    raise NotImplementedError

# Bestaand, te hergebruiken: één capture, één staged veranderingenset.
ReviewCommandInputs   # immutable bron-/historie-/actor-/bindingsinvoer
ReviewChangeSet       # requestgebonden staging, niet duurzaam en geen authority
RevisionWindow        # door bestaande eigenaar gecertificeerde historie-invoer

# Bestaande fysieke opslaggrens; signatures blijven gelijk.
def write(store, con, sid, before, following) -> VerifiedObjectDelta: ...
# VerifiedObjectDelta.seal(self, store, con, sid, current)
```

De eerste private ingress betreft de gemeten source-units-correctie. Andere repairvarianten blijven onder hun bestaande contract totdat hun eigen volledige dependency- en atomiciteitsproef aanwezig is. Dit is een gefaseerde interne omzetting, geen tweede publieke API. De oorspronkelijke kernel en KO-overgang blijven beslissen; geen kopie van correctiebeleid in een nieuwe executor. Het uiteindelijke typeontwerp moet alle daadwerkelijk gelezen commandinvoer bevatten; de schets verleent geen toestemming om een vergeten afhankelijkheid weg te laten.

De capture bevat geordende objecten en de noodzakelijke admission-, relatie- en broncontext. Historische payloads van ongerelateerde objecten hoeven niet opnieuw te worden geladen. Documentbrede herreview of admission kan wel legitiem een documentbrede actuele afhankelijkheid hebben. Dan blijft die expliciet, met gerichte actuele gegevens in plaats van afgekapt beleid. De volledige revisievoorwaarde mag niet worden vervangen door alleen de doelobjectrevisie.

| Bestaande modulegrens | Uit te voeren verantwoordelijkheid |
| --- | --- |
| `review/deterministic_review_repair_v1.py`, `operations_console_v1.py` | Publieke resolution/correctie, autorisatie, oorspronkelijke kernel, bewijsbinding en resultaat. |
| `review/review_command_v1.py`, `review_command_state_v1.py`, `revision_window_v1.py` | Consistente capture, private prepared ingress, actuele guards en integratie met bestaande commit. |
| `workflows/object_delta_postgres_v1.py` en bestaande transaction/concurrency-owners | Fysieke rijcontrole, epochs/frontiers, object-/binding-/fact-/auditwrites en rollback. |
| `vorming/bounded_formation_v1.py`, `formation_checkpoint_v1.py`, bestaande taakstore | Taakidentiteit, bronvolgorde, lease/budget, checkpoint en activatie. |
| `product_api_v1.py`, `product_source_authority_v1.py`, `publication/` | Verse broncontrole, canonieke servingautoriteit, afgeleide projectie en bestaande reconciliatie. |
| Bestaande bron-, ingest-, quality-, telemetry- en exportmodules | Eigen bron- of leescontract; geen algemene performance-service. |

Deze grens verbergt capture, actuele controle en opslag achter één bestaande domeinhandeling. Er komt geen publiek callbackraamwerk, algemene cache of tweede writer bij. Per invariant blijft één eigenaar verantwoordelijk; gelezen afhankelijkheden en commitguards mogen geen twee handmatig bijgehouden, uiteenlopende lijsten worden.

## Werkpakketten en volgorde

`W0 → W1` is de eerste implementatielijn. `W2` en de metingen voor `W3` kunnen vanaf W0 parallel lopen. `W4` volgt het databaseprofiel; providerprofilering in W5 kan eerder beginnen, maar extra gelijktijdigheid volgt pas na bewijs dat afhankelijkheden en lokale capaciteit dit toelaten. W6 bestaat uit afzonderlijke kleine wijzigingen. W7 sluit elke geleverde gebruikersbelofte af.

| Werkpakket | Urgentie en eigenaar | Concrete oplevering | Afhankelijkheid |
| --- | --- | --- | --- |
| W0 — meetbasis en versie | P1; #729/#952, acceptatie #953 | Faseprofiel echte correctie; productiecommit; meetdekking voor Product API/publicatie en wachttijd | Bestaande audit hergebruiken |
| W1 — volledige correctie | P1; #729 met #952-tegenproeven | Source-units-resolution met voorbereiding buiten de buitenste transactie en één atomaire commit | W0, dependencyanalyse van deze variant |
| W2 — bestaande fixes hertesten | P1; #887/#729/#953 | Productie-uitkomst voor A3/A4 op exact bekende release | Deploymentidentiteit en toegankelijke meetomgeving |
| W3 — serving, publicatie en bron-I/O | R1/R2 eerst P1; #959 coördineert bestaande module-eigenaren | Gemeten, afzonderlijke verbeteringen voor R1/R2/R3/R4/R9/R10 | Routebaseline; juiste bron-/servinggarantie |
| W4 — lokale vormingskosten | P2; #729, bewijs afstemmen met #952 | Minder aangetoond database-/checkpoint-/activatiewerk met exact hervatresultaat | SQL-server- en driverprofiel uit W0 |
| W5 — model/Docling/capaciteit | P2; #931 | Bewezen veilige begrenzing van gelijktijdig werk, queue- en throughputbewijs | Afhankelijkheden, budgetten en capaciteitsmeting; W4-resultaten meenemen |
| W6 — operationele reads | P2/P3; bestaande module-eigenaren via #959 | Afzonderlijke gerichte wijzigingen voor R5/R6/R7/R8/R12 | Eigen reproduceerbare baseline |
| W7 — integrale acceptatie | P1 voor interactieve hoofdhandelingen; #953 | Versiegebonden lokaal en productieacceptatiebewijs, inclusief herstel | Elke relevante geleverde slice |

### W0 — ontbrekend bewijs gericht aanvullen

Behoud de oorspronkelijke KO4-fixture: 923 alinea's, 924 fragmenten en 92 kandidaten. Meet capture, bron-I/O, admission, JSON/CPU, huidige-controle en commit afzonderlijk, plus echte buitenste lockhold/-wait en transactie. Log geen broninhoud of credentials. Product API en bewust uitgesloten telemetrie-endpoints krijgen onafhankelijke meting zonder recursieve requestlogging.

Voor A2: meet querygroepen, server-executietijd, trigger-/frontierwerk, lockwait en transport apart. Het bestaande profiel van 31,05 s omvat setup, onderbreking en hervatting; de 20,59 s driverwachten en 15,27 s object-deltaschrijven overlappen. Dat profiel rechtvaardigt onderzoek, geen vooraf gekozen SQL-herschrijving.

Leg dataset, commit, configuratie, hardware, PostgreSQL-versie en herhalingen vast. Bewijsdocumentatie is C/none; kleine runtime-instrumentatie B/none zolang gedrag en autoriteit gelijk blijven. Ontbrekende productietoegang blokkeert lokale W1/W4 niet, maar laat productieacceptatie open.

### W1 — één volledige correctie, inclusief bewijs

1. Leg een falende echte HTTP-/browserproef voor `/review/resolve` vast. Traceer de buitenste transactie, ingediende objectsetrevisie en alle writes tot aan de 303. De rode proef moet expliciet aantonen dat bron-/admissionvoorbereiding nog binnen de werkelijke buitenste schrijftransactie valt; de groene proef eist voorbereiding erbuiten. Gebruik niet uitsluitend de al snelle generation-reviewroute.
2. Bepaal de volledige afhankelijkheden van source-units-resolution: doelversie, admissioncontext, relaties, bronpins/fragments, actor, beleid, named reviewers, bindings en ledger. Leg vast welke gegevens alleen actueel en welke historisch nodig zijn. Behoud de bestaande foutvolgorde en bronvalidatie.
3. Bereid de oorspronkelijke correctie en beide bewijsvormen voor buiten de echte buitenste schrijftransactie. Discrepancybewijs blijft aan de bekeken oude versie gekoppeld; repairbewijs aan de opvolger. De bestaande staged buffer bevat de gehele handeling.
4. Controleer binnen de huidige authorization-/document-/ledgergrens de complete actuele afhankelijkheden en exacte objectsetvoorwaarde. Schrijf opvolger, bindinginvalidatie, benodigde feiten en audit samen. Injecteer specifiek een fout na de correctie maar vóór het laatste evidencewrite en bewijs vanuit een verse runtime dat geen deelwijziging duurzaam is. Laat een late COMMIT-fout dezelfde rollback opleveren als een vroege fout.
5. Controleer de directe `correct_object`-callers en andere repairvarianten op compatibiliteit. Geen onderzoeker uitsluiten door reviewer-only hergebruik; documentherbeoordeling mag niet stil objectherbeoordeling worden.

Class A / high, conform bestaande #729/#952-contracten. Eerste gereedcriterium: dezelfde correctie-uitkomst en bewijzen, dezelfde conflict-/weigeringssemantiek, kortere volledige verwerking en alle onderstaande prestatie- en herstelproeven geslaagd. Een sneller innerlijk helperresultaat telt niet als oplevering.

### W2 — al verbeterde productiegevallen verifiëren

Hertest Vormingsproblemen, brede Review, gewone opslag, bronviewer en 400/409-antwoorden met de oorspronkelijke documentvorm op de actuele release. PR #977 heeft bronbevriezing en hergebruik al toegevoegd; gewone opslag/navigatie heeft lokaal bewijs. Geef elke bevinding de status `code geleverd`, `lokaal bewezen` en `productie bewezen` afzonderlijk. Alleen een actuele restoorzaak leidt tot een nieuwe implementatieslice bij de bestaande issue-eigenaar.

### W3 — gedeelde I/O en blokkering

| Risico | Ontwerp na bevestigde meting | Acceptatie en grens |
| --- | --- | --- |
| R1 Product API | Batch canonieke metadata; hergebruik projectie bij exact dezelfde actuele autoritatieve revisie; onderzoek begrensde parallelle bronreads | Verse verificatie van alle vereiste actieve bronnen blijft per aanvraag gelden. Ontbrekende/corrupte bron weigert serving; een TTL vervangt die garantie niet. |
| R2 publicatie | Verplaats uitsluitend aantoonbaar onafhankelijke voorbereiding; meet publicatie tegelijk met Review en signin | Bestaande canonieke beslissing en workflowreconciliatie blijven behouden. Canonieke commit en workflowcommit zijn afzonderlijke grenzen, geen fictieve gezamenlijke rollback. |
| R3 passage | Hergebruik geverifieerde bytes binnen dezelfde consistente passagecapture | Koude cache: één vereiste bronread waar dezelfde verificatie geldig blijft; dezelfde inhoud en weigering; geen herstelwrites vanuit GET. |
| R4 ontvangst | Onderzoek of upload-readbackbewijs de extra readback veilig kan vervangen binnen dezelfde ontvangst | Exacte blobidentiteit, hash en duurzaamheid bewezen vóór receipt; anders verificatie behouden. Aantal transports en bytes vóór/na meten. |
| R9 retrieval | Begrensde afgeleide indexcache met geheugenlimiet | Sleutel bevat corpusrevisie en volledige geautoriseerde selectie; wisselende tenants/filters geven dezelfde resultaten, geen scopelek of stale withdrawal. |
| R10 opstart/herstel | Meet dubbel werk tussen workers en onderzoek coördinatie bij bestaande reconciliatie-eigenaar | Cold start, crash en tweede worker blijven dezelfde canonieke actieve set opleveren; herstel niet overslaan om startup te versnellen. |

Serving-, publicatie- en herstelgrenzen zijn A/high zodra ze materieel wijzigen. Bronhergebruik krijgt per concrete wijziging classificatie: een puur lokale dubbele read verwijderen verschilt van het wijzigen van ontvangst- of bronautoriteit. Eerst de geldigheid van gedeeld bewijs bepalen; niet alle zes risico's in één PR samenvoegen.

### W4 — databasewerk bij vorming

Gebruik het serverprofiel om te kiezen tussen minder reads, minder herhaalde frontierberekening of groepering van bewezen onafhankelijke SQL. De bestaande `object_delta_postgres_v1.write` blijft eigenaar. Ook bij batching moet iedere bedoelde wijziging een exacte identiteit, positie en JSON-payload teruggeven; ontbrekende of gewijzigde writes, onverwachte triggerwrites en mutation-epochs moeten detecteerbaar blijven. Behoud geordende tussentransities en `VerifiedObjectDelta.seal(store, con, sid, current)`.

Per-taak checkpoint, taakidentiteit, lease, budget, bronvolgorde en exacte activatie blijven bestaan. Geen meerdere gecommitteerde taken opofferen om minder commits te tellen. Herhaal dezelfde 130-taakproef vijfmaal op dezelfde baseline-/wijzigingsomgeving; eis gelijk resultaat, dezelfde hergebruikte eerste taak en aantoonbare daling van het geprofileerde kostendeel. Leg een concrete tijd-/query-/bytegrens vast **na het profiel en vóór de patch**, waar een bestaande grens ontbreekt. A/high bij wijziging van de gedeelde writer-/herstelgrens.

### W5 — provider, Docling en wachtrij (A5/A6/R11)

Splits reserve→claim, claim→start, modeltransport, lokale voorbereiding/validatie, checkpoint, activatie en totale documentduur. `provider_seconds` is geen zuivere modeltijd. De huidige `narrow_task`/`source_use.remaining`-logica maakt taken onderling afhankelijk: parallelle uitvoering mag geen bron dubbel verwerken doordat latere taken de eerdere resultaten nog niet kennen.

Start alleen een begrensd parallelisme-experiment nadat onafhankelijkheid of een deterministische uitvoering met dezelfde selectie-uitkomst is bewezen. Behoud annulering, leaseovername, kostenbudget, per-taak duurzaamheid en dezelfde kandidaatmaker. Rapporteer ook totale modelkosten en outputpariteit. Houd de bestaande uitvoering aan als het experiment de semantiek niet kan behouden.

Controleer voor Docling eerst of deze route actief is. Meet koude/warme conversie, geheugengebruik en wachtrij met meerdere documenten voordat de twee dispatcherworkers of ene Docling-slot worden aangepast. Capaciteitswijzigingen zijn B/none als hun semantiek gelijk blijft; duurzame taak-/activatiegrenzen A/high. Auth- en pollingintervallen tellen niet als gemeten runtijd.

### W6 — overige lees- en verwerkingstaken

| Risico | Kleinste zinvolle ingreep na baseline | Bewijs |
| --- | --- | --- |
| R5 URL-ontvangst | Totale downloaddeadline naast sockettimeout, met bestaande grootte- en broncontroles | Langzaam doorleverende bron stopt binnen vastgelegd budget; herstelbare fout en geen onterecht voltooide receipt. |
| R6 kwaliteit | Historisch rapport geautoriseerd selecteren vóór actuele capture; metadatahistorie pagineren; scope van actuele berekening expliciet | Historisch rapport blijft identiek; geen onnodige actuele bron/ledgerreads; toegangscontrole en huidige berekening gelijk. |
| R7 telemetrie | Eerst tijdgerichte bestandsselectie; daarna alleen indien nodig incrementele afgeleide index | Grote retentie en meerdere kijkers: daadwerkelijk minder gescande bytes, correcte rotatie/late events, herstel uit gezaghebbende logs en geen recursieve meting. |
| R8 export | Bounded reads naar tijdelijke opslag met consistente geautoriseerde snapshot; complete ZIP vrijgeven na succes | Zelfde manifest/tabellen/hashes, begrensd piekgeheugen en opruiming bij fout; eerste byte én totale gereedtijd rapporteren. Vroeg antwoord alleen is geen versnelling. |
| R12 auth/PDF/voortgang | Meet aanmeldsucces/fouten, PDF-markering en tijd tot zichtbare afronding afzonderlijk | Alleen aangetoonde kosten aanpakken; identiteit/sessioncontract behouden; pollinterval niet verwarren met jobduur. |

Deze onderdelen zijn doorgaans B/none. Wanneer een ingreep duurzame domeintoestand of een gedeelde autoriteitsgrens raakt, geldt de bijbehorende stateful-B- of A/high-uitwerking vóór de codewijziging. Een ongemeten risico afsluiten met onderbouwd `geen optimalisatie nodig` is een geldige uitkomst.

## Acceptatiecriteria en uitrol

De gebruikersgrens is **strikt meer dan 5,000 seconden**. Rapporteer per route en variant aantallen, aantal >5 s, mediaan, empirische p95 en fouten. Scheid POST, redirect/volgende GET, heropenen en de totale gebruikershandeling; een losse snelle response verbergt geen latere wachttijd. Voor de interactieve correctieketen is ≤5 s totaal de voorgestelde aanvullende gebruikersdoelwaarde, te toetsen op vooraf vastgelegde datasets. De bestaande strengere budgetten blijven: **POST ≤3 s, detail ≤5 s, buitenste lock ≤250 ms, transactie ≤500 ms**.

W1 gebruikt ten minste de oorspronkelijke twintig correcties en twintig approvals met verse workers en afwisselende baseline-/wijzigingsruns. Rapporteer alle overschrijdingen; een p95 onder vijf seconden mag trage individuele gevallen niet verbergen. Meet daarnaast historie-/objectgroei, ongerelateerde documenten, gelijktijdige mutatie, GET en signin. De bestaande schaalproef begint bij minstens 1.500 objectversies. Vijf samples bij A2 geven mediaan/bereik, geen robuuste productie-p95.

Correctheidsbewijs omvat per geraakte variant: broncorruptie/ontbrekende bron, stale objectset, gewijzigde policy/bindings/actor, researcher/reviewer, object-/documentscope, gelijktijdige reviewers, publicatierace, fout na een deelwrite, late commitfout, verloren antwoord en herstart in een verse runtime. Een fout mag geen half objectbesluit of los auditbewijs achterlaten. Behoud bestaande D1-revocation- en receiptregels; geen sterkere exactly-oncebelofte introduceren.

Gebruik de bestaande native PostgreSQL-, command-dependency-, KO4-, delta-/frontier- en lifecycleproeven; voeg alleen ontbrekende gedrag-/tegenproeven toe. De audit gebruikte PostgreSQL 17.11. Voor repositoryacceptatie blijft de vereiste PostgreSQL 16-/CI-validatie gelden. Lokale cijfers worden niet als productieverbetering gepresenteerd.

Iedere slice krijgt één samenhangende PR met haar bronbaseline, belofte, wijzigingsklasse, relevante proeven, voor/na-evidence en rollback. Hergebruik #729, #952, #953, #959, #887 en #931; #942 is alleen een afhankelijkheid waar bronrolconsolidatie aantoonbaar nodig is. Geen nieuwe duplicerende issues of algemene projectblokkade doordat alle andere slices nog niet klaar zijn.

W7 controleert de volledige gebruikershandeling op de werkelijk draaiende commit, binnen een vooraf vastgelegd representatief meetvenster. Zonder actuele productietelemetrie blijft het aantal resterende productieoverschrijdingen onbekend. Achtergrondtaken boven vijf seconden blijven in de rapportage, met queuewait, uitvoeringstijd, throughput en gebruikersimpact; vijf seconden wordt geen universele jobtimeout.

## Eerste slice: lifecycle, migratie en terugval

Deze concretisering maakt W1 reviewbaar. De uitvoerings-PR vult de dependency- en topologiemap aan met de exacte actuele code; onzekerheden worden niet als bewezen optimalisaties behandeld.

| Lifecycleveld | W1-contract |
| --- | --- |
| Lifecycle entity / transition | Ongepubliceerde WorkingRevision; geldige source-units-resolution maakt een opvolger die opnieuw review nodig heeft. |
| Initial durable state / trigger | Bestaand object en bekeken objectsetrevisie; één geldige `/review/resolve`-inzending. |
| Authorization / validation | Huidige resolution/preflightregels; bron, admission, exacte revisie, actor en actuele dependencies blijven doorslaggevend. Directe correctie houdt haar eigen researcher/reviewerregels. |
| Mutable entities | Betrokken werkobjectversies, bindinginvalidatie, geraakte facts en bestaand discrepancy-/repair-/auditbewijs. |
| Immutable entities | Bronbytes/SourceSnapshot, eerdere objectversies, publicatiereleases en gepubliceerd werk. |
| Workflow state before / after | Vóór: bestaande mutable revisie onder huidige voorwaarden. Na: de gerepareerde objectversie heeft `needs_review`; overige effecten volgen exact de bestaande kernel. |
| Release state before / after | Eventuele actieve voorganger blijft dezelfde release; deze handeling maakt geen publicatie. |
| Serving state before / after | Dezelfde canonieke actieve set; correctie verandert serving niet. |
| Expected API / UI result | Zelfde herziene objectresultaat; dezelfde 303-bestemming en zichtbare herreviewuitkomst, sneller. |
| Failure result | Bestaande weigering/conflict; geen deelwrite. 400/409 behouden formulier-/draftgedrag. |
| Restart / recovery result | Verse runtime ziet de volledige geldige correctie of de ongewijzigde/winnende toestand; recovery neemt geen nieuw menselijk besluit. |
| Legacy-data result | Bestaande expliciete serial/ongeprepareerde compatibiliteit; nooit stil een nieuwe precondition eisen. |
| Required black-box scenario | Gegeven mutable bron/object en bekeken revisie: werkelijke correctie indienen, bron/evidence/historie controleren, volgende passage openen en na procesherstart dezelfde duurzame uitkomst lezen; herhaal met conflict en late commitfout. |
| Explicit non-goals / rewrite risk | Geen andere kandidaatmaker, servingpolicy, schema- of contentmigratie, automatische stale-retry of timeoutverhoging. Rewrite risk: high. |

| Rewriteveld | W1-maatregel |
| --- | --- |
| Rewrite target / why local patching is insufficient | Volledige resolution-capture/commitgrens. Een innerlijke helper versnellen verwijdert de buitenste transactie niet en bewijst geen complete correctie. |
| Authority/writer/reader map | Bestaande workflowdocument-/reviewstores zijn authority; resolution en directe correctie gebruiken dezelfde kernel/writer. Ook gewone review, bronreparatie, vormingsactivatie, publicatiebarrière en herstel zijn geraakte tegenlezers/-schrijvers; concrete ingangen inventariseren vóór wijziging. |
| Supported runtime topologies | Beide bestaande PostgreSQL FastBadge-composities en lokale/Azure bronadapter; geen nieuwe multi-hostgarantie. Exacte ondersteunde configuraties in de uitvoerings-PR vastleggen. |
| Persisted-state impact | Aanvankelijk geen schema, identiteit of backfill wijzigen; gewone versies, bindings, facts en events behouden hun formaat. |
| Compatibility/migration | Expand → gemeten variant omzetten → brede fallback voor die bewezen variant afsluiten. Eén kernel en één authority; andere varianten houden expliciete compatibiliteit. Geen GET-migratie. |
| Rollback/recovery | Vorige compatibele binary terugzetten nadat leesbaarheid van nieuwe normale writes is getest. Reeds gecommitteerde besluiten blijven bestaan; geen database-reset. Canonieke commit/projectiefout blijft het bestaande reconciliatiepad. |
| Cutover trigger | Exacte codeversie slaagt voor native keten, huidige-dependency-/fault-/restartproeven, budgetten en afzonderlijke adversariële review. Uitrol volgt het bestaande deploymentprotocol. |
| Cleanup criteria | Elke omgezette ingress gebruikt één route; tijdelijke selectie/fallback verwijderen wanneer de compatibiliteitsmatrix bewezen is. Geen permanent tweede executorpad. |
| Failure blast radius | Correctie, evidencebinding, herreview en andere callers van gedeelde opslag. Grootste risico is schijnbaar succesvolle gedeeltelijke of stale mutatie. |
| Adversarial proof matrix | De in acceptatie genoemde bron-, actor-, dependency-, concurrerende write-, publication-, fault- en restartscenario's, tegen beide runtimecomposities waar relevant. |

Voor W3/W4/W5 geldt dezelfde bestaande governance, maar met een eigen concrete lifecycle-/rewritekaart als hun grens A/high is. Hun nog onbekende SQL-, bronproof- of capaciteitskeuze is een onderzoeksgate, geen uitvoeringsvrijbrief. Een eventuele schemawijziging krijgt apart migratie-, backup- en rollbackbewijs; het huidige plan vereist die wijziging niet.

## Alternatieven, synthese en open vragen

**Alternatief O — operatiegericht, gekozen:** behoud één publiek command en verberg capture/guard/commit bij de bestaande eigenaar. Dit kan onnodige payloads en berekening binnen de lock verwijderen, maar vereist nauwkeurige dependencyanalyse.

**Alternatief S — eerst opslaggroepering:** laat huidige callers en berekening grotendeels staan en combineer SQL-/Blob-operaties in stores. Het publieke oppervlak blijft klein en transport kan dalen; volledige historie/admission en de buitenste resolutiontransactie blijven echter mogelijk dominant. Daarom is S een gerichte techniek voor W4, geen hoofdoplossing voor A1. Een centrale cache/performance-service is verworpen omdat die nieuwe coördinatie en overlappende bron-/workflow-/servingautoriteit zou introduceren.

Architect/Arena liet twee onafhankelijke agents beide volledige vormen beoordelen en daarna één afzonderlijke agent de vaste kandidaten toetsen. Alle gebruikten het beschikbare sessiemodel; dit was geen multimodelproef. Beide kandidaten kozen O. **Kandidaat A vormt de basis**, omdat die de buitenste resolutiontransactie en evidence op oude/nieuwe objectversie expliciet meeneemt. Uit B zijn de expliciet geordende, volledige dependencyselectie en de afzonderlijke onderzoeks-/implementatiestatus per risico verwerkt. De onjuiste verkorting `seal()` en een generieke `invoke`-parameter uit de kandidaat zijn niet overgenomen.

| Rubric, 0–4 per criterium | Hoofdbeoordeling A / B | Afzonderlijke beoordelaar A / B |
| --- | --- | --- |
| Autoriteit, dependencies en transactiegrens | 4 / 2 | 4 / 2 |
| Gemeten kosten en werkelijke caller | 4 / 3 | 4 / 3 |
| Kleine interface bij bestaande eigenaren | 3 / 3 | 3 / 3 |
| Prestatie-, correctheids- en herstelbewijs | 4 / 4 | 4 / 4 |
| Slices, afhankelijkheden en rollback | 3 / 4 | 3 / 3 |
| Volledige auditdekking zonder speculatieve verbouwing | 4 / 4 | 4 / 4 |
| Totaal | **22 / 20** | **22 / 19** |

Beide beoordelingen kiezen dezelfde basis. Het beperkte verschil betreft de uitwerking van B's uitvoeringsvolgorde; het verandert de keuze niet. Er vielen geen kandidaten uit. De synthese verwerkt alle vier concrete correcties uit de afzonderlijke beoordeling: werkelijke caller, juiste seal-signature, domeinspecifieke private ingress en een foutproef tussen correctie en laatste evidencewrite.

Geaccepteerde afwegingen: extra voorbereiding en guardcontrole in ruil voor korte beschermde writes; expliciete compatibiliteit voor nog niet omgezette varianten; verse servingbroncontrole ook wanneer een TTL sneller zou zijn. Er worden geen procentuele snelheidswinsten beloofd voordat ze zijn gemeten.

Open vragen worden in W0 en de betreffende slice opgelost: welke admissioncontext is per correctie noodzakelijk; hoe bewaakt de eigenaar de exacte volledige objectset zonder brede payloadreads; welke server-/triggerkosten domineren A2; welke versie en belasting gelden in productie; wanneer dekt één bronbewijs beide reads; welke taken zijn werkelijk onafhankelijk? Deze vragen blokkeren alleen de daarvan afhankelijke keuze.

**Herontwerpcriterium:** bij twee onafhankelijke afwijkingen van hetzelfde patroon, een tweede handmatige dependencylijst, een nieuw lock dat onvoorzien gedeelde state afschermt, of callbacks/beleidsvlaggen die de oorspronkelijke kernel omzeilen: opnieuw gronding en twee ontwerpen vergelijken. Eerst extra mechanismen schrappen; geen steeds groter framework om een verkeerde grens heen bouwen.

Eerste implementatiestap: onder #729 de echte source-units-resolution profileren en de falende native keten-/outer-transactionproef vastleggen; daarna deze complete variant via de bestaande prepared uitvoering realiseren.

## Bronnen en verificatiestatus

- [Pstack Architect](https://github.com/WilliamGomes41/plugins/blob/5108b719a7aa484ef1a9781f587c7bbeac793f92/pstack/skills/architect/SKILL.md), inclusief runner, rationale en redflags; [Arena](https://github.com/WilliamGomes41/plugins/blob/5108b719a7aa484ef1a9781f587c7bbeac793f92/pstack/skills/arena/SKILL.md). De auditgronding is hergebruikt en voor de buitenste resolutiongrens aangevuld.
- [#729-contract](https://github.com/WilliamGomes41/Metis-DS/blob/c4db3bd84bfe722ab235eff67d2ccf69b60a785b/docs/change-contracts/729-bounded-revision-inputs.md), [#952-contract](https://github.com/WilliamGomes41/Metis-DS/blob/c4db3bd84bfe722ab235eff67d2ccf69b60a785b/docs/change-contracts/952-current-command-dependencies.md), [#959-projectcontract](https://github.com/WilliamGomes41/Metis-DS/blob/c4db3bd84bfe722ab235eff67d2ccf69b60a785b/docs/change-contracts/959-bounded-io-project-redesign.md).
- [Prepared command](https://github.com/WilliamGomes41/Metis-DS/blob/c4db3bd84bfe722ab235eff67d2ccf69b60a785b/src/review/review_command_v1.py#L401), [correct_object](https://github.com/WilliamGomes41/Metis-DS/blob/c4db3bd84bfe722ab235eff67d2ccf69b60a785b/src/operations_console_v1.py#L4159), [fysieke writer en seal](https://github.com/WilliamGomes41/Metis-DS/blob/c4db3bd84bfe722ab235eff67d2ccf69b60a785b/src/workflows/object_delta_postgres_v1.py#L43).

Voor dit plan zijn bronpaden/signatures, meetcijfers, auditdekking en de ontwerpen gecontroleerd. Nieuwe runtimebenchmarks of regressietests zijn niet uitgevoerd; er is nog geen prestatieverbetering gerealiseerd. De afzonderlijk opgedragen registratie koppelt dit contract via een documentatie-PR en trackerhandoffs aan GitHub en Linear. Productcode, merge en deployment vallen buiten deze registratiewijziging.

Registratieverificatie, 7 november 2026: [de uitvoerbare artifactcheck](../../tests/characterization/check_performance_audit_20261107.py) herberekent alle 80 KO4-observaties en vijf hervatruns en controleert de auditdekking en lokale planlinks: PASS. `scripts/check_architecture_boundaries.py`, `scripts/repository_preflight.py`, `scripts/release_control_preflight.py` op de expliciete gewijzigde paden, document-contractvalidator en diff-whitespace: PASS. Dit is bewijs voor het dossier; actuele PR-CI/review en productieacceptatie worden afzonderlijk in de handoff vermeld.
