# #1067 deel A — Richting en sterkte bij de reviewer

Change class: A
Promise: De medewerker kiest nooit richting of sterkte van een aanbeveling; Metis stelt ze voor en de reviewer bevestigt of corrigeert ze op de reviewkaart. Alleen bevestigde richting en sterkte worden geleverd.
Proof: Native PostgreSQL-proef: een aanbeveling uit annotatie zonder voorstel voor richting en sterkte wordt gereed, gebouwd en toegelaten met een signaal; de reviewer kiest richting en sterkte op de reviewkaart en keurt goed; een keuze die niet bij de bron past wordt geweigerd; een fout voorstel van Metis wordt door de reviewer gecorrigeerd.
Touches lifecycle invariants: yes
Rewrite risk: none

Part of MET-78. Besluiten William, 13 november 2026: “De richting en de sterkte
liggen niet meer bij de medewerker”; “Er moet wel een manier zijn om aan te
passen bij een fout van Metis”; correctie bij de reviewer op de reviewkaart:
“Ja, doe dat samen met slice 5.”

## Huidige toestand

- `human_annotation_preview_v1.inspect_annotation` meldt
  `recommendation_semantics_invalid` als een aanbeveling geen volledige richting
  en sterkte heeft; dat houdt gereedmelden en de documentcontrole tegen. De kaart
  opent daarvoor het stappenformulier.
- `semantic_passage_v1._recommendation_semantics_from_proposal` weigert een
  half voorstel (`recommendation_direction_invalid`); bouwen faalt dan.
- `admission_gate_v1._recommendation_semantics_codes` blokkeert een aanbeveling
  zonder voorstel (`recommendation_direction_missing`).
- `review_assessment_v1.displayed_review_descriptor` kan een aanbeveling zonder
  volledig voorstel niet bevestigen; de compacte reviewkaart biedt geen keuze.
- Goedkeuren (`operations_console_v1.review_object`) accepteert al een keuze van
  de reviewer en bindt het bronbewijs zelf
  (`confirmed_recommendation_semantics_from_review`); een sterkte zonder
  letterlijk sterk- of zwak-signaal in de bron wordt geweigerd.

## Lifecycle-specificatie (§14)

```text
Lifecycle entity: WorkingRevision (één kennisobjectversie van het soort aanbeveling)
Lifecycle transition: aanbeveling In review → Goedgekeurd, met richting en sterkte
  door de reviewer gekozen of bevestigd
Initial durable state: een niet-gepubliceerde WorkingRevision met een
  aanbeveling uit annotatie, met of zonder volledig voorstel van Metis voor
  richting en sterkte.
Trigger: de reviewer kiest of bevestigt richting en sterkte op de reviewkaart en
  keurt goed.
Authorization: ongewijzigd: de bevoegde eerste reviewer van deze versie.
Validation: drie vragen ja; richting is aanraden of afraden; sterkte is sterk,
  zwak of niet vermeld; Metis vindt het bronbewijs zelf en weigert een sterkte
  zonder bijpassend signaal in de bron (bestaande regel); exacte versie en revisie.
Mutable entities: de objectversie (bevestigd soort, bevestigde richting en
  sterkte, nieuwe patchversie zoals nu bij bevestigen); reviewbinding; logboek.
Immutable entities: bron, annotaties, bouwbewijs, eerdere versies, releases,
  publicatieregister.
Workflow state before: in_review.
Workflow state after: in_review als er elders nog curatorwerk open staat, anders
  ready_for_publication voor zover technische poorten slagen.
Release state before: geen release voor deze WorkingRevision.
Release state after: ongewijzigd; een latere release bevat de aanbeveling met de
  bevestigde richting en sterkte.
Serving state before: niet uitgeleverd.
Serving state after: niet uitgeleverd tot publicatie; daarna alleen met
  bevestigde richting en sterkte (ongewijzigde regel).
Expected API result: de bestaande reviewopdracht met de gekozen richting en
  sterkte; weigering met een bestaande foutcode bij een keuze die niet bij de
  bron past.
Expected UI result: de annotatiekaart vraagt nooit richting of sterkte; de
  reviewkaart toont bij een aanbeveling twee keuzes in de bestaande regel,
  vooraf ingevuld met het voorstel van Metis als dat er is.
Failure result: bij een weigering wordt niets vastgelegd en blijft de keuze
  zichtbaar met de melding.
Restart result: de bevestigde richting en sterkte staan in de objectversie en
  blijven na herstart gelijk.
Recovery result: een fout bij de reviewer wordt hersteld door aanpassen in de
  kaart en opnieuw bouwen (#1064); de nieuwe versie wordt opnieuw beoordeeld.
Legacy-data result: bestaande annotaties met volledige richting en sterkte en
  bestaande bevestigde objecten blijven ongewijzigd; objecten met de oude
  sterkte-notatie blijven hun bestaande route volgen.
Required black-box scenario: GIVEN een aanbeveling uit annotatie zonder
  voorstel voor richting en sterkte; WHEN de medewerker haar gereedmeldt, het
  document wordt gebouwd en de reviewer op de reviewkaart ‘afraden · zwak’ kiest
  bij een bron die ‘overweeg niet’ zegt; THEN wordt de annotatie zonder
  blokkade gereed, wordt het object toegelaten met een signaal, wordt de keuze
  bevestigd en goedgekeurd, en wordt ‘sterk’ bij diezelfde bron geweigerd zonder
  wijziging.
Explicit non-goals: richting en sterkte wijzigen in de tweede review (die
  bevestigt de versie van de eerste); objecten die niet uit annotatie komen
  (hun voorstelregels blijven blokkerend); de beslisboom.
```

## Grenzen

- Alleen voor kennisobjecten uit annotatie wordt een ontbrekend voorstel een
  signaal (`recommendation_semantics_open`). Een volledig maar ongeldig voorstel
  blijft blokkeren, en objecten uit andere routes houden hun regels.
- Een half voorstel van Metis telt bij bouwen als geen voorstel; de annotatie
  zelf blijft ongewijzigd bewaard.

## Uitvoering (13 november 2026)

- `recommendation_semantics_v1.complete_annotation_semantics`: één regel voor
  wanneer het voorstel van Metis in een annotatie volledig is.
- Kaartcontrole (`human_annotation_preview_v1`) en toelating
  (`admission_gate_v1`): zonder volledig voorstel het signaal
  `recommendation_semantics_open` (in `HUMAN_SIGNAL_CODES`), alleen voor
  annotatie; een aanwezig voorstel wordt volledig gecontroleerd zoals voorheen.
- Bouwen (`human_annotation_materialisation_v1`): alleen een volledig voorstel
  gaat mee; anders geen voorstel, zodat het document niet faalt.
- Reviewkaart: in de eerste review twee keuzes in het formulier, vooraf ingevuld
  met het voorstel; zonder voorstel staat erbij dat Metis het niet kon
  vaststellen. De keuze wordt in `review_assessment_v1` en in beide
  goedkeurroutes (`ko_review_page_v1` en `review_command_v1`) gecontroleerd met
  dezelfde regel als goedkeuren. Geen keuze in de tweede review.
- De keuze staat alleen op de reviewkaart van kennisobjecten uit annotatie;
  andere objecten houden hun correctieroute en hun blokkade zonder voorstel.
- Een keuze telt alleen als paar (`review_assessment_v1.reviewer_semantics_choice`).
  Beide keuzes zijn verplicht in het formulier; een halve keuze wordt op de
  reviewkaart geweigerd met ‘Kies richting en sterkte van deze aanbeveling
  voordat je goedkeurt.’ en nooit stil aangevuld met het voorstel.
- Bewijs: `tests/test_reviewer_recommendation_semantics_1067.py` (black-box op
  native PostgreSQL: gereed zonder richting, gebouwd, toegelaten met signaal,
  ‘sterk’ geweigerd met de bestaande uitleg zonder wijziging, ‘afraden · zwak’
  goedgekeurd en bevestigd). Bijgewerkt naar het besluit:
  `tests/test_source_first_signals_1060.py` en
  `tests/test_d3_3_human_recommendation_semantics.py`. Karakteriseringsgoldens
  ongewijzigd.

## Deel B — stappenformulier uit de kaart (Class B)

Besluit William, 13 november 2026: het formulier mag de medewerker niet meer
zien; de kaart is de enige weg.

- `human_annotation_editor.js`: de kaart opent altijd; een bewaarde keuze voor
  het uitgebreide formulier wordt bij laden verwijderd. Open punten worden in de
  kaart hersteld (voorstel → vraag bij ‘Hoort erbij’, type → typekeuze,
  verplichte koppeling → de regel in de bron) of als melding getoond. Het
  typebewijs is altijd de uitspraak zelf. Een dubbele uitspraak is een
  validatieantwoord; − trekt het concept direct in. Een netwerkfout geeft
  “Geen verbinding met de server. Je werk staat nog hier; probeer opnieuw.”
- `human_annotation_ui_v1`: Nederlandse uitleg voor de codes die de kaart nu
  zelf toont, en één vaste melding voor een onbekende code.
- De verborgen opmaak van het stappenformulier dient nog als toestandsdrager
  van de kaart (type, rol, velden). Ze is onbereikbaar; opruimen is een aparte
  refactor zonder gedragswijziging.
- Bewijs: alle 21 browserproeven via de kaart (`tests/test_browser_knowledge_context.py`);
  herschreven: bouw-, bronselectie-, binding-, voorstel- en veerkrachtproef.
  `browser_human_annotation_check.cjs` en de hulpfuncties voor het
  stappenformulier zijn vervallen: wat ze bewezen en nog bestaat zit in de
  veerkracht-, selectie- en bouwproef.

## Deel C — richting voor de gebruiker, soort corrigeerbaar, uitleg op de plek

Besluit William, 14 november 2026: “Alle drie”, zonder extra stappen; de
gebruiker moet weten welke mijlpalen er komen. Vastgelegd in #1067 en MET-78.

- **Routeregel** (`src/review/knowledge_route_v1.py`): één regel met de
  mijlpalen Inleveren › Annoteren › Documentcontrole › Bouwen › Review ›
  (Tweede review) › Publicatie en één zin “Hierna: …”. De tweede review staat
  er alleen als die geldt: bij inleveren gekozen (annotatiepagina's) of voor dit
  object vereist (reviewkaart). De regel staat op de annotatiekaart, de
  documentcontrole en de reviewkaart van objecten uit annotatie. Hij wordt
  afgeleid van bestaande toestand (KO-status, bouwstatus, correctie,
  vierogenplicht) en voegt geen knop, vraag of stap toe.
- **Soort als kaartregel**: de kaart toont het soort altijd als regel met een
  keuzelijst. De keuzelijst is één blijvend element, zodat een keuze in
  uitvoering de focus houdt. Wijzigen houdt de selecties; de betekenisvelden
  van het oude soort vervallen en blijven open als signaal.
- **Uitleg via ?** bij Uitspraak, Soort, Hoort erbij en Onderbouwing: tikken
  klapt de uitleg open onder de regel (`aria-expanded`, geen hover-tooltip). De
  uitleg blijft open tijdens het werk.
- **Documentcontrole**: elk signaal staat op een eigen regel en de links
  plakken niet meer aan de volgende kop (Impeccable-audit).

### Bouwregel bij een gecorrigeerd soort (raakt de levenscyclus, fail-closed)

`revision_workflow._drop_confirmation_of_another_kind`: bij opnieuw bouwen nam
de nieuwe versie het eerder bevestigde soort over, waardoor een correctie van
het soort in de kaart verloren ging. Dit gat bestond al vóór deel B.

```text
Lifecycle entity: WorkingRevision (opvolgende kennisobjectversie uit annotatie)
Lifecycle transition: correctie in de kaart → opnieuw bouwen → nieuwe versie In review
Initial durable state: een gebouwde versie met bevestigd soort S.
Trigger: de annotatie krijgt in de kaart soort T ≠ S en wordt opnieuw gebouwd.
Authorization: ongewijzigd (bestaande bouw- en correctierechten).
Validation: ongewijzigd; alleen het gecorrigeerde soort wordt vergeleken.
Mutable entities: de nieuwe versie: zonder bevestiging van S, en zonder
  bevestigde richting en sterkte (die horen alleen bij een aanbeveling).
Immutable entities: de vorige versie en haar bevestigingen, bron, annotaties,
  bouwbewijs, releases.
Workflow state before/after: In review → In review (nieuwe versie, zoals elke correctie).
Release/Serving state: ongewijzigd; niets wordt uitgeleverd zonder nieuwe goedkeuring.
Expected UI result: de reviewkaart van de nieuwe versie toont T als voorgesteld soort.
Failure result: bij een bouwfout blijft de vorige versie ongewijzigd (bestaande bouw).
Restart result: de nieuwe versie bewaart T; de oude bevestiging blijft historie.
Legacy-data result: gelijk soort houdt alle bevestigingen; objecten buiten annotatie ongewijzigd.
Required black-box scenario: GIVEN een goedgekeurde versie met soort Toelichting;
  WHEN de reviewer via ‘Aanpassen in de kaart’ Definitie kiest en opnieuw bouwt;
  THEN toont de nieuwe versie Definitie en wordt die na beoordeling goedgekeurd.
Explicit non-goals: soort wijzigen op de reviewkaart zelf; objecten buiten annotatie.
```

### Bewijs

- `tests/test_knowledge_route_1067.py` (routeregel uit toestand, geen bediening)
  en `tests/test_kind_correction_1067.py` (bouwregel).
- Browser: `browser_annotation_suggestions_check.cjs` (route, ?, soort
  corrigeren), `browser_human_review_check.cjs` (route bij bouwen en review,
  soort corrigeren tot en met goedkeuren), `browser_source_first_card_check.cjs`.
- verify-this, met dezelfde reviewproef: VERIFIED.
  - Nulmeting `d7dddf3`: de proef faalt, want de kaart heeft geen soortkeuze.
  - Tussenmeting zonder bouwregel: de reviewkaart toont het oude soort.
  - Behandeling: de reviewkaart toont het nieuwe soort.
- Karakteriseringsgoldens: alleen het versienummer van `console.css` verandert;
  vergeleken met dat nummer weggefilterd zijn alle 31 bestanden gelijk.

### Besluiten William, 14 november 2026 (uit de Codex-review van #1070)

1. **Relatie naar een doel dat opnieuw wordt gebouwd: de relatie vervalt en wordt opnieuw bevestigd**
   (`revision_workflow._retarget_relations_to_rebuilt`).
   - Een bevestigde relatie noemt de exacte versie van het doel die de reviewer zag.
   - Krijgt dat doel in dezelfde bouw een nieuwe versie, dan:
     - vervalt de bevestiging;
     - wijst het voorstel naar de nieuwe versie, zodat de reviewer het opnieuw kan bevestigen.
   - Een bronobject dat zelf niet veranderde, krijgt een nieuwe versie en gaat terug naar de review, want zijn
     goedkeuring ging over de oude doeltekst.
   - Een nieuwe versie kan weer andere relaties raken. Daarom herhaalt deze stap zich tot er niets meer
     verandert, met een grens die een eindeloze lus weigert.
   - Fail-closed. Dit gat bestond al vóór slice 5 en gold voor elke correctie van een doel.
   - Bewijs: `tests/test_kind_correction_1067.py::test_a_relation_to_a_rebuilt_target_is_confirmed_again`, op
     echte gebouwde objecten.
2. **Soort wisselen in de kaart: terugzetten herstelt het voorstel van Metis, zonder extra vraag.**
   - De kaart onthoudt de betekenisvelden per soort zolang de kaart openstaat.
   - Bewijs: de suggestieproef (aanbeveling → toelichting → aanbeveling: de richting komt terug). Die proef faalt
     zonder de wijziging.
3. **Soortkeuze tijdens ‘Gereed’.** Zolang ‘Gereed’ bezig is, staat de soortkeuze uit. Anders maakte een keuze in
   dat moment de opslag ongezien af. Dat was de oorzaak van de browserfouten die alleen in CI optraden.
   - Bewijs: de bindingsproef met een vertraagde controle.
