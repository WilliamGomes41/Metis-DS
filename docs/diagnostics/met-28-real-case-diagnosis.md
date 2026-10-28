# MET-28 / #911 — oorzaak per echt geval (één snapshot)

Change class: C (onderzoek). Rewrite risk: none. Touches lifecycle invariants: no.
Geen productcode gewijzigd. Vervolg op het MET-5-dossier
(`docs/diagnostics/met-5-formation-rejection-diagnosis.md`); het voegt geen norm toe.

## 0. Gepinde basis en privacygrens

| Gegeven | Waarde |
| --- | --- |
| Export | `processing-evidence-export-v16`, sha256 `a51491c8b09564523596246d027b6238594ce64c12178f771a60cfa7ded0a013`, geëxporteerd 2026-10-28T19:41Z |
| Snapshot | `snap-f24235c0fa00742a-c6fa4767`; bron-sha256 `20b4256c…bfc49f`, bronversie 1.0 |
| Route en contract | `bounded-formation-v1`; semantische replay-identiteit `semantic-replay-v1.0.0` (hash `b26b5acf…`); extractor `metis-docling-source-v1/2.132.0` |
| Pogingen | ingest `pa_0b4a…` (26-10, 12:27–13:36) en resume `pa_ae61…` (26-10, 23:18–23:30), beide `succeeded` |
| Code die de calls deed | `53f7551` (300 calls) en `96b22c1` (25 calls) |
| Code vergeleken | main `b3282b6`. De zeven betrokken validators (`source_evidence_resolution_v1`, `source_bound_fields_v2/v3`, `recommendation_semantics_v1`, `semantic_passage_v1`, `recoverable_formation_v1`, `bounded_formation_v1`) verschillen alleen in imports, door de verplaatsing naar `src/vorming/`. De oorzaken gelden dus ook voor de huidige code. |

De export en de brontekst blijven buiten GitHub. Dit dossier bevat alleen tellingen,
veldnamen, codeverwijzingen en de generieke sterktewoorden die voor de classificatie nodig
zijn. Brontekst per blok is gereconstrueerd uit de opgeslagen request-payloads: 185 calls,
861 blokken, 0 tekstconflicten. De analyse liep in de sessie-scratchmap en is niet
gecommit.

**Telling.** Bevindingen worden ontdubbeld op (foutcode, kandidaatspans, veld, bewijsverwijzing).
Dezelfde plek wordt bij een volgende call of de resume opnieuw afgewezen;
"veel bevindingen" is dus geen "veel onafhankelijke oorzaken".

## 1. Overzicht

| Meting | Waarde |
| --- | --- |
| Taken gepland / terminal / pending / failed | 123 / 102 / 21 / 0 (62 open bronbereiken, 15 720 tekens) |
| Taakrecords (initial + recovery) | 325: initial 182 completed, 56 partial, 1 failed; recovery 38 completed, 48 partial |
| Echte modelcalls | 325: 220 validated, 104 partial, 1 call-breed `pre_review_llm_proposal_rejected`. **Geen** budgetuitputting |
| Tokens | input 1 976 795, output 807 558 |
| Kandidaten per run | 762 (ingest) en 770 (resume) |
| Admissionbevindingen | 390 blocked, 85 allowed (andere laag; niet in deze diagnose) |
| Bronregister | 665 `not_yet_assessed`, 54 `used_as_context`, 44 `selected_as_candidate`, 42 `linked_as_support` |

| Foutcode | Bevindingen | Uniek | Uniek pending |
| --- | --- | --- | --- |
| `semantic_evidence_literal_ambiguous` | 109 | 54 | 37 |
| `source_bound_field_outside_candidate` | 71 | 52 | 22 |
| `semantic_dependency_rejected` | 54 | 33 | 11 |
| `semantic_evidence_literal_not_found` | 25 | 14 | 9 |
| `recommendation_strength_literal_mismatch` | 20 | 15 | 12 |
| `relation_endpoint_missing` | 8 | 5 | 4 |
| `recommendation_strength_evidence_missing` | 3 | 2 | 0 |
| `recommendation_strength_evidence_not_applicable` | 2 | 1 | 0 |
| `source_assessment_bounds_invalid` | 1 | 1 | 0 |
| `semantic_supplement_outside_target` | 0 | 0 | 0 |

Anders dan in het v12-incident wordt het open werk hier niet door het budget verklaard:
alle 21 pending taken zijn `partial`, met producerafwijzingen.

## 2. Oorzaak per foutcode

Klassen zoals in MET-5: (a) kandidaatgrens, (b) contextbinding, (c) bronlokalisatie,
(d) modelvoorstel, (e) terechte domeinregel, (f) cascade, (g) onbeslist.

### 2.1 `semantic_evidence_literal_ambiguous` — 54 uniek

Mechanisme: `source_evidence_resolution_v1.resolve_proposal_evidence` eist bij
`occurrence = null` dat de literal uniek is in het **hele blok**.

| Situatie | Uniek (pending) | Klasse |
| --- | --- | --- |
| Literal komt precies 1× voor binnen de eigen kandidaatspan, maar elders in het blok nog eens | **47** (31) | (c) bronlokalisatie, met (d) als directe veroorzaker: `occurrence` ontbreekt |
| Literal komt ook binnen de kandidaat meerdere keren voor | 6 (5) | (e) terecht: echt ambigu |
| Literal komt niet binnen de kandidaat voor | 1 (1) | (d), of een contextveld buiten de kern |

- Bij 41 van de 54 gevallen bestaat de literal uit 1–2 woorden; in het blok komt hij 2× (36), 3× (15) of 4× (3) voor.
- Velden: 30 kernvelden en 17 contextvelden (`target_group_span`, `scope_span`, `condition_span`, `actor_span`) in de groep "uniek in kandidaat".
- **Eerste oorzaak:** de resolver zoekt blokbreed, terwijl het model een korte literal zonder `occurrence` geeft. Binnen de kandidaat is de plek in 47 gevallen ondubbelzinnig.
- **Kleinste wijziging (open besluit B5-e):** bij `occurrence = null` een kernveld oplossen binnen de geselecteerde kandidaatspans. Een kernveld moet volgens `bind_fields` toch al binnen de kandidaat liggen. Voor contextvelden kan dat niet zonder meer, omdat die buiten de kern mogen staan. Het alternatief zonder domeinwijziging is een producerinstructie die `occurrence` verplicht stelt bij korte literals.
- **Regressieproef:** positief bij 1× in de kandidaat en 2× in het blok; negatief bij 2× in de kandidaat (blijft ambigu); contextvelden blijven ongewijzigd.

### 2.2 `source_bound_field_outside_candidate` — 52 uniek

| Groep | Uniek | Bevinding | Klasse |
| --- | --- | --- | --- |
| Doelvelden: `supported_object` (verklaring), `condition_target` (voorwaarde) | 22 | Wijzen naar de uitspraak die wordt uitgelegd of geconditioneerd: 4× in een ander blok, 11× aansluitend ervoor of erna, 7× met tussentekst | (d), met een contractvraag: V2/V3 eisen dat het doel letterlijk in de kandidaat staat. Een losstaand doel hoort via een relatie te lopen (B5-f) |
| `scope_span` (16) en `target_group_span` (1). De bevinding meldt ze als `actor_of_scope` | 17 | 9× geen contextentry voorgesteld; 4× een entry die de span niet dekt; **4× wel gedekt, maar met rol `list_introduction`**, die `CONTEXT_FIELDS["scope_span"]` niet toestaat | 13× (d); 4× (b), open besluit B5-d |
| Kernvelden (`type_evidence_spans`, `subject_span`, `support_span`) | 13 | 6× in een ander blok, 6× aansluitend ervóór, 1× erna | (a) of (d): de kern is te krap gekozen of het bewijs staat in een buurzin. Zonder menselijke referentie onbeslist welke van de twee |

**Diagnostisch defect (aangetoond).** `source_bound_fields_v3.bind_fields` hergebruikt
`bind_v2` met `legacy_field = "actor_of_scope"` voor `actor_span`, `target_group_span` en
`scope_span`. Daardoor noemt de bevinding de V2-veldnaam: alle 19 `actor_of_scope`-meldingen
waren `scope_span` (17) of `target_group_span` (2). Het weigergedrag is correct; alleen de
diagnose (Review/blokkade/export) misleidt. Kleinste wijziging: het echte V3-veld
in de finding zetten.

### 2.3 `semantic_dependency_rejected` — 33 uniek (cascade)

Telling per bevinding, naar de primaire afwijzing in dezelfde call en status:

| Primaire afwijzing | Bevindingen |
| --- | --- |
| Object: `source_bound_field_outside_candidate` | 13 |
| Object: ambigu + outside_candidate | 11 |
| Object: `semantic_evidence_literal_not_found` | 6 |
| **Relatie: `relation_endpoint_missing`** | 6 |
| Object: strength-codes, al dan niet gecombineerd | 14 |
| Object: `semantic_evidence_literal_ambiguous` in dezelfde call, maar met andere status (transitief, zie hieronder) | 4 |

- Alle gevallen met een herkenbare oorzaak zijn een cascade (f).
- De 6 na `relation_endpoint_missing` bevestigen **in productiebewijs** de call-brede quarantaine uit MET-5, proef P2 (`recoverable_formation_v1.py:115`). Die is relevant voor besluit B5-b (#909).
- De laatste 4 bevindingen (2 uniek, één call) zijn herleid via de opgeslagen modeluitvoer. Object 2 is afgewezen als `semantic_evidence_literal_ambiguous` (pending); relatie `explains` 2→0 neemt object 0 mee, en relatie `explains` 1→0 daarna object 1. Dat is een **transitieve cascade (f)**. De cascaderijen staan op historical omdat een latere call hun spans heeft gevalideerd; de primaire afwijzing staat nog op pending. Daardoor viel het verband weg bij groepering per status.

### 2.4 `recommendation_strength_literal_mismatch` — 15 uniek, 9 unieke bronplekken

Alle 20 bevindingen hebben `observed_value = null` en `proposed_value = strong`: de validator
herkent in het gekozen bewijs geen sterkte, niet een andere sterkte.

| Subgroep | Bronplekken | Oorzaak | Klasse |
| --- | --- | --- | --- |
| S1: het model koos `sterke`, terwijl de bron `sterke aanbeveling` zegt | 4 | De volledige literal wordt wél herkend (`SOURCE_LITERAL_STRONG_RE`). In 3 van de 4 staat het label echter in een inleiding vóór de kern; met de volledige literal volgt dan `not_applicable` (zie 2.5) | (d) modelvoorstel als eerste oorzaak; daarna B5-c |
| S2: werkwoordelijke formulering (`sterk afgeraden` 3×, `sterk aanbevolen` 1×, `sterk geadviseerd` 1×) | 5 | `recommendation_semantics_v1` herkent alleen labels (`sterke aanbeveling/advies`, `aanbeveling: sterk`, `Sterk – voor/tegen`). Werkwoordsvormen bestaan niet in het vocabulaire | **(g) onbeslist, besluit B5-c**: is werkwoordelijke sterkte in de bron een expliciete sterkte? A07 bindt bewust alleen aan herkende labels |

`afgeraden` impliceert bovendien de richting "tegen"; een besluit moet richting en sterkte samen
regelen. Eigenaar: MET-7 (richtlijnsterkte, #530), na besluit. De huidige grens is vastgelegd in
`tests/test_source_strength_labels.py::test_verbal_strength_phrasing_is_not_a_label_until_decided`;
die test verandert alleen samen met een vastgelegd besluit B5-c.

### 2.5 `recommendation_strength_evidence_not_applicable` — 1 uniek (historisch)

Het label `sterke aanbeveling` (positie 13–31) ligt binnen de kandidaat (0–192), maar vóór
de aanbevelingskern (45–192): in een inleidend zinsdeel van dezelfde zin, met de kern direct erna.
`_applicable_strength_ranges` accepteert alleen de kern, direct volgende stempels en
omsluitende koppen (A07). Een inleidend label valt daar bewust buiten. Klasse **(g) onbeslist**,
hetzelfde patroon als S1 in 2.4; het hoort bij besluit B5-c. Een latere call heeft het geval
opgelost (historical).

### 2.6 `semantic_supplement_outside_target` — 0

Komt in deze snapshot niet voor. De gedragstest is #910 (in main).

### 2.7 Overige codes in deze snapshot

Deze codes vallen buiten de zes MET-5-codes, maar staan in het overzicht en worden daarom
ook geclassificeerd.

**`semantic_evidence_literal_not_found` — 14 uniek (9 pending).** Volgens de
resolver is de literal niet als aaneengesloten tekst in het blok aanwezig.

| Situatie | Uniek | Klasse |
| --- | --- | --- |
| `predicate_span`: alle woorden staan in volgorde in de bron, maar het model liet 2–4 woorden ertussen weg (9×), of 17 woorden (2×) | 11 | (d) modelvoorstel. De 2–4-woordgevallen passen bij een gescheiden Nederlands werkwoordscluster, waarbij onderwerp of object tussen de werkwoorden staat. Eén span kan zo'n predicaat niet letterlijk aanwijzen: **open besluit B5-g** |
| Lange span (`support_span`, 94 woorden) met 18 woorden weggelaten | 1 | (d): het model verkortte de bron |
| Woorden niet in volgorde in het blok (`factual_claim_span`, 39 woorden) | 1 | (d): niet-letterlijke reconstructie |
| Alleen hoofdletters verschillen (`type_evidence_spans`, 1 woord) | 1 | (d): de resolver vergelijkt terecht exact |

De afwijzing is in alle gevallen terecht (e): de literal staat niet aaneengesloten in de bron.
De eerste oorzaak ligt bij het model.

**`relation_endpoint_missing` — 5 uniek (4 pending).** De eindpunten van de relatie zijn vergeleken
met de spans van alle objecten die het model in dezelfde call voorstelde (opgeslagen
modeluitvoer). `recoverable_formation_v1.prepare` eist dat beide eindpunten exact
gelijk zijn aan de selectie van een object.

| Relatie | Bron-eindpunt | Doel-eindpunt |
| --- | --- | --- |
| `explains` (pending) | exact object | overlapt een object, niet exact |
| `applies_if` (historical) | exact object | geen object |
| `explains` (pending) | geen object | exact object |
| `explains` (pending) | geen object | geen object |
| `applies_if` (pending) | overlapt, niet exact | overlapt, niet exact |

In alle 5 gevallen is de eerste oorzaak (d): het model gaf als eindpunt een span die geen
voorgesteld object is, of een span die wijder of smaller is dan het object. De regel is terecht
(e): een relatie zonder identificeerbaar eindpunt kan geen afhankelijkheid vastleggen. Het
gevolg is de call-brede quarantaine (§2.3, B5-b). Kleinste wijziging zonder domeinbesluit is
een producerinstructie: eindpunten exact gelijk aan `objects[i].spans`.

**`recommendation_strength_evidence_missing` — 2 uniek (historical).** Het model gaf
`strength_status = unmapped` zonder `strength_evidence`. `unmapped` vereist een
letterlijke verwijzing (`semantic_passage_v1`). Klasse (d); een latere call heeft beide
gevallen opgelost.

**`source_assessment_bounds_invalid` — 1 uniek (historical).** Een bronbeoordeling met rol
`structure` over meerdere blokken, met een bewijsverwijzing naar een blok buiten die spans.
`source_accountability_v1.validate_assessments` weigert dat terecht. Klasse (d), later opgelost.

### 2.8 Besluiten uit MET-5

| Besluit | Bewijs in deze snapshot |
| --- | --- |
| B5-a: uitzonderingscontext in V3 | Geen `exception_span`-afwijzing: geen bevestigend of ontkrachtend geval. Blijft **open** |
| B5-b: quarantaine bij relatiefout | Bevestigd: 6 cascadebevindingen na `relation_endpoint_missing` in 5 unieke relatiegevallen. Of de getroffen objecten zelfstandig geldig waren, is zonder hun eigen validatie UNKNOWN |

## 3. Nieuwe open besluiten (projectlead)

| ID | Vraag | Bewijs | Kleinste wijziging na een "ja" |
| --- | --- | --- | --- |
| B5-c | Telt werkwoordelijke sterkte in de bron (`sterk aanbevolen/geadviseerd/afgeraden`) als expliciete sterkte en richting? En een inleidend label in dezelfde zin vóór de kern (2.5)? | 5 bronplekken, 15 pending bevindingen (S2); 1 historisch geval (2.5) | Vocabulaire uitbreiden in `recommendation_semantics_v1`, met een negatieve test (`sterk` als bijwoord in andere betekenis). Eigenaar MET-7 |
| B5-d | Mag een `list_introduction`-context een `scope_span` dragen? | 4 unieke gevallen | `CONTEXT_FIELDS["scope_span"]` aanvullen. Eigenaar MET-6 |
| B5-e | Mag `occurrence = null` voor een **kernveld** binnen de kandidaatspans worden opgelost? | 30 unieke kernveldgevallen (47 incl. contextvelden) | Resolver scopen voor kernvelden, positief en negatief getest. Eigenaar MET-6 |
| B5-f | Horen doelvelden (`supported_object`, `condition_target`) binnen de kandidaat, of via een relatie? | 22 unieke gevallen | Eerst een producerinstructie, geen domeinwijziging. Eigenaar MET-6 |
| B5-g | Mag een predicaat dat in de bron gescheiden staat (Nederlands werkwoordscluster) uit meerdere letterlijke spans bestaan? | 9 unieke gevallen met 2–4 weggelaten woorden (2.7) | Versiegebonden veldcontract, zoals `type_evidence_spans` al een lijst is. Zonder besluit blijft het een producerinstructie (`missing_reason` in plaats van een niet-aaneengesloten literal). Eigenaar MET-6 |

## 4. Zonder besluit uit te voeren (producer en diagnostiek)

1. Het diagnostisch defect uit §2.2: de juiste V3-veldnaam in `source_bound_field_outside_candidate`.
2. Producerinstructies, binnen de bestaande providerroute en zonder domeinwijziging:
   - `occurrence` meegeven bij een herhaalde literal;
   - het volledige sterktelabel selecteren (S1);
   - een contextentry meegeven voor `scope_span`/`target_group_span` buiten de kern;
   - een niet-aaneengesloten literal vervangen door `missing_reason` (2.7, zolang B5-g open is);
   - relatie-eindpunten exact gelijk aan de spans van een voorgesteld object (2.7).

Beide wijzigen vorming of diagnose van werkpakket MET-6 en vragen een eigen GitHub-issue
na triage. Ze zijn niet in dit dossier uitgevoerd.

## 5. Gereed (#911)

- [x] Elke foutcode in deze snapshot heeft een oorzaakklasse (2.1–2.5 en 2.7), en de zesde MET-5-code staat expliciet als "komt niet voor" (2.6).
- [x] B5-a en B5-b hebben een bevestigend of ontkrachtend bronvoorbeeld, of blijven expliciet open (2.8).
- [x] Geen private brontekst of ruwe provideruitvoer in GitHub.
- [x] Geen runtime- of productieacceptatie geclaimd. Reads/writes en runtime per I/O-pad zijn NOT TESTED (de export bevat ze niet); dat hoort bij MET-10.
