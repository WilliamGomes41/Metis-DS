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
