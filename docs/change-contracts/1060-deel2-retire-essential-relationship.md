# #1060 deel 2 — Het essentiële verband helemaal weg

Change class: A
Promise: Een annotatie kent geen essentieel verband meer. Het opslagcommando, de opgeslagen annotatie, de databasecontrole en de broncontext van een gebouwd kennisobject dragen geen `required_for_meaning`, `required_links` of terugnamereden meer. Een gekoppeld stuk tekst weghalen is een gewone correctie. De kernel weigert een client die de oude velden nog meestuurt. Een object dat met het oude veld is gebouwd, wordt als `source_bound_context_stale` geweigerd en nooit stil herlezen.
Proof: Black-box op native PostgreSQL: het opslagcommando weigert beide oude velden, een verband weghalen slaagt in kernel en databasecontrole, en een gebouwd object draagt het veld niet. Op `main` (`fa8000e`) faalt dit, want daar slaagt het meesturen en draagt het object het veld. Een object met het oude veld wordt als stale geweigerd. Migratie 042 staat in de geordende lijst en de toepassingsproef.
Touches lifecycle invariants: yes
Rewrite risk: high

Part of MET-78. Besluit William, 15 november 2026: “Ga door met deel twee”, na “Een schone code gaat in dit geval boven behoud”. Vastgelegd in #1060 en MET-78. Het ene bestaande document wordt verwijderd en opnieuw ingeleverd.

## Huidige toestand (op `main`)

- De kaart koppelt alles met `required_for_meaning: false` en stuurt `required_links: []` mee (#1076, #1077). Het stappenformulier dat een verband essentieel kon maken, is weg.
- De kernel (`human_annotation_v1._validate` en `_relationship_history`) neemt beide velden nog aan. Hij eist dat een essentieel verband bij een volgende opslag blijft staan, of wordt teruggenomen met een reden (`annotation_required_relationship_missing`, `annotation_relationship_withdrawal_required`).
- De databasecontrole `workflow.guard_annotation_input_transition` (migratie 035) eist hetzelfde, met de hulpfunctie `workflow.annotation_relationship_key`.
- De preview meldt een open essentieel verband. Het overzicht toont ‘(essentieel)’ en ‘Relatieverplichtingen’.
- `bind_context` neemt `required_for_meaning` mee in de broncontext van een gebouwd kennisobject. `validate_context` bouwt die context opnieuw op en vergelijkt haar exact.

## Wijziging

- Kernel: `_validate` weigert `required_for_meaning` op een bereik (`annotation_anchor_invalid`) en `required_links` in de selectie (`annotation_selection_invalid`), en slaat geen van beide meer op. `_relationship_history` controleert alleen nog de vorm van de relatiesleutels en de stale-regel voor `field_evidence`.
- Database: migratie `042_retire_essential_relationships.sql` vervangt `guard_annotation_input_transition` door dezelfde functie zonder de controles op essentiële verbanden. De versie- en `field_evidence`-controles en de controle op de laatste revisie blijven gelijk. Daarna verdwijnt `annotation_relationship_key`.
- Projectie en materialisatie: `bind_context`, `bind_candidate` en de materialisatie dragen geen `required_for_meaning` of `required_links` meer.
- Preview en werkplek: de melding, het label ‘(essentieel)’, ‘Relatieverplichtingen’ en de twee foutteksten verdwijnen. De kaart en `bindRange` sturen de velden niet meer mee.

De versiemarkering verandert niet. Een kaartopslag krijgt `human-annotation-input-v2` al door `field_evidence` en `relationship_id`.

## Programma-ontwerp (high rewrite risk)

Rewrite target: het essentiële verband in annotatie-invoer, de kernelcontrole, de databasecontrole (035 → 042), de broncontext van een gebouwd object, de preview en het overzicht.
Why local patching is insufficient: de regel staat op vier plekken: kernel, database, broncontext en weergave. Wie er één laat staan, houdt een regel over die niemand meer kan bevredigen of die oude data anders leest dan nieuwe. Alleen het geheel weghalen geeft één betekenis.
Current authority/writer/reader map: schrijver is `annotations.save`, via de kaart (`human_annotation_editor.js`, `human_annotation_binding.mjs`) en de bronrol-POST in `human_annotation_ui_v1`. Bewaker is de kernel `_validate`/`_relationship_history` plus de databasetrigger. Lezers zijn de preview (`inspect_document`), het overzicht, de materialisatie, `bind_candidate` en `validate_context`, die wordt gebruikt door de review, `source_bound_fields_v3`, de bronbeoordeling en de containers.
Supported runtime topologies: de bestaande. De productieconsole draait op Azure PostgreSQL met de workflowmigraties via `workflow_postgres_migration_v1`. Lokaal en in CI draait native PostgreSQL met dezelfde migratielijst.
Persisted-state impact: nieuwe annotatieversies en gebouwde objecten dragen de velden niet. Bestaande annotatieversies blijven onveranderd staan, want de geschiedenis is onveranderlijk. Bestaande gebouwde objecten passen niet meer bij hun broncontext. Bij dezelfde bron en annotatie blijven object-ID, tekst en inhoud gelijk. Alleen de afgeleide hashes veranderen: `content_hash`, `canonical_object_hash`, `context_hash`, `binding_hash`, `payload_hash` en `semantic_spec_hash`. Een herbouw levert dus een nieuwe objectversie op die opnieuw door de review moet (vastgelegd in `tests/test_document_spec_v1.py`).
Compatibility/migration plan: geen datamigratie. Er is één bestaand document. William verwijdert het en levert het opnieuw in (besluit 15 november 2026). Migratie 042 wordt in Azure toegepast met de bestaande gecontroleerde migratiestap, vóór of samen met de uitrol van deze code. Een oudere client die de velden meestuurt, krijgt een weigering in plaats van een stille herinterpretatie.
Rollback/recovery plan: terugdraaien is de code terugzetten en migratie 035 opnieuw toepassen (`CREATE OR REPLACE` van de functie, hulpfunctie terug). Annotaties die intussen zonder de velden zijn opgeslagen, blijven geldig onder 035, want een ontbrekend veld telt daar als niet essentieel.
Cutover trigger: merge door William, gevolgd door de migratiestap in Azure en het opnieuw inleveren van het ene document.
Cleanup/decommission criteria: na de merge verwijst geen code of test meer naar `required_for_meaning`, `required_links`, `annotation_required_relationship_missing` of `annotation_relationship_withdrawal_required`. Migratie 035 blijft als historie.
Failure blast radius: alleen annotatie-invoer en kennisobjecten die uit annotaties zijn gebouwd. Wordt de migratie vergeten, dan blijft de oude trigger staan. Die vindt in nieuwe payloads geen essentiële verbanden en weigert dus niets. Alleen een oude annotatie met een essentieel verband zou bij een nieuwe opslag nog worden geweigerd, en zo'n annotatie is er na het opnieuw inleveren niet.
Adversarial proof matrix: de acht gevallen hieronder, elk met een test (zie Bewijs).
- een client stuurt `required_for_meaning` mee: geweigerd (`annotation_anchor_invalid`);
- een client stuurt `required_links` mee: geweigerd (`annotation_selection_invalid`);
- een verband weghalen: slaagt in kernel en databasecontrole, ook na een herstart;
- twee gelijktijdige correcties (veld leegmaken tegen verband weghalen): één wint, de ander krijgt `annotation_write_conflict`;
- een oudere writer laat `selection_version` of `field_evidence` vallen: de databasecontrole weigert het (`annotation_client_contract_stale`);
- een back-up met een zelfconsistente revisie zonder `field_evidence`: het herstel weigert die;
- een object dat met het oude veld is gebouwd: `source_bound_context_stale`;
- de migratielijst eindigt op 042 en de toepassingsproef past 040–042 toe.

## Lifecycle-specificatie (§14)

```text
Lifecycle entity: Annotation (annotatieversies) en de WorkingRevision die eruit wordt gebouwd.
Lifecycle transition: annotatie opslaan (concept → gereed, gereed → gecorrigeerd) en bouwen → review.
Initial durable state: een document met annotaties uit de kaart (zonder essentiële verbanden) of het ene oude document.
Trigger: de medewerker slaat een annotatie op of bouwt de kennisobjecten.
Authorization: ongewijzigd (onderzoeker of benoemde deelnemer).
Validation: de kernel weigert de oude velden; de databasecontrole houdt de versie- en field_evidence-regels.
Mutable entities: annotation_versions en annotation_heads (nieuwe revisies), gebouwde objecten (nieuwe versies).
Immutable entities: bestaande annotatieversies, bron, extractie, releases, publicatieregister.
Workflow state before: annotatie concept of gereed; objecten in review.
Workflow state after: ongewijzigd; alleen de essentiële plicht is weg.
Release state before: geen release.
Release state after: ongewijzigd.
Serving state before: niet uitgeleverd.
Serving state after: ongewijzigd.
Expected API result: opslaan zonder de oude velden slaagt; met een van beide velden volgt een weigering met een gesloten code.
Expected UI result: het overzicht toont geen ‘(essentieel)’ en geen ‘Relatieverplichtingen’; de kaart werkt zoals voorheen.
Failure result: een geweigerde opslag verandert niets (generatie gelijk).
Restart result: een weggehaald verband blijft weg na een herstart; er blijft geen open verplichting staan.
Recovery result: herstel uit een back-up past dezelfde databasecontrole toe en weigert een revisie die field_evidence laat vallen.
Legacy-data result: objecten die met het oude veld zijn gebouwd, worden geweigerd met source_bound_context_stale. Het ene document wordt verwijderd en opnieuw ingeleverd. Bestaande annotatieversies blijven als historie staan.
Required black-box scenario: GIVEN een gereed annotatie met een gekoppelde voorwaarde; WHEN de medewerker de voorwaarde weghaalt en opslaat; THEN slaagt de opslag en staat er na een herstart alleen de kern. AND GIVEN een client die required_for_meaning of required_links meestuurt; THEN volgt een weigering en blijft de generatie gelijk. AND GIVEN een gebouwd object; THEN draagt de broncontext geen required_for_meaning.
Explicit non-goals: bestaande annotatieversies herschrijven; de versiemarkering wijzigen; de relatiesleutel (relationship_id) wijzigen.
```

## Bewijs

- `tests/test_human_annotation_postgres.py`: weigering van beide oude velden; geen veld na opslaan.
- `tests/test_human_annotation_input_v2_postgres.py`: een verband weghalen zonder plicht, een gelijktijdige correctie, een oudere writer en een vervalste back-up.
- `tests/test_human_annotation_build_postgres.py`: de gebouwde broncontext draagt het veld niet.
- `tests/test_human_annotation_materialisation.py`: een object met het oude veld is stale.
- `tests/test_workflow_postgres_migration_v1.py`: 042 staat in de lijst en wordt toegepast.
- `tests/test_document_spec_v1.py`: de vastgepinde bouwhash is bijgewerkt. Ten opzichte van `main` verschillen alleen de afgeleide hashes.
- De browserproeven van de kaart en de bindingchecks.
