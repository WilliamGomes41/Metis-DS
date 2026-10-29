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
| Call-breed `pre_review_llm_proposal_rejected` (onderliggend: `relation_target_ambiguous`, zie 2.7) | 1 call | 1 | 0 |
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
| Kernvelden (`type_evidence_spans`, `subject_span`, `support_span`) | 13 | Per geval bepaald uit de bron (alleen vorm, geen tekst): **5×** begint de kandidaat met een kleine letter midden in een zin, met het bewijs direct ervóór en zonder leesteken ertussen; **2×** staat het bewijs in een andere zin van hetzelfde blok (zinsgrens ertussen); **6×** in een ander blok (3× in de 1–3 voorgaande blokken, 3× ver weg) | 5× **(a)**: de kandidaat breekt de zin af en laat het typebewijs buiten de kern. 8× **(d)**: het model verwijst naar een andere zin of ander blok, terwijl de instructie zegt "Other field evidence must stay within the selected core" |

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
`tests/test_source_strength_labels.py::test_verbal_strength_phrasing_is_never_a_label`. Na
besluit B5-c (sectie 3) telt werkwoordelijke sterkte alleen binnen een V3-kern, nooit als label.

### 2.5 `recommendation_strength_evidence_not_applicable` — 1 uniek (historisch)

Het label `sterke aanbeveling` (positie 13–31) ligt binnen de kandidaat (0–192), maar vóór
de aanbevelingskern (45–192): in een inleidend zinsdeel van dezelfde zin, met de kern direct erna.
`_applicable_strength_ranges` accepteert alleen de kern, direct volgende stempels en
omsluitende koppen (A07). Een inleidend label viel daar bewust buiten. Klasse (g), hetzelfde
patroon als S1 in 2.4. Een latere call heeft het geval opgelost (historical). **Besluit B5-c**
(sectie 3): in V3 telt zo'n label wel, mits in hetzelfde object en blok, direct vóór de kern, met
alleen een dubbele punt of spaties ertussen.

### 2.6 `semantic_supplement_outside_target` — 0

Komt in deze snapshot niet voor. De gedragstest is #910 (in main).

### 2.7 Overige codes in deze snapshot

Deze codes vallen buiten de zes MET-5-codes, maar staan in het overzicht en worden daarom
ook geclassificeerd.

**`semantic_evidence_literal_not_found` — 14 uniek (9 pending).** Volgens de
resolver is de literal niet als aaneengesloten tekst in het blok aanwezig.

| Situatie | Uniek | Klasse |
| --- | --- | --- |
| `predicate_span`: alle woorden staan in volgorde in de bron, maar het model liet 2–4 woorden ertussen weg (9×), of 17 woorden (2×) | 11 | (d) modelvoorstel. De 2–4-woordgevallen passen bij een gescheiden Nederlands werkwoordscluster, waarbij onderwerp of object tussen de werkwoorden staat. Na besluit B5-g (sectie 3) wijst één aaneengesloten span inclusief de tussenliggende woorden het predicaat aan |
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

**`source_assessment_bounds_invalid` — 1 uniek (historical).** Het model gaf een
bronbeoordeling (rol `structure`) over een volledig blok van 40 tekens. Dat blok stond in de taak
alleen als **context-only** blok (`evidence_blocks`), niet tussen de 9 selecteerbare
`source_blocks`. De literal-resolutie kent context-blokken wel en geeft geldige offsets (0–40,
binnen het blok). `source_accountability_v1.validate_assessments` toetst echter alleen tegen de
bronblokken van de taak, en meldt een onbekend blok onder dezelfde code als ongeldige offsets.
De meerblok-`spans` in de bevinding zijn de doelbereiken van de taak; `bounded_formation_v1` vult
die in als een afwijzing geen eigen spans heeft. Het werkelijke bereik staat in `evidence_span`.
Klasse: **mismatch in het producercontract**, niet zuiver (d). `SEMANTIC_V3_INSTRUCTION`
verbiedt alleen een nieuwe *kandidaat* uit `evidence_blocks` en noemt `selectable_ranges` de
*kandidaat*grens (`pre_review_semantic_v1.py:160–162`). `SOURCE_ACCOUNTABILITY_INSTRUCTION`
(`:165–173`) en het response-schema beperken bronbeoordelingen niet tot de bronblokken. Dat doet
alleen `validate_assessments`, achteraf. De regel zelf is terecht (e): een taak verantwoordt
alleen haar eigen bron. Kleinste wijziging zonder domeinbesluit: de instructie laat beoordelingen
uitdrukkelijk binnen `selectable_ranges` blijven (§4). Het geval is later opgelost. Diagnostische
kanttekening: de code onderscheidt "blok niet selecteerbaar" niet van "offsets ongeldig".

**Call-breed `pre_review_llm_proposal_rejected` — 1 call (initiële taak `failed`; recovery `completed`).**
De call-rij en de opgeslagen provider-evidence bewaren alleen de generieke code, zonder
`formation`-record. Daarom is de onderliggende code vastgesteld met een offline replay van de
opgeslagen modeluitvoer door `recoverable_formation_v1.prepare`, met de opgeslagen
validator-input en de blokken uit de request-payload (code functioneel gelijk aan de call-commit,
§0). Drie in productie gevalideerde calls slaagden als positieve controle in dezelfde replay.

- **Uitkomst:** `relation_target_ambiguous` (`semantic_passage_v1.attach_relation_proposals`).
- **Oorzaak:** het model stelde 4 objecten voor, waarvan er 2 (`recommendation` en `explanation`) exact dezelfde selectie hebben. De check faalt dan, ook zonder relaties in het voorstel, omdat een relatiedoel niet eenduidig te maken is.
- **Waarom de hele call:** de fout draagt geen `candidate_index`, dus `prepare` (regel 88–90) kan hem niet aan één object toewijzen. De twee andere objecten gaan daardoor ook verloren.
- **Klasse:** **mismatch in het producercontract**. Instructie en schema verbieden twee objecten met identieke selectie nergens; alleen `attach_relation_proposals` weigert dat. De weigering zelf is terecht (e), want het relatiedoel moet eenduidig zijn. Dat de hele call sneuvelt, is dezelfde versterking als bij B5-b.
- **Herstel:** de recovery-taak voor hetzelfde bronbereik is afgerond.
- **Diagnostisch gat:** de onderliggende code wordt niet bewaard; zie §4.

### 2.8 Besluiten uit MET-5

| Besluit | Bewijs in deze snapshot |
| --- | --- |
| B5-a: uitzonderingscontext in V3 | Geen `exception_span`-afwijzing: geen bevestigend of ontkrachtend geval. **BESLOTEN 2026-10-29**: niet bouwen (zie MET-5-dossier §8) |
| B5-b: quarantaine bij relatiefout | Bevestigd: 6 cascadebevindingen na `relation_endpoint_missing` in 5 unieke relatiegevallen. Of de getroffen objecten zelfstandig geldig waren, is zonder hun eigen validatie UNKNOWN |

## 3. Nieuwe open besluiten (projectlead)

| ID | Vraag | Bewijs | Kleinste wijziging na een "ja" |
| --- | --- | --- | --- |
| B5-c | Telt werkwoordelijke sterkte in de bron (`sterk aanbevolen/geadviseerd/afgeraden`) als expliciete sterkte en richting? En een inleidend label in dezelfde zin vóór de kern (2.5)? | 5 bronplekken, 15 pending bevindingen (S2); 1 historisch geval (2.5) | **BESLOTEN 2026-10-29** (projectlead: beide adviezen overgenomen). (1) Gesloten lijst, alleen binnen de V3-aanbevelingskern zelf: `sterk aanbevolen`/`sterk geadviseerd` → sterk, voor; `sterk afgeraden`/`sterk ontraden` → sterk, tegen. Een ontkenning (`niet`, `geen`, `nooit`) eerder in dezelfde zin sluit de cue uit (fail closed). Zwak wordt nooit uit een werkwoord afgeleid. Buiten de kern, als stempel of als kop telt een werkwoordsvorm niet. Een werkwoordelijke richting die de voorgestelde richting tegenspreekt, wijst af. (2) Een inleidend label telt alleen in hetzelfde object en hetzelfde bronblok, direct vóór de kern, met alleen dubbele punt of spaties ertussen. Zonder dubbele punt telt het label alleen aan het begin van het blok; anders kan het de nastempel van de vorige tekst zijn (fail closed). Een label boven een lijst (eigen bronblok) telt niet. V2 ongewijzigd. Contractdeel `v3-verbal-strength-and-lead-in-label-v1`; tests `tests/test_v3_verbal_strength_b5c.py`. Restrisico: binnen één fragment worden regeleinden tot spaties genormaliseerd, dus een label en kern in één fragment gelden als dezelfde zin. Eigenaar MET-6 (uitvoering), MET-7 (vocabulaire) |
| B5-d | Mag een `list_introduction`-context een `scope_span` dragen? | 4 unieke gevallen | **BESLOTEN 2026-10-29** (projectlead): ja. `CONTEXT_FIELDS["scope_span"]` bevat `list_introduction` (V3; contractdeel `scope-list-introduction-v1`). Eigenaar MET-6 |
| B5-e | Mag `occurrence = null` voor een **kernveld** binnen de kandidaatspans worden opgelost? | 30 unieke kernveldgevallen (47 incl. contextvelden) | **BESLOTEN 2026-10-29** (projectlead: advies overgenomen). Ja, alleen voor V3-kernvelden en alleen bij precies één treffer binnen de eigen kandidaat. V2 houdt blokbrede uniciteit. Resolverversie `candidate-scoped-core-v1`. **Uitbreiding 2026-10-29** (projectlead: "ga door"): ook contextvelden, binnen de eigenaren die `bind_fields` toelaat (de kandidaat plus opgeloste contextentries met een toegelaten rol). Resolverversie `owner-scoped-fields-v2`. Eigenaar MET-6 |
| B5-f | Horen doelvelden (`supported_object`, `condition_target`) binnen de kandidaat, of via een relatie? | 22 unieke gevallen (24 op main na B5-e) | **BESLOTEN 2026-10-29** (projectlead): via een relatie. In V3 mag een doelveld `span null` met `missing_reason via_relation` dragen; admissie neemt het doel uitsluitend uit `incoming_relation_targets`: precies één peer-relatie (`applies_if`/`except_if`/`explains`/`supported_by`) die deze exacte objectversie noemt en de relatie-admissiechecks doorstaat. De compatibiliteitswaarde van `_target_for` telt niet. Zonder zo'n relatie blijft `*_target_missing` blokkeren. Contractdeel `target-via-relation-v1`. Eigenaar MET-6 |
| B5-g | Mag een predicaat dat in de bron gescheiden staat (Nederlands werkwoordscluster) uit meerdere letterlijke spans bestaan? | 9 unieke gevallen met 2–4 weggelaten woorden (2.7) | **BESLOTEN 2026-10-29** (projectlead: advies overgenomen). Nee, geen meervoudige spans. Een predicaat blijft één aaneengesloten literal; bij een gescheiden werkwoordscluster loopt het van het eerste tot het laatste werkwoorddeel, inclusief de woorden ertussen. Negatie en modaliteit vallen er zo automatisch binnen. Alleen de V3-veldbeschrijving wijzigt (contractdeel `predicate-contiguous-v1`); validatie, schemavorm en opslag blijven gelijk. Tests `tests/test_v3_split_predicate_b5g.py`. Eigenaar MET-6 |

## 4. Zonder besluit uit te voeren (producer en diagnostiek)

1. Twee diagnostische defecten:
   - §2.2: de juiste V3-veldnaam in `source_bound_field_outside_candidate`;
   - §2.7: bij een call-brede afwijzing de onderliggende code bewaren (nu alleen `pre_review_llm_proposal_rejected`).
2. Producerinstructies, binnen de bestaande providerroute en zonder domeinwijziging:
   - `occurrence` meegeven bij een herhaalde literal;
   - het volledige sterktelabel selecteren (S1);
   - een contextentry meegeven voor `scope_span`/`target_group_span` buiten de kern;
   - een niet-aaneengesloten literal vervangen door `missing_reason` (2.7, zolang B5-g open is);
   - relatie-eindpunten exact gelijk aan de spans van een voorgesteld object (2.7);
   - bronbeoordelingen alleen binnen `formation_task.selectable_ranges` (2.7; nu staat dat alleen in de validator);
   - geen twee objecten met identieke selectie (2.7; nu staat dat alleen in de validator).

   Gecontroleerd tegen de instructie in `pre_review_semantic_v1`: de regels voor `occurrence`, relatie-eindpunten ("exact selected spans") en velden binnen de kern staan er al expliciet in. Daar blijft (d) de classificatie.

Beide wijzigen vorming of diagnose van werkpakket MET-6 en vragen een eigen GitHub-issue
na triage. Ze zijn niet in dit dossier uitgevoerd.

## 5. Gereed (#911)

- [x] Elke foutcode in deze snapshot heeft een oorzaakklasse (2.1–2.5 en 2.7), en de zesde MET-5-code staat expliciet als "komt niet voor" (2.6).
- [x] B5-a en B5-b hebben een bevestigend of ontkrachtend bronvoorbeeld, of blijven expliciet open (2.8).
- [x] Gevallen met klasse (g) zijn per geval vastgesteld en bewust open, omdat hun uitkomst van een domeinbesluit afhangt: S2 en het inleidende label (2.4, 2.5) wachten op B5-c. Ook de zelfstandige geldigheid onder B5-b blijft open. Dit volgt #878: "Onbeslist blijft open"; geen van deze gevallen mist een vastgestelde oorzaak.
- [x] Geen private brontekst of ruwe provideruitvoer in GitHub.
- [x] Geen runtime- of productieacceptatie geclaimd. Reads/writes en runtime per I/O-pad zijn NOT TESTED (de export bevat ze niet); dat hoort bij MET-10.
