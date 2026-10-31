# MET-36: objectversies alleen toevoegen (één schrijfmodel voor kennisobjecten)

Change class: A
Promise: Elke mutatie van een bestaand werksnapshot schrijft alleen de wijziging (nieuwe versies en de huidige rijen die volgens `validate_revision_write` mogen veranderen), via één begrensde opdracht. Het volledig verwijderen en opnieuw invoegen van alle objecten van een snapshot is alleen toegestaan bij het aanmaken (ingest). De kosten van een mutatie groeien met de wijziging, niet met het document, en een lopende mutatie houdt aanmelden nooit tegen.
Proof: zie §8; een schaaltest op de omvang van Richtlijn Smetten, een gelijkwaardigheidstest oud tegenover nieuw per route, een weigeringstest en een test met gelijktijdig aanmelden. Alle tests moeten falen op main b5fab075.
Touches lifecycle invariants: yes (revisiegeschiedenis, werksnapshot, bevriezing na publicatie)
Rewrite risk: high

Taalregel: regels gebruiken MOET / MAG NIET / NOOIT. Bronnen: incidenten 2026-10-30 en 2026-10-31 (MET-33), inventarisatie MET-36 (Linear-comment 2026-10-31), besluit projectlead 2026-10-31: "behalve bij ingest zie ik geen reden voor opnieuw alles herschrijven".

## 1. Aanleiding

- Een batch-uitsluiting op Richtlijn Smetten hield de schrijftransactie 11 minuten of langer vast. In productie liep `DELETE FROM workflow.document_objects WHERE snapshot_id=$1` zonder wait event. Aanmeldingen wachtten erachter: `sign_in` wachtte op de `accounts`-rij, de andere aanmeldingen op identity-lock 734821095. De backend is handmatig gestopt; er is niets half opgeslagen.
- Oorzaak: `write_bundle` (`workflow_document_concurrency_v1`, `workflow_documents_cutover_v1`) vervangt bij elke mutatie het hele snapshot. De per-rij trigger `advance_object_generation` (migratie 021) werkt per verwijderde of ingevoegde rij de documentrij bij. #943 nam alleen het werk per lid in de bronopdracht weg.
- Het juiste model bestaat al voor één route: `execute_review_command` met `apply_review_changes`, voor de losse beoordeling. Alle andere mutaties gebruiken nog de bestandsachtige volledige herschrijving.

## 2. Domeinmodel

Ubiquitous terms:

- **Werksnapshot**: een niet-gepubliceerde documentversie met zijn objectversies. Het is de aggregate-grens.
- **Objectversie**: (snapshot_id, object_id, object_version) plus payload. De identiteit is de primaire sleutel (migratie 002).
- **Geschiedenis**: alle versies van een object, in volgorde van toevoegen (`position`).
- **Huidige versie**: de laatste versie van een object (`current_revisions`).
- **Objectmutatie**: één domeinopdracht die objectversies toevoegt, en waar dat mag de huidige rij bijwerkt.
- **Aanmaak (ingest)**: de enige opdracht die de volledige objectlijst van een snapshot vastlegt.

| Rol | Wie | Mag | Mag niet |
|---|---|---|---|
| Mutatieopdracht | alle routes behalve ingest (zie §4) | versies achteraan toevoegen; de huidige rij bijwerken als `validate_revision_write` de transitie toestaat | een rij verwijderen, de geschiedenis herordenen of een historische versie wijzigen |
| Aanmaak | `ingest`, en de eerste vastlegging van een nieuw snapshot | de volledige objectlijst schrijven | een bestaand snapshot met objecten overschrijven |
| Opslag (kernel) | `apply_object_changes` (de veralgemeniseerde `apply_review_changes`) | de delta valideren en schrijven, de teller ophogen | een volledige vervanging uitvoeren voor een mutatieopdracht |

## 3. Invarianten

| Id | Invariant | Eigenaar en handhaving | Weerlegd door |
|---|---|---|---|
| V1 | Een mutatieopdracht MAG NOOIT een objectrij van een bestaand snapshot verwijderen of herordenen | Opslag: `apply_object_changes` weigert (`workflow_review_history_removal_or_reorder`, bestaand) | weigeringstest |
| V2 | Een historische (niet-huidige) versie MAG NOOIT veranderen; de huidige rij alleen volgens `validate_revision_write` | Opslag: de transitieketen wordt gevalideerd onder het rijslot (bestaand in `apply_review_changes`) | weigeringstest |
| V3 | `write_bundle` met objecten voor een bestaand werksnapshot MOET worden geweigerd, behalve via de aanmaakroute | Opslag, nieuw: `workflow_object_replace_forbidden` | weigeringstest en inventaristest (geen bypass) |
| V4 | Een gepubliceerd snapshot is bevroren | Opslag (bestaand: `PUBLISHED_WORKING_REVISION_IMMUTABLE`) | bestaande test |
| V5 | Een mutatie is alles of niets, in één transactie | Opslag (bestaand) | test met een falende commit |
| V6 | Het aantal geschreven objectrijen en triggeraanroepen per mutatie is begrensd door de wijziging | Opslag: alleen delta-INSERT en delta-UPDATE | schaaltest (tellers plus een tijdsgrens) |
| V7 | Een lopende objectmutatie MAG aanmelden NOOIT blokkeren | Identiteit (zie §5, besluit D1) | gelijktijdigheidstest |
| V8 | De verouderingscontrole blijft gelden | Opslag: generatieteller of objectset (bestaand) | bestaande conflicttests |

**Beleidsstandaard (geen invariant):** de volgorde van nieuwe versies is de volgorde van toevoegen (`position = max+1`). Lezers sorteren op `position` (vastgesteld: `review_card_inputs_postgres_v1:189`, `workflow_document_concurrency_v1:122/232`).

## 4. Routes (vastgesteld in de inventarisatie)

| Route | Functie | Was | Wordt |
|---|---|---|---|
| Losse beoordeling | `review_object` → `execute_review_command` | delta | ongewijzigd |
| Tweede beoordeling | `approve_second_review` | volledig | mutatieopdracht |
| Correctie | `correct_object` | volledig | mutatieopdracht |
| Type/relaties | `confirm_object_type`, `confirm_relations`, `_commit_knowledge_change` | volledig | mutatieopdracht |
| Bronbesluit los, batch, groep | `_confirm_source_context`, `_source_batch` | volledig | mutatieopdracht |
| Heropenen | `closed_review_loop_v1._reopen_for_review` | volledig | mutatieopdracht |
| Herstel samenvoegen | `deterministic_review_repair_v1._supersede_merge_targets` | volledig | mutatieopdracht |
| Participatie, beslisboom | `review_participation_v1._execute`, `decision_review_commands_v1._execute` | volledig | mutatieopdracht |
| Klasse wijzigen | `promote_class` (governance van de huidige rijen terug naar `needs_review`) | volledig | mutatieopdracht (update van de huidige rij, zie D3) |
| Herverwerking | `reextract_unpublished` (alleen zonder menselijk werk: `pre_review_retry_existing_work`) | volledig, vervangt kandidaten | zie besluit D2 |
| Aanmaak | `ingest` (3 aanroepen) | volledig | aanmaakroute, de enige |
| Cutover-migratie | `workflow_documents_cutover_v1._save_objects` | volledig | eenmalige migratie, blijft buiten de mutatieroute |

## 4a. Besluiten

- **D1 (inloggen loskoppelen):** `execute_review_command` doet `_require_role(..., current=True)` → `account_by_id(for_share=True)`, dus `FOR SHARE` op de `accounts`-rij voor de hele transactie. `sign_in` neemt `FOR UPDATE` op dezelfde rij onder identity-lock 734821095.
  - **Voorstel:** de identiteitscontrole in een domeinopdracht wordt `FOR KEY SHARE`, en `sign_in` gebruikt `FOR NO KEY UPDATE` (de sleutel verandert niet). Die twee conflicteren niet. Pensionering en blokkering blijven bewaakt, omdat beide de `accounts`-rij in `FOR NO KEY UPDATE` bijwerken.
  - **Open:** dit vraagt een apart bewijs dat pensionering tijdens een lopende opdracht nog steeds wordt geweigerd bij de eerstvolgende opdracht.
- **D2 (herverwerking):** het besluit van de projectlead is dat alleen ingest alles herschrijft. Herverwerking (`reextract_unpublished`) wordt daarom een mutatieopdracht:
  - kandidaten die vervallen, krijgen een nieuwe versie met `validation_status=superseded` en de bestaande reden `same-source candidate retirement`;
  - nieuwe kandidaten worden toegevoegd;
  - er wordt niets verwijderd.
  - **Gevolg:** de geschiedenis van eerdere vormingspogingen blijft bewaard en herleidbaar; dat is een winst voor de herkomst. Het snapshot groeit bij herhaalde herverwerking.
  - **Te bewijzen:** lezers en de publicatiegereedheid negeren vervallen kandidaten.
- **D3 (klasse wijzigen):** `promote_class` zet de governance van de huidige rijen terug. Dat mag als update van de huidige rij, mits `validate_revision_write` dit toestaat. Anders wordt het een nieuwe versie per object; dat wordt vastgesteld in slice 3.

## 5. Transactiegrens

- Een mutatieopdracht doet in één PostgreSQL-transactie:
  1. de autorisatielock;
  2. het documentrijslot;
  3. de identiteitscontrole (D1);
  4. de verouderingscontrole;
  5. het inlezen van alleen de geraakte geschiedenissen;
  6. de domeinwijziging;
  7. `apply_object_changes` (delta);
  8. de bindingdelta;
  9. het ledger-event.
- Na de commit volgen alleen de spiegels (#678, ongewijzigd).
- Aanmaak: één transactie met de volledige lijst, alleen als het snapshot nog geen objecten heeft.

## 6. Falen, herstel, idempotentie en gelijktijdigheid

- Falen: rollback; niets geschreven; de oorspronkelijke fout wint (#678 U4).
- Herstart: verandert niets aan de domeinwaarheid.
- `command_id` blijft idempotent waar het bestaat.
- Gelijktijdige mutaties: de eerste wint, de tweede krijgt `snapshot_object_write_conflict`.

## 7. Audit en herleidbaarheid

- Er blijft één ledger-event per opdracht.
- Geen enkele versie verdwijnt nog uit een bestaand snapshot (V1). Dat geldt ook voor vervallen kandidaten (D2).

## 8. Bewijs (acceptatie; elke test MOET falen op b5fab075)

1. **Schaal:** een snapshot van ten minste 1500 objectversies (gegenereerde PDF, native PostgreSQL). Per route uit §4 schrijft één mutatie ten hoogste het aantal gewijzigde rijen; de triggerteller stijgt met ten hoogste het aantal gewijzigde rijen; de duur blijft onder een vaste grens.
2. **Gelijkwaardigheid:** per route levert de oude volledige herschrijving dezelfde eindinhoud op als de nieuwe delta (rijen, payload, `position`-volgorde, revisietoken), op dezelfde invoer.
3. **Weigering:**
   - een mutatie die een rij verwijdert of herordent, of een historische versie wijzigt, wordt door de opslag geweigerd;
   - `write_bundle` met objecten op een bestaand werksnapshot wordt geweigerd (V3);
   - een gepubliceerd snapshot blijft bevroren.
4. **Geen bypass:** een inventaristest faalt als er een nieuwe aanroep van `write_bundle(objects=…)` buiten de aanmaakroute bijkomt.
5. **Gelijktijdigheid (D1):** `sign_in` van dezelfde reviewer tijdens een lopende mutatie is binnen een seconde klaar. Een gepensioneerde account wordt bij de volgende opdracht geweigerd.
6. **Herverwerking (D2):** vervallen kandidaten blijven bewaard als `superseded` en tellen niet mee voor review en publicatiegereedheid.
7. **Regressie:** de suites voor review, publicatie, verwerking, B6 en characterization blijven groen.

## 9. Rewrite-risk mitigation

```text
Rewrite target: de schrijfgrens voor objecten van bestaande werksnapshots (write_bundle met objecten en _commit_prepared_store met objecten), naar één delta-mutatieopdracht.
Why local patching is insufficient: elke route die het hele snapshot herschrijft, heeft hetzelfde schaalgedrag. Een fix per knop (#943) liet de oorzaak bestaan; het incident van 2026-10-31 kwam terug via dezelfde opslaggrens. Alleen één schrijfmodel met weigering van volledige vervanging (V3) voorkomt een terugval elders.
Current authority/writer/reader map: authority = PostgreSQL workflow.document_objects (ongewijzigd). Writers = write_bundle (concurrency en cutover), apply_review_changes (delta, alleen review_object), workflow_documents_postgres_v1 INSERT (migratie). Readers sorteren op position of lezen current_revisions; trigger advance_object_generation per rij (ongewijzigd).
Supported runtime topologies: R+ lokaal en productie (PostgreSQL). De bestandstopologie (zonder PostgreSQL) houdt de bestaande lijstopslag; daar speelt het schaalprobleem niet. Tier D/I-weigering ongewijzigd.
Persisted-state impact: geen schema- of datamigratie. Bestaande rijen en posities blijven geldig; nieuwe rijen worden achteraan toegevoegd.
Compatibility/migration plan: expand -> migrate -> contract. (1) expand: apply_object_changes als veralgemenisering van apply_review_changes, plus een bounded mutation command naast execute_review_command. (2) migrate: route voor route uit §4 overzetten, elk met een gelijkwaardigheidstest; bronbesluiten eerst (blokkeert MET-33). (3) contract: V3 aanzetten, zodat write_bundle met objecten op een bestaand snapshot wordt geweigerd; daarna de inventaristest.
Rollback/recovery plan: per stap terug te draaien met een revert. Er is geen persistente afhankelijkheid: delta-rijen zijn gewone rijen die de oude code ook leest. Na contract (3) betekent een rollback alleen dat de weigering weer uit gaat.
Cutover trigger: per stap merge na groene CI, de schaaltest op productieschaal en GO van de projectlead. Productie per stap deployen; eerst één kleine sectie proberen op Richtlijn Smetten.
Cleanup/decommission criteria: na stap 3 bestaat er in src/ geen aanroep van write_bundle(objects=…) buiten de aanmaakroute; de inventaristest bewaakt dat.
Failure blast radius: alle objectmutaties op werksnapshots. Ergste geval van een fout: een opdracht wordt geweigerd (fail closed) of krijgt een conflict. Stille dataverandering wordt uitgesloten door V1, V2 en de gelijkwaardigheidstests.
Adversarial proof matrix: §10.
```

## 10. Adversarial review (vóór merge in te vullen per stap)

| Aanval | Verwacht |
|---|---|
| Een route geeft een lijst zonder één bestaande rij door (zou in het oude model stil verwijderen) | Geweigerd (V1); test |
| Een route wijzigt de payload van een historische versie | Geweigerd (V2) |
| Een nieuwe ontwikkelaar roept `write_bundle(objects=…)` aan voor een bestaand snapshot | Geweigerd (V3) en de inventaristest wordt rood |
| Twee reviewers muteren hetzelfde snapshot tegelijk | De eerste wint, de tweede krijgt een conflict; geen verloren update |
| Een mutatie faalt na de INSERT, vóór de commit | Rollback; geen rij en geen tellerverhoging |
| Herverwerking na menselijk werk | Bestaande weigering `pre_review_retry_existing_work` blijft; test |
| Pensionering tijdens een lopende opdracht (D1) | De eerstvolgende opdracht van die account wordt geweigerd |
| Een lezer die de volgorde aanneemt | Positie-volgorde gelijk aan het oude model (gelijkwaardigheidstest) |
| Een groot document met 1500+ versies | Schaaltest binnen de grens; geen volledige scan in de schrijfstap |
| Herstart midden in een mutatie | Rollback door PostgreSQL; de domeinwaarheid ongewijzigd |

## 11. Buiten scope

- De trigger `advance_object_generation` wijzigen. Hij blijft per rij, maar raakt na de fix alleen de gewijzigde rijen.
- De opslag van de envelope (`workflow.documents`).
- Leesprestaties van Vorming (de pagina met 37 s laadtijd is een aparte bevinding).

## 12. Volgorde van uitvoering (na GO op dit contract)

1. Slice 3a: expand (`apply_object_changes` plus de mutatieopdracht) en de bronbesluiten migreren (los, batch, groep), met schaal-, gelijkwaardigheids- en weigeringstests. Dit ontgrendelt MET-33.
2. Slice 3b: de overige routes uit §4, één PR per routegroep.
3. Slice 4: D2 herverwerking.
4. Slice 5: D1 inloggen.
5. Slice 6: contract (V3) en de inventaristest.
